import re
import random
import string
import datetime
import unicodedata
from config import Config
from ..utils import Logger
from .parsing import clean_task_text, get_indent_depth

def normalize_raw_tasks(lines, filename_stem):
    if not lines or not filename_stem: return lines

    new_lines = []
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    raw_pattern = re.compile(r'^(>\s*-\s*\[\s*\])(.*)$')
    id_pattern = re.compile(r'(?:\^[a-z0-9]{6}|<span id="[a-z0-9]{6}"(?: data-timestamps="[^"]*")?></span>)\s*$')

    def generate_id():
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    for line in lines:
        match = raw_pattern.match(line)
        if match:
            prefix = match.group(1)
            text_body = match.group(2).strip()

            if not id_pattern.search(text_body):
                new_id = generate_id()
                new_lines.append(f"{prefix} <span id=\"{new_id}\"></span>[[{filename_stem}#^{new_id}|⮐]] [[{today_str}]] {text_body}")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    return new_lines

def maintain_section_integrity(lines):
    cleaned = []
    empty_count = 0
    for line in lines:
        if not line.strip():
            empty_count += 1
            if empty_count <= 1:
                cleaned.append(line)
        else:
            empty_count = 0
            cleaned.append(line)
    return cleaned

def _calculate_sort_key(block_data):
    """
    [v12.2 Absolute Hybrid Sort]
    绝对排序规则：
    1. 第一梯队：有时间限制的任务 (Time-Blocked) -> 按时间先后 (08:00 < 09:00)
    2. 第二梯队：无时间限制的任务 -> 按 Block ID 字典序 (^aaaa < ^zzzz)
    """
    first_line = block_data['lines'][0].strip()
    block_id = block_data['id']

    # --- 1. 时间提取 ---
    time_match = re.search(r'(\d{1,2}:\d{2})', first_line)

    if time_match:
        has_time = 0
        time_val = time_match.group(1).zfill(5)
    else:
        has_time = 1
        time_val = "99:99"

    return (has_time, time_val, block_id)

def inject_into_task_section(file_lines, block_lines, filename_stem=None):
    """Preserve manual content, upsert managed blocks, and relocate Tasks to EOF."""
    from .task_section import find_task_section, visible_lines, task_id, UnsafeTaskSection

    lines = ''.join(file_lines).splitlines(keepends=True)
    section = find_task_section(lines)
    if section is None and not block_lines:
        return file_lines
    body = lines[section.start + 1:section.end] if section else []
    outside = lines[:section.before] + lines[section.after:] if section else lines
    incoming = ''.join(block_lines).splitlines(keepends=True)
    date_header = re.compile(r'^##+\s*\[\[(\d{4}-\d{2}-\d{2})\]\]')
    date_link = re.compile(r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\||\]\])')

    def blocks(content, incoming=False):
        visible = visible_lines(content)
        result = []
        date = None
        for index, line in enumerate(content):
            if index not in visible:
                continue
            header = date_header.match(line)
            if header:
                date = header[1]
            if not re.match(r'^[ \t]*- \[[ xX]\]', line):
                continue
            bid = task_id(line)
            if not bid:
                continue
            if get_indent_depth(line) >= 2 and not date_link.search(line):
                continue
            end = index + 1
            # Only owned child lines belong to a replaceable block. Standalone
            # prose/blank lines remain at their original position.
            probe = end
            while probe < len(content):
                child = content[probe]
                if not child.strip():
                    probe += 1
                    continue
                if child.strip() and (child.startswith((' ', '\t', '>')) or child.lstrip().startswith('![[')):
                    if task_id(child) and date_link.search(child) and re.match(r'^[ \t]*- \[[ xX]\]', child):
                        break
                    end = probe + 1
                    probe += 1
                else:
                    break
            link = date_link.search(line)
            result.append((index, end, bid, link[1] if link else date))
        if incoming:
            # Incoming data is already a complete task block. A blank line is
            # not its end: keep subsequent child notes, images and fenced code.
            result = [(start, result[i + 1][0] if i + 1 < len(result) else len(content), bid, date)
                      for i, (start, end, bid, date) in enumerate(result)]
        return result

    existing = blocks(body)
    ids = [item[2] for item in existing]
    if len(ids) != len(set(ids)):
        raise UnsafeTaskSection('任务区含重复主键，禁止自动覆盖')
    incoming_blocks = blocks(incoming, incoming=True)
    if incoming and not incoming_blocks:
        raise UnsafeTaskSection('待插入内容没有可识别的任务主键，取消写入')
    incoming_ids = [item[2] for item in incoming_blocks]
    if len(incoming_ids) != len(set(incoming_ids)):
        raise UnsafeTaskSection('待插入任务含重复主键')
    additions = []
    changes = {}
    old_map = {item[2]: item for item in existing}
    for start, end, bid, date in incoming_blocks:
        chunk = incoming[start:end]
        old = old_map.get(bid)
        if old and (not date or date == old[3]):
            changes[old[0]] = (old[1], chunk)
        else:
            if old:
                changes[old[0]] = (old[1], [])
            additions.append((date, chunk))
    merged = []
    index = 0
    while index < len(body):
        if index in changes:
            end, chunk = changes[index]
            merged.extend(chunk)
            index = end
        else:
            merged.append(body[index])
            index += 1
    for date, chunk in additions:
        header_index = next((i for i, line in enumerate(merged)
                             if date_header.match(line) and date_header.match(line)[1] == date), None)
        if header_index is not None:
            insert_at = next((i for i in range(header_index + 1, len(merged))
                              if re.match(r'^#', merged[i])), len(merged))
            merged[insert_at:insert_at] = chunk
        else:
            if merged and not merged[-1].endswith('\n'):
                merged[-1] += '\n'
            if merged and merged[-1].strip():
                merged.append('\n')
            if date:
                merged.extend([f'## [[{date}]]\n', '\n'])
            merged.extend(chunk)

    # Do not trim or reformat manual section content on migration.
    while outside and not outside[-1].strip():
        outside.pop()
    prefix = ''.join(outside)
    if prefix:
        # One newline terminates the body line; the next ten are blank lines.
        prefix = prefix.rstrip('\r\n') + '\n' * 11
    content = ''.join(merged)
    if not content.startswith('\n'):
        content = '\n' + content
    if not content.endswith('\n'):
        content += '\n'
    if content.rstrip('\r\n'):
        content = content.rstrip('\r\n') + '\n\n'
    result = prefix + '----------\n# Tasks\n' + content
    file_lines[:] = result.splitlines(keepends=True)
    return file_lines

def aggressive_daily_clean(lines: list) -> list:
    if not lines: return []

    footer_idx = len(lines)
    for i, line in enumerate(lines):
        if line.strip() in set(Config.TOP_LEVEL_DAILY_HEADERS) | {"# Day planner", "# Journey", "# Deployment"}:
            footer_idx = i
            break

    body = lines[:footer_idx]
    foot = lines[footer_idx:]

    cleaned_body = []
    empty_count = 0
    empty_pattern = re.compile(r'^\s*$')

    for i, line in enumerate(body):
        is_empty = bool(empty_pattern.fullmatch(line))
        if '---' in line: is_empty = False

        if is_empty:
            empty_count += 1
            if empty_count > 2:
                Logger.debug(f"[CLEAN] Removing excess daily line {i + 1}: {repr(line)}")
                continue
            else:
                cleaned_body.append(line)
        else:
            empty_count = 0
            cleaned_body.append(line)

    return cleaned_body + foot

def format_line(indent, status, text, dates, fname, bid, is_daily):
    # indent now represents visual depth (spaces)
    # We can simply output spaces, or convert to tabs if preferred.
    # Assuming we stick to spaces or mix based on indent // 4.
    # For robustness, we will just use indent spaces.
    # But original logic was: tab_count = indent // 4; indent_str = '\t' * tab_count
    # To maintain compatibility with visual depth:
    tab_count = indent // 4
    indent_str = '\t' * tab_count

    if is_daily:
        span_id = f'<span id="{bid}"></span>'
        link = f"[[{fname}#^{bid}|⮐]]"
        time_match = re.match(r'^(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)', text)
        if time_match:
            time_part = time_match.group(1)
            rest_part = text[len(time_part):].strip()
            return f"{indent_str}- [{status}] {time_part} {span_id}{link} {rest_part}\n"
        else:
            return f"{indent_str}- [{status}] {span_id}{link} {text}\n"
    else:
        clean_text = clean_task_text(text, bid, fname)
        creation_date = None
        if dates and re.match(r'^\d{4}-\d{2}-\d{2}$', str(dates).strip()):
            creation_date = str(dates).strip()
        if not creation_date:
            patterns = [
                r'\[\[(\d{4}-\d{2}-\d{2})\]\]',
                r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\|)',
                r'(?:📅|\|📅\]\])\s*(\d{4}-\d{2}-\d{2})'
            ]
            for p in patterns:
                m = re.search(p, str(dates)) or re.search(p, text)
                if m: creation_date = m.group(1); break
        if not creation_date:
            today = datetime.date.today().strftime('%Y-%m-%d')
            if dates:
                Logger.info(f"⚠️ [FORMAT WARNING] 日期解析失败！输入: '{dates}' -> 兜底: '{today}'")
            creation_date = today

        date_link = f"[[{creation_date}#^{bid}|⮐]]"
        processed_dates = []
        done_date_match = re.search(r'✅\s*(\d{4}-\d{2}-\d{2})', str(dates))
        if done_date_match: processed_dates.append(f"✅ {done_date_match.group(1)}")
        meta_str = " ".join(processed_dates)

        span_id = f'<span id="{bid}"></span>'
        parts = [span_id + date_link]
        if clean_text: parts.append(clean_text)
        if meta_str: parts.append(meta_str)

        return f"{indent_str}- [{status}] {' '.join(parts)}\n"

def normalize_child_lines(raw_lines, target_parent_indent, source_parent_indent=None, as_quoted=False):
    """
    [v14.0 Relative Anchor Normalization]
    使用相对偏移量重构子行，完美保留复杂列表结构（图片、引用、多级列表）。

    Args:
        raw_lines: 子行列表 (不包含父行)
        target_parent_indent: 父行在目标文件中的缩进 (int, visual depth)
        source_parent_indent: 父行在源文件中的原始缩进 (int, visual depth)
    """
    if not raw_lines: return []

    # 如果未提供源缩进，尝试从第一行反推（兜底策略）
    if source_parent_indent is None:
        if raw_lines:
            source_parent_indent = max(0, get_indent_depth(raw_lines[0]) - 4)
        else:
            source_parent_indent = 0

    children = []
    for line in raw_lines:
        # [FIX] 使用 lstrip() 而非 strip()，保留尾部空格以支持 Obsidian "- " 列表语法
        content_cleaned = re.sub(r'^[>\s]+', '', line).lstrip()
        if not content_cleaned:
            children.append(("> \n" if as_quoted else "\n"))
            continue

        # 1. 计算当前行相对于“原父级”的偏移量
        current_depth = get_indent_depth(line)
        delta = max(0, current_depth - source_parent_indent)

        # 2. 计算目标缩进
        target_depth = target_parent_indent + delta

        # 3. 转换为缩进字符串 (使用空格更安全，或按需转 Tab)
        # 这里统一使用 Space 确保层级准确，后续 format_line 若用 Tab 可能需要转换，
        # 但通常子内容可以保持 Space。如果必须 Tab，可以用 '\t' * (target_depth // 4)
        indent_str = ' ' * target_depth

        final = f"{indent_str}{content_cleaned}"
        if as_quoted: final = f"> {final}"
        children.append(final + "\n")

    return children

def reconstruct_daily_block(sd, target_date, preserved_time=None):
    fname = sd['fname']
    bid = sd['bid']
    status = sd['status']
    text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}\]\]', '', sd['pure']).strip()
    text = clean_task_text(text, bid, fname)

    # [FIX] 如果传入了保留的时间，将其注入到 text 前端供 format_line 识别
    if preserved_time:
        text = f"{preserved_time} {text}"

    parent_line = format_line(sd['indent'], status, text, "", fname, bid, True)
    children = normalize_child_lines(
        sd['raw'][1:],
        target_parent_indent=sd['indent'],
        source_parent_indent=sd['indent'],
        as_quoted=False
    )
    return [parent_line] + children

def ensure_structure(lines):
    existing_headers = {l.strip() for l in lines if l.strip().startswith('# ')}
    missing_headers = [h for h in Config.TOP_LEVEL_DAILY_HEADERS if h not in existing_headers]
    if missing_headers:
        insert_pos = 0
        if lines and lines[0].strip() == '---':
            for i in range(1, len(lines)):
                if lines[i].strip() == '---':
                    insert_pos = i + 1
                    break
        scaffold = []
        for header in missing_headers:
            scaffold.extend([header + "\n", "\n"])
        lines[insert_pos:insert_pos] = scaffold

    return lines

def cleanup_empty_headers(lines, date_tag):
    lines = ensure_structure(lines)
    cleaned_lines = []
    i = 0
    modified = False
    current_section = None
    target_sections = [Config.DEPLOYMENT_HEADER]
    while i < len(lines):
        line = lines[i]
        s_line = line.strip()
        if s_line.startswith('# '):
            current_section = s_line;
            cleaned_lines.append(line);
            i += 1;
            continue
        if current_section not in target_sections:
            cleaned_lines.append(line);
            i += 1;
            continue
        if s_line.startswith('## '):
            has_content = False
            j = i + 1
            while j < len(lines):
                next_s = lines[j].strip()
                if next_s.startswith('# ') or next_s.startswith('## ') or next_s == '----------': break
                if next_s: has_content = True; break
                j += 1
            if not has_content:
                modified = True;
                i = j
            else:
                cleaned_lines.append(line);
                i += 1
        else:
            cleaned_lines.append(line);
            i += 1
    return cleaned_lines, modified
