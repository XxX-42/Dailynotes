from __future__ import annotations

import re
from typing import Dict, List, Tuple


def _cfg(config, attr_name: str, default_value: str) -> str:
    return getattr(config, attr_name, default_value) if config else default_value


def _ensure_nl(line: str) -> str:
    return line if line.endswith("\n") else line + "\n"


def _repair_wiki_link_escapes(line: str) -> str:
    """
    Obsidian 笔记里偶发会把 wiki link 内的 `_`、`|` 等字符写成 markdown 转义。
    这里仅在 `[[...]]` 内做定向反转义，避免污染普通代码/正文。
    """
    if "[[" not in line or "\\" not in line:
        return line

    has_nl = line.endswith("\n")
    body = line[:-1] if has_nl else line

    def _repair(match: re.Match[str]) -> str:
        inner = match.group(1)
        repaired = re.sub(r'\\([_|[\]])', r'\1', inner)
        return f"[[{repaired}]]"

    repaired_body = re.sub(r'\[\[(.*?)\]\]', _repair, body)
    return repaired_body + ("\n" if has_nl else "")


def _strip_blank_edges(lines: List[str]) -> List[str]:
    out = list(lines)
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def _split_top_sections(lines: List[str]) -> Tuple[List[str], List[Tuple[str, List[str]]]]:
    preamble: List[str] = []
    sections: List[Tuple[str, List[str]]] = []
    current_header = None
    current_body: List[str] = []

    for line in lines:
        if line.startswith("# "):
            if current_header is None:
                current_header = line.strip()
                current_body = []
            else:
                sections.append((current_header, current_body))
                current_header = line.strip()
                current_body = []
        else:
            if current_header is None:
                preamble.append(line)
            else:
                current_body.append(line)

    if current_header is not None:
        sections.append((current_header, current_body))

    return preamble, sections


def _extract_legacy_subsections(
    body_lines: List[str],
    targets: Dict[str, List[str]],
) -> Tuple[List[str], Dict[str, List[List[str]]]]:
    remaining: List[str] = []
    captured: Dict[str, List[List[str]]] = {key: [] for key in targets}
    i = 0

    while i < len(body_lines):
        stripped = body_lines[i].strip()
        matched_key = None
        for canonical_header, legacy_headers in targets.items():
            if stripped in legacy_headers:
                matched_key = canonical_header
                break

        if matched_key is None:
            remaining.append(body_lines[i])
            i += 1
            continue

        i += 1
        chunk: List[str] = []
        while i < len(body_lines):
            next_stripped = body_lines[i].strip()
            if body_lines[i].startswith("# ") or next_stripped.startswith("## "):
                break
            chunk.append(body_lines[i])
            i += 1
        captured[matched_key].append(chunk)

    return remaining, captured


def _merge_chunks(chunks: List[List[str]]) -> List[str]:
    merged: List[str] = []
    for chunk in chunks:
        trimmed = _strip_blank_edges(chunk)
        if not trimmed:
            continue
        if merged and merged[-1].strip():
            merged.append("\n")
        merged.extend(_ensure_nl(line) for line in trimmed)
    while merged and not merged[-1].strip():
        merged.pop()
    return merged


def normalize_daily_note_lines(lines: List[str], config) -> List[str]:
    lines = [_repair_wiki_link_escapes(_ensure_nl(line)) for line in lines]

    deployment = _cfg(config, "DEPLOYMENT_HEADER", "# Deployment 🚀")
    thinking = _cfg(config, "THINKING_HEADER", "# Thinking 🧠")
    takein = _cfg(config, "TAKEIN_HEADER", "# Takein 🍱")
    exercice = _cfg(config, "EXERCICE_HEADER", "# Exercice 🏋️")
    economic = _cfg(config, "ECONOMIC_HEADER", "# Economic 📈")
    canonical_headers = [deployment, thinking, takein, exercice, economic]

    preamble, top_sections = _split_top_sections(lines)

    second_level_legacy = {
        thinking: ["## Insights"],
        takein: ["## #takein"],
        exercice: ["## #exercice"],
        economic: ["## #account"],
    }
    deployment_headers = {deployment, "# Deployment", "# Day planner", "# Journey"}

    canonical_chunks: Dict[str, List[List[str]]] = {header: [] for header in canonical_headers}
    extra_sections: List[Tuple[str, List[str]]] = []

    for header, body in top_sections:
        remaining_body, extracted = _extract_legacy_subsections(body, second_level_legacy)
        for target_header, chunks in extracted.items():
            for chunk in chunks:
                trimmed = _strip_blank_edges(chunk)
                if trimmed:
                    canonical_chunks[target_header].append(trimmed)

        trimmed_remaining = _strip_blank_edges(remaining_body)

        if header in deployment_headers:
            if trimmed_remaining:
                canonical_chunks[deployment].append(trimmed_remaining)
        elif header in canonical_chunks:
            if trimmed_remaining:
                canonical_chunks[header].append(trimmed_remaining)
        elif header == "# Log":
            if trimmed_remaining:
                extra_sections.append((header, trimmed_remaining))
        else:
            if trimmed_remaining:
                extra_sections.append((header, trimmed_remaining))

    normalized: List[str] = list(preamble)
    if normalized and normalized[-1].strip():
        normalized.append("\n")

    for header in canonical_headers:
        normalized.append(_ensure_nl(header))
        body = _merge_chunks(canonical_chunks[header])
        if body:
            normalized.append("\n")
            normalized.extend(body)
            normalized.append("\n")
        else:
            normalized.append("\n")

    for header, body in extra_sections:
        normalized.append(_ensure_nl(header))
        normalized.append("\n")
        normalized.extend(_ensure_nl(line) for line in body)
        normalized.append("\n")

    return normalized


def find_daily_section(
    lines: List[str],
    primary_header: str,
    legacy_headers: List[str] | None = None,
) -> Tuple[int, int, int, str | None]:
    legacy_headers = legacy_headers or []
    targets = [primary_header] + legacy_headers
    normalized_targets = {h.strip().lower(): h for h in targets}

    header_idx = -1
    matched_header = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower() in normalized_targets:
            header_idx = i
            matched_header = stripped
            break

    if header_idx == -1:
        return -1, -1, -1, None

    start_idx = header_idx + 1
    is_legacy = matched_header != primary_header
    end_idx = len(lines)
    for i in range(start_idx, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("# "):
            end_idx = i
            break
        if is_legacy and stripped.startswith("## "):
            end_idx = i
            break

    return header_idx, start_idx, end_idx, matched_header
