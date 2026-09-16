from __future__ import annotations

import json
import hashlib
import os
import tempfile
from collections import Counter
from datetime import date, datetime
from typing import Optional, Tuple

try:
    from .note_attachments import AttachmentExporter, AttachmentStateStore, NoteSnapshot
except ImportError:
    from note_attachments import AttachmentExporter, AttachmentStateStore, NoteSnapshot


class NoteAttachmentTransaction:
    def __init__(self, reader, config, logger=print):
        self.reader = reader
        self.config = config
        self.log = logger
        self.state = AttachmentStateStore(config.APPLE_NOTES_ATTACHMENT_STATE_FILE)
        self.exporter = AttachmentExporter(
            config.VAULT_ROOT,
            config.REL_ATTACHMENT_DIR,
            reader.save_attachment,
        )
        self.blocked_note_ids = set()
        self.mapping_changed = False

    def prepare(self, snapshot: NoteSnapshot, target_date: date) -> bool:
        if snapshot.note_id in self.blocked_note_ids:
            self.log(f"⛔ [Notes附件] 已阻止该备忘录继续写入: {snapshot.name}")
            return False
        self.mapping_changed = self.state.mapping_changed(snapshot)
        self.state.hydrate_snapshot(snapshot, self.config.VAULT_ROOT)
        if not self.exporter.export_all(snapshot, target_date):
            self.log("⛔ [Notes附件] 附件导出或校验失败，本轮禁止重写备忘录")
            return False
        self.state.archive_removed(snapshot, self.config.VAULT_ROOT, self.config.REL_ATTACHMENT_DIR)
        self.state.update_snapshot(snapshot)
        self.state.save()
        return True

    def _write_recovery(self, snapshot: NoteSnapshot, reason: str) -> str:
        note_key = snapshot.note_id.encode("utf-8").hex()[:32]
        recovery_dir = os.path.join(self.config.APPLE_NOTES_RECOVERY_DIR, note_key)
        os.makedirs(recovery_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        html_path = os.path.join(recovery_dir, f"{timestamp}.html")
        meta_path = os.path.join(recovery_dir, f"{timestamp}.json")
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(snapshot.html_body)
        with open(meta_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "reason": reason,
                    "note_id": snapshot.note_id,
                    "name": snapshot.name,
                    "modification_date": snapshot.modification_date,
                    "attachments": [
                        {
                            "id": item.attachment_id,
                            "cid": item.content_id,
                            "path": item.obsidian_path,
                            "sha256": item.sha256,
                        }
                        for item in snapshot.attachments
                    ],
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
        return html_path

    def _restore_missing_files(self, before: NoteSnapshot, after: Optional[NoteSnapshot]) -> None:
        existing_ids = {item.attachment_id for item in after.attachments} if after else set()
        for attachment in before.attachments:
            if attachment.attachment_id in existing_ids or not attachment.obsidian_path:
                continue
            source = os.path.join(self.config.VAULT_ROOT, attachment.obsidian_path)
            if os.path.isfile(source):
                self.reader.add_attachment(before.note_id, source)

    @staticmethod
    def _sha256(path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _verify_attachment_bytes(self, before: NoteSnapshot, after: NoteSnapshot) -> bool:
        expected = Counter(item.sha256 for item in before.attachments if item.sha256)
        if len(expected) == 0 and before.attachments:
            return False
        actual = Counter()
        with tempfile.TemporaryDirectory(prefix="notes-verify-") as directory:
            for index, attachment in enumerate(after.attachments):
                path = os.path.join(directory, f"attachment-{index}")
                if not self.reader.save_attachment(after.note_id, attachment.attachment_id, path):
                    return False
                if not os.path.isfile(path) or os.path.getsize(path) <= 0:
                    return False
                digest = self._sha256(path)
                actual[digest] += 1
                old = next((item for item in before.attachments if item.sha256 == digest), None)
                if old:
                    attachment.sha256 = digest
                    attachment.obsidian_path = old.obsidian_path
        return actual == expected

    def write_html(self, snapshot: NoteSnapshot, new_html: str) -> Tuple[bool, Optional[NoteSnapshot]]:
        if snapshot.attachments and not all(item.obsidian_path and item.sha256 for item in snapshot.attachments):
            self.log("⛔ [Notes附件] 写入前附件尚未完整落盘")
            return False, snapshot
        if snapshot.attachments:
            recovery_path = self._write_recovery(snapshot, "blocked-unsafe-notes-body-write")
            self.log(
                "🛡️ [Notes附件] 当前 macOS 实测 set body 会移除正文图片，"
                f"已跳过整篇回写；附件和原始 HTML 已备份: {recovery_path}"
            )
            return False, snapshot
        recovery_path = self._write_recovery(snapshot, "pre-write")
        ok, after, error = self.reader.update_note_html(
            snapshot.note_id,
            new_html,
            expected_modification_date=snapshot.modification_date,
        )
        if ok:
            if snapshot.attachments and after and not self._verify_attachment_bytes(snapshot, after):
                ok = False
                error = "ATTACHMENT_CONTENT_MISMATCH"
            else:
                if after:
                    for current in after.attachments:
                        old = next((item for item in snapshot.attachments if item.sha256 == current.sha256), None)
                        if old:
                            current.obsidian_path = old.obsidian_path
                    self.state.update_snapshot(after)
                    self.state.save()
                return True, after

        if error == "CONCURRENT_MODIFICATION":
            self.log("↪️ [Notes附件] 用户同时修改了备忘录，取消本轮写入并等待重试")
            return False, after

        self._restore_missing_files(snapshot, after)
        self.blocked_note_ids.add(snapshot.note_id)
        self._write_recovery(snapshot, error or "unknown-write-failure")
        self.log(f"⛔ [Notes附件] 写后校验失败 ({error})，已尝试恢复并封锁后续写入；恢复文件: {recovery_path}")
        return False, after
