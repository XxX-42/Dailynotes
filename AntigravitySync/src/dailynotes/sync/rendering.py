import re
import random
import string
import datetime
import unicodedata
from ..utils import Logger
from .parsing import clean_task_text, get_indent_depth

def normalize_raw_tasks(lines, filename_stem):
    if not lines or not filename_stem: return lines

    new_lines = []
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    raw_pattern = re.compile(r'^(>\s*-\s*\[\s*\])(.*)$')
    id_pattern = re.compile(r'\^[a-z0-9]{6}\s*$')

    def generate_id():
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    for line in lines:
        match = raw_pattern.match(line)
        if match:
            prefix = match.group(1)
            text_body = match.group(2).strip()

            if not id_pattern.search(text_body):
                new_id = generate_id()
                formatted_body = f"[[{filename_stem}#^{new_id}|⮐]] [[{today_str}]]"
                if text_body:
                    formatted_body += f" {text_body}"
                new_lines.append(f"{prefix} {formatted_body} ^{new_id}")
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
    """
    [v14.5 Indent-Aware Injection]
    修复 inject 逻辑误将缩进的子任务 (- [ ]) 识别为新 Block 导致的截断问题。
    现在只有【顶层任务】(缩进 < 2 空格) 才会触发分块。
    """
    # --- 1. 定位锚点 ---
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(file_lines):
        if line.strip() == '# Tasks': start_idx = i; break

    if start_idx != -1:
        for i in range(start_idx + 1, len(file_lines)):
            curr_line = file_lines[i].strip()
            if curr_line == '----------': end_idx = i; break
        if end_idx <= start_idx: end_idx = -1

    # --- 2. 自愈结构 ---
    need_scaffold = False
    if start_idx == -1:
        need_scaffold = True
        file_lines = [l for l in file_lines if l.strip() not in ('# Tasks', '----------')]
    elif end_idx == -1:
        file_lines.append("\n----------\n")
        end_idx = len(file_lines) - 1
    elif end_idx < start_idx:
        need_scaffold = True
        file_lines = [l for l in file_lines if l.strip() not in ('# Tasks', '----------')]

    if need_scaffold:
        insert_pos = 0
        if file_lines and file_lines[0].strip() == '---':
            for i in range(1, len(file_lines)):
                if file_lines[i].strip() == '---': insert_pos = i + 1; break
        scaffold = ["\n", "# Tasks\n", "\n", "----------\n"]
        file_lines[insert_pos:insert_pos] = scaffold
        start_idx = insert_pos + 1
        end_idx = insert_pos + 3

    # --- 3. 提取现有内容 ---
    existing_content = file_lines[start_idx + 1: end_idx]
    existing_structure_map = {}
    current_header_date = None
    header_pattern = re.compile(r'^#+\s*\[\[\s*(\d{4}-\d{2}-\d{2})\s*\]\]')
    id_pattern = re.compile(r'\^([a-zA-Z0-9]{6,})\s*$')

    for line in existing_content:
        stripped = line.strip()
        h_m = header_pattern.match(stripped)
        if h_m: current_header_date = h_m.group(1); continue
        if stripped.startswith('- ['):
            bid_m = id_pattern.search(stripped)
            if bid_m and current_header_date:
                existing_structure_map[bid_m.group(1)] = current_header_date

    # --- 4. 合并与分组 ---
    candidates = existing_content + block_lines
    blocks = []
    current_block = []
    date_pattern = re.compile(r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\||\]\])')

    def flush_block(blk_lines):
        if not blk_lines: return
        head = blk_lines[0]
        bid_m = id_pattern.search(head)
        if bid_m:
            bid = bid_m.group(1)
            final_date = "0000-00-00"
            if bid in existing_structure_map:
                final_date = existing_structure_map[bid]
            else:
                date_m = date_pattern.search(head)
                if date_m: final_date = date_m.group(1)
            blocks.append({'id': bid, 'date': final_date, 'lines': blk_lines})

    for line in candidates:
        s_line = line.strip()
        if not s_line: continue
        if s_line == '-----': continue
        if s_line == '----------': continue

        # 处理标题行：强制分块
        if s_line.startswith('#'):
            flush_block(current_block);
            current_block = [];
            continue

        # 处理任务行：增加缩进检测
        if s_line.startswith('- ['):
            # [关键修复] 计算原始缩进深度
            # 不使用 .strip() 后的 s_line，而是使用原始 line
            # 只有缩进非常浅 (小于2个空格或半个Tab) 的才视为新 Block
            # 这样可以保护缩进的子任务 (		- [ ]) 不被拆分

            # 简单计算前导空白长度 (Tab算1个字符，但在startswith逻辑下足够区分顶层)
            raw_indent_len = len(line) - len(line.lstrip())

            # 如果是顶层任务 (Indent 0 or 1 space/tab usually 0)
            # 使用更宽松的阈值：比如 < 2。
            # 注意：如果您的顶层任务也有缩进，这里需要调整。通常顶层任务是贴边的。
            is_toplevel = (raw_indent_len < 2)

            if is_toplevel:
                flush_block(current_block)
                current_block = [line]
            else:
                # 是子任务，加入当前块
                if current_block:
                    current_block.append(line)
                # 如果没有 current_block (即孤儿缩进任务)，暂且作为新块（虽然不合规范）
                else:
                    current_block = [line]
        else:
            # 纯文本或其他内容，归属当前块
            if current_block: current_block.append(line)

    flush_block(current_block)

    # --- 5. 分组与排序 ---
    unique_map = {}
    for b in blocks: unique_map[b['id']] = b
    date_groups = {}
    for b in unique_map.values():
        d = b['date']
        if d not in date_groups: date_groups[d] = []
        date_groups[d].append(b)

    # [SORTING] 执行绝对排序
    for date_key, group_blocks in date_groups.items():
        group_blocks.sort(key=_calculate_sort_key)

    # --- 6. 构建输出 ---
    output_lines = []
    sorted_dates = sorted(date_groups.keys(), reverse=True)
    for d in sorted_dates:
        group_blocks = date_groups[d]
        if d and d != "0000-00-00":
            if output_lines: output_lines.append("\n")
            output_lines.append(f"## [[{d}]]\n")
            output_lines.append("\n")
        elif output_lines:
            output_lines.append("\n")
        for b in group_blocks:
            output_lines.extend(b['lines'])
            if output_lines and not output_lines[-1].endswith('\n'):
                output_lines[-1] += '\n'

    section_body = ["\n"] + output_lines + ["\n"]

    # --- [FIX] 移除内部判断，总是应用变更到 list ---
    file_lines[start_idx + 1: end_idx] = section_body
    return file_lines

def aggressive_daily_clean(lines: list) -> list:
    if not lines: return []

    footer_idx = len(lines)
    for i, line in enumerate(lines):
        if line.strip().startswith('# Day planner') or line.strip().startswith('# Journey'):
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
        link = f"[[{fname}#^{bid}|⮐]]"
        time_match = re.match(r'^(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)', text)
        if time_match:
            time_part = time_match.group(1)
            rest_part = text[len(time_part):].strip()
            return f"{indent_str}- [{status}] {time_part} {link} {rest_part} ^{bid}\n"
        else:
            return f"{indent_str}- [{status}] {link} {text} ^{bid}\n"
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

        parts = [date_link]
        if clean_text: parts.append(clean_text)
        if meta_str: parts.append(meta_str)
        parts.append(f"^{bid}")

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
        content_cleaned = re.sub(r'^[>\s]+', '', line).strip()
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

def reconstruct_daily_block(sd, target_date):
    fname = sd['fname']
    bid = sd['bid']
    status = sd['status']
    text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}\]\]', '', sd['pure']).strip()
    link_tag = f"[[{fname}]]"
    if link_tag not in text: text = f"{link_tag} {text}"

    # 传递 sd['indent'] 作为 source_parent_indent
    parent_line = format_line(sd['indent'], status, text, "", fname, bid, True)
    children = normalize_child_lines(
        sd['raw'][1:],
        target_parent_indent=sd['indent'],
        source_parent_indent=sd['indent'],
        as_quoted=False
    )
    return [parent_line] + children

def ensure_structure(lines):
    has_dp = any(l.strip() == "# Day planner" for l in lines)
    j_idx = -1
    try:
        j_idx = next(i for i, l in enumerate(lines) if l.strip() == "# Journey")
    except StopIteration:
        pass
    if not has_dp:
        if j_idx != -1:
            lines.insert(j_idx, "# Day planner\n\n")
        else:
            lines.insert(0, "# Day planner\n\n");
            lines.append("\n# Journey\n")
    if has_dp and j_idx == -1: lines.append("\n# Journey\n")
    return lines

def cleanup_empty_headers(lines, date_tag):
    lines = ensure_structure(lines)
    cleaned_lines = []
    i = 0
    modified = False
    current_section = None
    target_sections = ['# Day planner', '# Journey']
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
