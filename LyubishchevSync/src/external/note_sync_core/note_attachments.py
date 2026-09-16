from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
import difflib
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple


BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "div", "figcaption", "figure",
    "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "li", "main",
    "nav", "p", "section", "td", "th",
}
ATTACHMENT_TAGS = {"img", "object", "embed", "video", "audio"}


def _normalise_cid(value: str) -> str:
    value = (value or "").strip().strip("<>")
    return value[4:] if value.lower().startswith("cid:") else value


def _normalise_text(value: str) -> str:
    return " ".join(html.unescape(value or "").replace("\xa0", " ").split())


@dataclass
class AttachmentSnapshot:
    attachment_id: str
    content_id: str
    name: str
    obsidian_path: Optional[str] = None
    sha256: Optional[str] = None

    @property
    def cid_key(self) -> str:
        return _normalise_cid(self.content_id)


@dataclass
class _Token:
    raw: str
    kind: str
    tag: str = ""
    data: str = ""
    attrs: Tuple[Tuple[str, Optional[str]], ...] = ()


@dataclass
class NoteLine:
    index: int
    text: str
    start_token: int
    end_token: int
    text_tokens: List[int] = field(default_factory=list)
    attachment_cids: List[str] = field(default_factory=list)
    attachments: List[AttachmentSnapshot] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        payload = f"{self.index}\0{_normalise_text(self.text)}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class NoteHTMLDocument(HTMLParser):
    """Loss-minimising Notes HTML parser.

    Tags are retained using get_starttag_text(); text mutations are recorded against
    token indexes so unrelated rich text and attachment markup survive serialisation.
    """

    def __init__(self, source: str):
        super().__init__(convert_charrefs=False)
        self.source = source or ""
        self.tokens: List[_Token] = []
        self.lines: List[NoteLine] = []
        self.orphan_cids: List[str] = []
        self._line_start = 0
        self._line_text_tokens: List[int] = []
        self._line_text_parts: List[str] = []
        self._line_cids: List[str] = []
        self._last_nonempty: Optional[NoteLine] = None
        self._anonymous_attachment_count = 0
        self._replacements: Dict[int, str] = {}
        self._suffixes: Dict[int, List[str]] = {}
        self._insert_before_end: List[str] = []
        self.feed(self.source)
        self.close()
        self._finish_line(len(self.tokens) - 1)

    def _add(self, token: _Token) -> int:
        self.tokens.append(token)
        return len(self.tokens) - 1

    @staticmethod
    def _cid_from_attrs(attrs: Sequence[Tuple[str, Optional[str]]]) -> str:
        for key, value in attrs:
            if not value:
                continue
            if key.lower() in {"src", "data", "href", "content-id", "cid"}:
                match = re.search(r"(?:cid:)?([^\s\"'>]+)", value, re.IGNORECASE)
                if match and (value.lower().startswith("cid:") or key.lower() in {"content-id", "cid"}):
                    return _normalise_cid(match.group(1))
        return ""

    def _finish_line(self, end_token: int) -> None:
        raw_text = "".join(self._line_text_parts)
        text = _normalise_text(raw_text)
        if text or self._line_cids:
            line = NoteLine(
                index=len(self.lines),
                text=text,
                start_token=self._line_start,
                end_token=max(end_token, self._line_start),
                text_tokens=list(self._line_text_tokens),
                attachment_cids=list(self._line_cids),
            )
            self.lines.append(line)
            if text:
                self._last_nonempty = line
            elif self._last_nonempty and line.attachment_cids:
                self._last_nonempty.attachment_cids.extend(line.attachment_cids)
                line.attachment_cids.clear()
        self._line_start = max(end_token + 1, 0)
        self._line_text_tokens = []
        self._line_text_parts = []
        self._line_cids = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if tag in BLOCK_TAGS and (self._line_text_parts or self._line_cids):
            self._finish_line(len(self.tokens) - 1)
        idx = self._add(_Token(self.get_starttag_text(), "start", tag=tag, attrs=tuple(attrs)))
        if tag == "br":
            self._finish_line(idx)
            return
        if tag in ATTACHMENT_TAGS:
            cid = self._cid_from_attrs(attrs)
            if not cid:
                has_embedded_media = any(
                    value and (
                        value.lower().startswith("data:image/")
                        or value.lower().startswith("data:application/")
                        or key.lower() in {"src", "data"}
                    )
                    for key, value in attrs
                )
                if has_embedded_media:
                    cid = f"__anonymous_attachment_{self._anonymous_attachment_count}"
                    self._anonymous_attachment_count += 1
            if cid:
                if self._line_text_parts:
                    self._line_cids.append(cid)
                elif self._last_nonempty:
                    self._last_nonempty.attachment_cids.append(cid)
                else:
                    self.orphan_cids.append(cid)

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        idx = self._add(_Token(f"</{tag}>", "end", tag=tag.lower()))
        if tag.lower() in BLOCK_TAGS:
            self._finish_line(idx)

    def handle_data(self, data: str) -> None:
        idx = self._add(_Token(data, "data", data=data))
        self._line_text_tokens.append(idx)
        self._line_text_parts.append(data)

    def handle_entityref(self, name: str) -> None:
        raw = f"&{name};"
        idx = self._add(_Token(raw, "data", data=html.unescape(raw)))
        self._line_text_tokens.append(idx)
        self._line_text_parts.append(html.unescape(raw))

    def handle_charref(self, name: str) -> None:
        raw = f"&#{name};"
        idx = self._add(_Token(raw, "data", data=html.unescape(raw)))
        self._line_text_tokens.append(idx)
        self._line_text_parts.append(html.unescape(raw))

    def handle_comment(self, data: str) -> None:
        self._add(_Token(f"<!--{data}-->", "other"))

    def handle_decl(self, decl: str) -> None:
        self._add(_Token(f"<!{decl}>", "other"))

    def unknown_decl(self, data: str) -> None:
        self._add(_Token(f"<![{data}]>", "other"))

    def bind_attachments(self, attachments: Iterable[AttachmentSnapshot]) -> None:
        unique_attachments = []
        seen_ids = set()
        for item in attachments:
            if item.attachment_id in seen_ids:
                continue
            seen_ids.add(item.attachment_id)
            unique_attachments.append(item)
        by_cid = {item.cid_key: item for item in unique_attachments if item.cid_key}
        assigned_ids = set()
        anonymous_slots = []
        for line in self.lines:
            line.attachments = []
            for cid in line.attachment_cids:
                if cid.startswith("__anonymous_attachment_"):
                    anonymous_slots.append(line)
                    continue
                item = by_cid.get(cid)
                if item and item.attachment_id not in assigned_ids:
                    line.attachments.append(item)
                    assigned_ids.add(item.attachment_id)
        remaining = [item for item in unique_attachments if item.attachment_id not in assigned_ids]
        for line, item in zip(anonymous_slots, remaining):
            if item.attachment_id not in {existing.attachment_id for existing in line.attachments}:
                line.attachments.append(item)
                assigned_ids.add(item.attachment_id)

    def append_suffix(self, line_index: int, suffix: str) -> None:
        if not suffix or not (0 <= line_index < len(self.lines)):
            return
        line = self.lines[line_index]
        anchor = line.text_tokens[-1] if line.text_tokens else line.end_token
        self._suffixes.setdefault(anchor, []).append(html.escape(suffix, quote=False))

    def replace_line_text(self, line_index: int, value: str) -> None:
        if not (0 <= line_index < len(self.lines)):
            return
        line = self.lines[line_index]
        if line.text_tokens:
            self._replacements[line.text_tokens[0]] = html.escape(value, quote=False)
            for token_index in line.text_tokens[1:]:
                self._replacements[token_index] = ""
        else:
            self._suffixes.setdefault(line.end_token, []).append(html.escape(value, quote=False))

    def append_line(self, value: str) -> None:
        self._insert_before_end.append(f"<div>{html.escape(value, quote=False)}</div>")

    def reconcile_text_lines(self, new_lines: Sequence[str]) -> None:
        old_lines = [line.text for line in self.lines]
        matcher = difflib.SequenceMatcher(a=old_lines, b=list(new_lines), autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            if tag == "replace":
                pair_count = min(i2 - i1, j2 - j1)
                for offset in range(pair_count):
                    self.replace_line_text(i1 + offset, new_lines[j1 + offset])
                for old_idx in range(i1 + pair_count, i2):
                    old = self.lines[old_idx]
                    replacement = f"{old.text} [已解除同步]" if old.attachments else ""
                    self.replace_line_text(old_idx, replacement)
                for new_idx in range(j1 + pair_count, j2):
                    self.append_line(new_lines[new_idx])
            elif tag == "delete":
                for old_idx in range(i1, i2):
                    old = self.lines[old_idx]
                    replacement = f"{old.text} [已解除同步]" if old.attachments else ""
                    self.replace_line_text(old_idx, replacement)
            elif tag == "insert":
                for new_idx in range(j1, j2):
                    self.append_line(new_lines[new_idx])

    def render(self) -> str:
        result: List[str] = []
        insert_at = len(self.tokens)
        for idx in range(len(self.tokens) - 1, -1, -1):
            if self.tokens[idx].kind == "end" and self.tokens[idx].tag in {"body", "html"}:
                insert_at = idx
                break
        for idx, token in enumerate(self.tokens):
            if idx == insert_at:
                result.extend(self._insert_before_end)
            result.append(self._replacements.get(idx, token.raw))
            result.extend(self._suffixes.get(idx, []))
        if insert_at == len(self.tokens):
            result.extend(self._insert_before_end)
        return "".join(result)


@dataclass
class NoteSnapshot:
    note_id: str
    name: str
    plaintext: str
    html_body: str
    modification_date: str
    attachments: List[AttachmentSnapshot] = field(default_factory=list)
    document: NoteHTMLDocument = field(init=False)

    def __post_init__(self) -> None:
        self.document = NoteHTMLDocument(self.html_body)
        self.document.bind_attachments(self.attachments)

    @property
    def content_lines(self) -> List[str]:
        if self.attachments:
            return [line.text for line in self.document.lines]
        return self.plaintext.splitlines()

    @property
    def attachment_signature(self) -> set[Tuple[str, str]]:
        return {(item.attachment_id, item.cid_key) for item in self.attachments}


class AttachmentStateStore:
    def __init__(self, path: str):
        self.path = path
        self.data: Dict[str, object] = {"version": 1, "notes": {}}
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                self.data = loaded
                self.data.setdefault("notes", {})
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".attachment-state-", dir=os.path.dirname(self.path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def update_snapshot(self, snapshot: NoteSnapshot) -> None:
        notes = self.data.setdefault("notes", {})
        note_entry = notes.setdefault(snapshot.note_id, {})
        note_entry["name"] = snapshot.name
        note_entry["updated_at"] = datetime.now().astimezone().isoformat()
        note_entry["attachments"] = {
            item.attachment_id: {
                "cid": item.content_id,
                "name": item.name,
                "sha256": item.sha256,
                "obsidian_path": item.obsidian_path,
                "bound_line": next(
                    (line.fingerprint for line in snapshot.document.lines if item in line.attachments),
                    None,
                ),
            }
            for item in snapshot.attachments
        }

    def mapping_changed(self, snapshot: NoteSnapshot) -> bool:
        notes = self.data.get("notes", {})
        note_entry = notes.get(snapshot.note_id, {}) if isinstance(notes, dict) else {}
        saved = note_entry.get("attachments", {}) if isinstance(note_entry, dict) else {}
        previous = {
            key: value.get("bound_line")
            for key, value in saved.items()
            if isinstance(value, dict)
        } if isinstance(saved, dict) else {}
        current = {
            item.attachment_id: next(
                (line.fingerprint for line in snapshot.document.lines if item in line.attachments),
                None,
            )
            for item in snapshot.attachments
        }
        return previous != current

    def archive_removed(self, snapshot: NoteSnapshot, vault_root: str, relative_attachment_dir: str) -> None:
        notes = self.data.get("notes", {})
        note_entry = notes.get(snapshot.note_id, {}) if isinstance(notes, dict) else {}
        saved = note_entry.get("attachments", {}) if isinstance(note_entry, dict) else {}
        current_ids = {item.attachment_id for item in snapshot.attachments}
        if not isinstance(saved, dict):
            return
        orphan_dir = os.path.join(vault_root, relative_attachment_dir, "AppleNotes", ".orphaned")
        for attachment_id, record in saved.items():
            if attachment_id in current_ids or not isinstance(record, dict):
                continue
            rel_path = record.get("obsidian_path")
            if not rel_path:
                continue
            source = os.path.join(vault_root, rel_path)
            if not os.path.isfile(source):
                continue
            os.makedirs(orphan_dir, exist_ok=True)
            target = os.path.join(orphan_dir, os.path.basename(source))
            if os.path.exists(target):
                stem, ext = os.path.splitext(target)
                target = f"{stem}-{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
            os.replace(source, target)

    def hydrate_snapshot(self, snapshot: NoteSnapshot, vault_root: str) -> None:
        notes = self.data.get("notes", {})
        note_entry = notes.get(snapshot.note_id, {}) if isinstance(notes, dict) else {}
        saved = note_entry.get("attachments", {}) if isinstance(note_entry, dict) else {}
        if not isinstance(saved, dict):
            return
        for item in snapshot.attachments:
            record = saved.get(item.attachment_id)
            if not isinstance(record, dict):
                continue
            rel_path = record.get("obsidian_path")
            digest = record.get("sha256")
            if rel_path and digest and os.path.isfile(os.path.join(vault_root, rel_path)):
                item.obsidian_path = rel_path
                item.sha256 = digest


class AttachmentExporter:
    def __init__(
        self,
        vault_root: str,
        relative_attachment_dir: str,
        save_attachment: Callable[[str, str, str], bool],
    ):
        self.vault_root = vault_root
        self.relative_attachment_dir = relative_attachment_dir
        self.save_attachment = save_attachment

    @staticmethod
    def _safe_filename(value: str) -> str:
        value = os.path.basename(value or "attachment")
        value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", value).strip(" .")
        return value or "attachment"

    @staticmethod
    def _file_sha256(path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def export_all(self, snapshot: NoteSnapshot, target_date: date) -> bool:
        if not snapshot.attachments:
            return True
        relative_dir = os.path.join(
            self.relative_attachment_dir,
            "AppleNotes",
            target_date.strftime("%Y-%m-%d"),
        )
        absolute_dir = os.path.join(self.vault_root, relative_dir)
        os.makedirs(absolute_dir, exist_ok=True)

        for attachment in snapshot.attachments:
            if attachment.obsidian_path and attachment.sha256:
                existing = os.path.join(self.vault_root, attachment.obsidian_path)
                if os.path.isfile(existing) and self._file_sha256(existing) == attachment.sha256:
                    continue
            prefix = hashlib.sha256(attachment.attachment_id.encode("utf-8")).hexdigest()[:12]
            filename = f"{prefix}-{self._safe_filename(attachment.name)}"
            target_path = os.path.join(absolute_dir, filename)
            fd, temp_path = tempfile.mkstemp(prefix=".notes-attachment-", dir=absolute_dir)
            os.close(fd)
            try:
                os.unlink(temp_path)
                if not self.save_attachment(snapshot.note_id, attachment.attachment_id, temp_path):
                    return False
                if not os.path.isfile(temp_path) or os.path.getsize(temp_path) <= 0:
                    return False
                digest = self._file_sha256(temp_path)
                if os.path.exists(target_path) and self._file_sha256(target_path) == digest:
                    os.unlink(temp_path)
                else:
                    os.replace(temp_path, target_path)
                attachment.sha256 = digest
                attachment.obsidian_path = os.path.relpath(target_path, self.vault_root).replace(os.sep, "/")
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        return True


def render_attachment_links(attachments: Iterable[AttachmentSnapshot], suffix: str = "|L|200") -> str:
    links = []
    for attachment in attachments:
        if attachment.obsidian_path:
            links.append(f"![[{attachment.obsidian_path}{suffix}]]")
    return " ".join(links)
