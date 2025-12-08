import os
import re
import random
import string
import unicodedata
import datetime
import threading
import time
from typing import Dict, List, Optional, Any, Set
from config import Config
from utils import Logger, FileUtils


class SyncCore:
    def __init__(self, state_manager):
        self.sm = state_manager
        self.project_map = {}
        self.project_path_map = {}
        self.file_path_map = {}

    def trigger_delayed_verification(self, filepath, delay=10):
        def _job():
            time.sleep(delay)
            content = FileUtils.read_file(filepath) or []
            Logger.debug_block(f"VERIFICATION (T+{delay}s) Snapshot: {os.path.basename(filepath)}", content)

        t = threading.Thread(target=_job, daemon=True)
        t.start()

    def generate_block_id(self):
        return '^' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    def parse_yaml_tags(self, lines):
        tags = []
        if not lines or lines[0].strip() != '---': return []
        in_yaml = False
        for i, line in enumerate(lines):
            if i == 0: in_yaml = True; continue
            if line.strip() == '---': break
            if in_yaml and ('tags:' in line or 'main' in line):
                if re.search(r'\bmain\b', line): tags.append('main')
        return tags

    def clean_task_text(self, line, block_id=None, context_name=None):
        """
        [v10.7 Aggressive Clean]
        增加通用尾部清理，防止救援模式下残缺 ID (如 ^04cn) 未被清除导致 ID 重复。
        """
        # 1. 移除 Checkbox
        line = re.sub(r'^\s*-\s*\[.\]\s?', '', line)
        clean_text = line

        # 2. 移除指定块 ID (安全移除)
        if block_id:
            clean_text = re.sub(rf'(?<=\s)\^{re.escape(block_id)}\s*$', '', clean_text)

        # 3. [关键修改] 通用尾部清理 (暴力清洗)
        # 无论 block_id 是否匹配，只要行尾有 " ^..." 形式的残余，一律视为 ID 垃圾清除
        clean_text = re.sub(r'\s+\^[a-zA-Z0-9]*$', '', clean_text)

        # 4. 移除日期链接 [[YYYY-MM-DD...]]
        clean_text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}(?:#\^[a-zA-Z0-9]+)?(?:\|.*?)?\]\]', '', clean_text)

        # 5. 移除文件自身链接 [[Filename...]]
        if context_name:
            clean_text = re.sub(rf'\[\[{re.escape(context_name)}(?:#\^[a-zA-Z0-9]+)?(?:\|.*?)?\]\]', '', clean_text)

        # 6. 移除 Emoji 日期
        clean_text = re.sub(r'[📅✅]\s*\d{4}-\d{2}-\d{2}', '', clean_text)
        clean_text = re.sub(r'\(connect::.*?\)', '', clean_text)

        return clean_text.strip()

    def normalize_block_content(self, block_lines):
        normalized = []
        for line in block_lines:
            clean = re.sub(r'^[\s>]+', '', line).strip()
            if not clean or clean in ['-', '- ']: continue
            normalized.append(clean)
        return "\n".join(normalized) + "\n"

    def extract_routing_target(self, line):
        clean = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', line)
        matches = re.findall(r'\[\[(.*?)\]\]', clean)
        for match in matches:
            pot = match.split('|')[0]
            pot = unicodedata.normalize('NFC', pot)
            if pot in self.file_path_map: return self.file_path_map[pot]
        return None

    def capture_block(self, lines, start_idx):
        if start_idx >= len(lines): return [], 0

        def get_indent(s):
            no_quote = re.sub(r'^>\s?', '', s)
            return len(no_quote) - len(no_quote.lstrip())

        base_indent = get_indent(lines[start_idx])
        block = [lines[start_idx]]
        consumed = 1
        j = start_idx + 1

        while j < len(lines):
            nl = lines[j]

            if nl.strip() == '----------':
                break

            # 粘连标题切分
            split_match = re.search(r'^(.*?)([ \t]*#\s.*)$', nl)
            if split_match and split_match.group(1).strip():
                clean_text = split_match.group(1).rstrip()
                header_part = split_match.group(2).strip()
                lines[j] = clean_text
                lines.insert(j + 1, header_part)
                nl = lines[j]

            if nl.lstrip().startswith('#'): break

            stripped_check = re.sub(r'^[>\s]+', '', nl)
            if stripped_check.startswith('#'): break
            if stripped_check.startswith('---'): break

            if nl.strip() == "":
                block.append(nl);
                consumed += 1;
                j += 1;
                continue

            if get_indent(nl) > base_indent:
                block.append(nl);
                consumed += 1;
                j += 1
            else:
                break

        return block, consumed

    def normalize_raw_tasks(self, lines, filename_stem):
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

    def maintain_section_integrity(self, lines):
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

    def inject_into_task_section(self, file_lines, block_lines, filename_stem=None):
        """
        [v10.3 Nuclear Clean]
        1. 修复了死循环问题。
        2. [核打击] 在重组阶段，凡是以 '#' 开头的行（旧标题），一律强制丢弃。
           防止旧标题被误判为任务描述而残留，彻底根治“标题重影”。
        """
        # --- 1. 定位锚点 ---
        start_idx = -1
        end_idx = -1

        for i, line in enumerate(file_lines):
            if line.strip() == '# Tasks':
                start_idx = i
                break

        if start_idx != -1:
            for i in range(start_idx + 1, len(file_lines)):
                curr_line = file_lines[i].strip()
                if curr_line == '----------':
                    end_idx = i
                    break

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
                    if file_lines[i].strip() == '---':
                        insert_pos = i + 1
                        break
            scaffold = ["\n", "# Tasks\n", "\n", "----------\n"]
            file_lines[insert_pos:insert_pos] = scaffold
            start_idx = insert_pos + 1
            end_idx = insert_pos + 3

        # --- 3. 提取现有内容与归属 ---
        existing_content = file_lines[start_idx + 1: end_idx]
        existing_structure_map = {}
        current_header_date = None

        id_pattern = re.compile(r'\^([a-zA-Z0-9]{6,})\s*$')
        # 宽松正则用于上下文识别
        header_pattern = re.compile(r'^#+\s*\[\[\s*(\d{4}-\d{2}-\d{2})\s*\]\]')

        for line in existing_content:
            stripped = line.strip()
            h_m = header_pattern.match(stripped)
            if h_m:
                current_header_date = h_m.group(1)
                continue

            if stripped.startswith('- ['):
                bid_m = id_pattern.search(stripped)
                if bid_m and current_header_date:
                    existing_structure_map[bid_m.group(1)] = current_header_date

        # --- 4. 任务处理循环 ---
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
                    if date_m:
                        final_date = date_m.group(1)

                blocks.append({'id': bid, 'date': final_date, 'lines': blk_lines})

        for line in candidates:
            s_line = line.strip()
            if not s_line: continue
            if s_line == '-----': continue
            if s_line == '----------': continue

            # [CRITICAL FIX] 核打击逻辑
            if s_line.startswith('#'):
                flush_block(current_block)
                current_block = []
                continue

            if s_line.startswith('- ['):
                flush_block(current_block)
                current_block = [line]
            else:
                if current_block:
                    current_block.append(line)

        flush_block(current_block)

        # --- 5. 字典分组 ---
        unique_map = {}
        for b in blocks:
            unique_map[b['id']] = b

        date_groups = {}
        for b in unique_map.values():
            d = b['date']
            if d not in date_groups:
                date_groups[d] = []
            date_groups[d].append(b)

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

        # --- 7. 回写 ---
        section_body = ["\n"] + output_lines + ["\n"]
        file_lines[start_idx + 1: end_idx] = section_body

        return file_lines

    def aggressive_daily_clean(self, lines: list) -> list:
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

    def format_line(self, indent, status, text, dates, fname, bid, is_daily):
        """
        [v9.8 Single-Link Mode] 移除 Source 模式下的文件自引用链接。
        """
        tab_count = indent // 4
        indent_str = '\t' * tab_count

        if is_daily:
            # Daily Note 保持原样 (通常需要文件链接指回 Source)
            link = f"[[{fname}#^{bid}|⮐]]"
            time_match = re.match(r'^(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)', text)
            if time_match:
                time_part = time_match.group(1)
                rest_part = text[len(time_part):].strip()
                return f"{indent_str}- [{status}] {time_part} {link} {rest_part} ^{bid}\n"
            else:
                return f"{indent_str}- [{status}] {link} {text} ^{bid}\n"
        else:
            # Source File 逻辑
            clean_text = self.clean_task_text(text, bid, fname)
            creation_date = None

            # 1. 优先匹配纯日期字符串 (YYYY-MM-DD)
            if dates and re.match(r'^\d{4}-\d{2}-\d{2}$', str(dates).strip()):
                creation_date = str(dates).strip()

            # 2. 否则尝试正则提取
            if not creation_date:
                patterns = [
                    r'\[\[(\d{4}-\d{2}-\d{2})\]\]',
                    r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\|)',
                    r'(?:📅|\|📅\]\])\s*(\d{4}-\d{2}-\d{2})'
                ]
                for p in patterns:
                    m = re.search(p, str(dates)) or re.search(p, text)
                    if m: creation_date = m.group(1); break

            # 3. 兜底逻辑
            if not creation_date:
                today = datetime.date.today().strftime('%Y-%m-%d')
                if dates:
                    Logger.info(f"⚠️ [FORMAT WARNING] 日期解析失败！输入: '{dates}' -> 兜底: '{today}'")
                creation_date = today

            # 构建链接
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

    def normalize_child_lines(self, raw_lines, parent_indent, as_quoted=False):
        """
        [v11.1 Tab Enforcer]
        1. 强制使用 Tab (\t) 进行缩进，禁用空格混排。
        2. 即使 as_quoted=True，也只在最外层加引用，内部结构保持 Tab。
        """
        if not raw_lines: return []

        children = []
        first_line_raw_indent = -1

        for line in raw_lines:
            # 1. 强力清洗：移除现有的引用符号 > 和首尾空白
            content_cleaned = re.sub(r'^[>\s]+', '', line).strip()

            if not content_cleaned:
                children.append(("> \n" if as_quoted else "\n"))
                continue

            # 2. 计算原始缩进
            line_no_quote = re.sub(r'^>\s?', '', line)
            curr_indent = 0
            for char in line_no_quote:
                if char == '\t':
                    curr_indent += 4
                elif char == ' ':
                    curr_indent += 1
                else:
                    break

            # 3. 确定基准
            if first_line_raw_indent == -1:
                first_line_raw_indent = curr_indent

            # 4. 计算相对层级
            relative = curr_indent - first_line_raw_indent

            # 5. 计算目标层级
            target_indent_depth = parent_indent + 4 + relative
            if target_indent_depth < 0: target_indent_depth = 0

            # [关键修改] 强制转换为 Tab
            tab_count = target_indent_depth // 4
            indent_str = '\t' * tab_count

            final = f"{indent_str}{content_cleaned}"

            if as_quoted:
                final = f"> {final}"

            children.append(final + "\n")

        return children

    def reconstruct_daily_block(self, sd, target_date):
        """
        [v11.0 Structure Keeper]
        Source -> Daily 同步逻辑更新。
        """
        fname = sd['fname']
        bid = sd['bid']
        status = sd['status']

        # 1. 格式化父任务行
        text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}\]\]', '', sd['pure']).strip()
        link_tag = f"[[{fname}]]"
        if link_tag not in text:
            text = f"{link_tag} {text}"

        parent_line = self.format_line(sd['indent'], status, text, "", fname, bid, True)

        # 2. 格式化子任务
        children = self.normalize_child_lines(sd['raw'][1:], sd['indent'], as_quoted=False)

        return [parent_line] + children

    def ensure_structure(self, lines):
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
                lines.insert(0, "# Day planner\n\n")
                lines.append("\n# Journey\n")

        if has_dp and j_idx == -1:
            lines.append("\n# Journey\n")

        return lines

    def cleanup_empty_headers(self, lines, date_tag):
        lines = self.ensure_structure(lines)

        cleaned_lines = []
        i = 0
        modified = False
        current_section = None
        target_sections = ['# Day planner', '# Journey']

        while i < len(lines):
            line = lines[i]
            s_line = line.strip()

            if s_line.startswith('# '):
                current_section = s_line
                cleaned_lines.append(line)
                i += 1
                continue

            if current_section not in target_sections:
                cleaned_lines.append(line)
                i += 1
                continue

            if s_line.startswith('## '):
                has_content = False
                j = i + 1
                while j < len(lines):
                    next_s = lines[j].strip()
                    if next_s.startswith('# ') or next_s.startswith('## ') or next_s == '----------':
                        break
                    if next_s:
                        has_content = True
                        break
                    j += 1

                if not has_content:
                    modified = True
                    i = j
                else:
                    cleaned_lines.append(line)
                    i += 1
            else:
                cleaned_lines.append(line)
                i += 1

        return cleaned_lines, modified

    def scan_projects(self):
        self.project_map = {}
        self.project_path_map = {}
        self.file_path_map = {}
        for root, dirs, files in os.walk(Config.ROOT_DIR):
            dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
            if FileUtils.is_excluded(root): continue
            main_files = []
            for f in files:
                if f.endswith('.md'):
                    path = os.path.join(root, f)
                    f_name = unicodedata.normalize('NFC', os.path.splitext(f)[0])
                    self.file_path_map[f_name] = path
                    if 'main' in self.parse_yaml_tags(FileUtils.read_file(path) or []):
                        main_files.append(f)
            if len(main_files) == 1:
                p_name = unicodedata.normalize('NFC', os.path.splitext(main_files[0])[0])
                self.project_map[root] = p_name
                self.project_path_map[p_name] = os.path.join(root, main_files[0])

    def scan_all_source_tasks(self) -> Dict[str, Dict]:
        self.scan_projects()
        source_data_by_date = {}
        today_str = datetime.date.today().strftime('%Y-%m-%d')

        for root, dirs, files in os.walk(Config.ROOT_DIR):
            dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
            if FileUtils.is_excluded(root): continue

            curr_proj = None
            temp = root
            while temp.startswith(Config.ROOT_DIR):
                if temp in self.project_map: curr_proj = self.project_map[temp]; break
                temp = os.path.dirname(temp)
                if temp == os.path.dirname(temp): break
            if not curr_proj: continue

            for f in files:
                if not f.endswith('.md'): continue
                path = os.path.join(root, f)
                lines = FileUtils.read_file(path)
                if not lines: continue

                mod = False
                fname = os.path.splitext(f)[0]
                i = 0

                def get_raw_indent(s):
                    return len(s) - len(s.lstrip())

                in_task_section = False
                current_section_date = None
                seen_section_dates = set()

                while i < len(lines):
                    line = lines[i]
                    stripped = line.strip()

                    if stripped == '# Tasks':
                        in_task_section = True
                        current_section_date = None
                        seen_section_dates.clear()
                        i += 1
                        continue
                    if stripped == '----------':
                        in_task_section = False
                        current_section_date = None
                        i += 1
                        continue
                    if not in_task_section:
                        i += 1
                        continue

                    header_match = re.match(r'^#+\s*\[\[\s*(\d{4}-\d{2}-\d{2})\s*\]\]', stripped)
                    if header_match:
                        date_str = header_match.group(1)
                        if date_str in seen_section_dates:
                            Logger.info(f"   🔍 发现重复标题 {date_str}，将触发重组...")
                            mod = True
                        else:
                            seen_section_dates.add(date_str)
                        current_section_date = date_str
                        i += 1
                        continue

                    if stripped.startswith('#'):
                        current_section_date = None
                        i += 1
                        continue

                    if not re.match(r'^\s*-\s*\[.\]', line):
                        i += 1
                        continue

                    task_date = None
                    if current_section_date:
                        task_date = current_section_date
                    else:
                        date_match = re.search(r'[📅✅]\s*(\d{4}-\d{2}-\d{2})', line)
                        if date_match:
                            task_date = date_match.group(1)
                        else:
                            link_match = re.search(r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\||\]\])', line)
                            if link_match: task_date = link_match.group(1)

                    is_in_inbox_area = (current_section_date is None)
                    if is_in_inbox_area and not task_date:
                        i += 1
                        continue

                    if not task_date:
                        task_date = today_str
                        mod = True

                    indent = get_raw_indent(line)
                    status_match = re.search(r'-\s*\[(.)\]', line)
                    st = status_match.group(1) if status_match else ' '

                    # [Rescue] 智能救援
                    id_m = re.search(r'\^([a-zA-Z0-9]{6,7})\s*$', line)
                    bid = id_m.group(1) if id_m else None

                    if not bid:
                        raw_block, _ = self.capture_block(lines, i)
                        temp_clean = self.clean_task_text(line, None, fname)
                        temp_clean = re.sub(r'\s+\^?[a-zA-Z0-9]*$', '', temp_clean).strip()
                        combined_body = self.normalize_block_content(raw_block[1:])
                        temp_combined_text = temp_clean + "|||" + combined_body
                        recovery_hash = self.sm.calc_hash(st, temp_combined_text)
                        found_id = self.sm.find_id_by_hash(path, recovery_hash)

                        if found_id:
                            Logger.info(f"   🚑 [RESCUE] 指纹匹配成功! '{temp_clean[:10]}...' -> 复活 ID: {found_id}")
                            bid = found_id
                            mod = True
                        else:
                            bid = self.generate_block_id().replace('^', '')
                            mod = True

                    clean_txt = self.clean_task_text(line, bid, context_name=fname)
                    dates_pattern = r'([📅✅]\s*\d{4}-\d{2}-\d{2}|\[\[\d{4}-\d{2}-\d{2}(?:#\^[a-zA-Z0-9]+)?(?:\|[📅⮐])?\]\])'
                    dates = " ".join(re.findall(dates_pattern, line))

                    if current_section_date and current_section_date not in dates:
                        dates = f"[[{task_date}]]"
                        mod = True
                    if task_date not in line and not dates:
                        dates = f"[[{task_date}]]"
                        mod = True

                    new_line = self.format_line(indent, st, clean_txt, dates, fname, bid, False)
                    if new_line.strip() != line.strip():
                        lines[i] = new_line
                        mod = True

                    block, consumed = self.capture_block(lines, i)
                    combined_text = clean_txt + "|||" + self.normalize_block_content(block[1:])
                    content_hash = self.sm.calc_hash(st, combined_text)

                    if task_date not in source_data_by_date: source_data_by_date[task_date] = {}
                    source_data_by_date[task_date][bid] = {
                        'proj': curr_proj, 'bid': bid, 'pure': clean_txt, 'status': st,
                        'path': path, 'fname': fname, 'raw': block, 'hash': content_hash, 'indent': indent,
                        'dates': dates, 'is_quoted': False
                    }
                    i += consumed

                if mod:
                    lines = self.inject_into_task_section(lines, [])
                    Logger.info(f"   💾 [WRITE] 自动格式化源文件 (Scan): {os.path.basename(path)}")
                    FileUtils.write_file(path, lines)

        for delta in range(3):
            target_d = datetime.date.today() - datetime.timedelta(days=delta)
            target_s = target_d.strftime('%Y-%m-%d')
            if target_s not in source_data_by_date:
                source_data_by_date[target_s] = {}

        return source_data_by_date

    def organize_orphans(self, filepath, date_tag):
        """
        [v11.5 Precision Archiving]
        1. 修复标签冗余：精准使用文件名作为标签。
        2. 返回 processed_bids 辅助首轮同步。
        """
        lines = FileUtils.read_file(filepath)
        if not lines: return set()

        lines = self.ensure_structure(lines)
        tasks_to_move = []
        processed_bids = set()

        ctx = "ROOT"
        i = 0
        while i < len(lines):
            l = lines[i].strip()
            if l.startswith('# '):
                ctx = 'JOURNEY' if l == '# Journey' else ('PLANNER' if l == '# Day planner' else 'OTHER')
                i += 1; continue
            if l.startswith('## [[') and l.endswith(']]'): ctx = 'PROJECT'; i += 1; continue

            if re.match(r'^[\s>]*-\s*\[.\]', lines[i]):
                if ctx in ['JOURNEY', 'PLANNER']:
                    routing_target = self.extract_routing_target(lines[i])
                    p_name = None
                    if routing_target:
                        curr = os.path.dirname(routing_target)
                    else:
                        curr = Config.ROOT_DIR

                    search_start = curr
                    while search_start.startswith(Config.ROOT_DIR):
                        if search_start in self.project_map: p_name = self.project_map[search_start]; break
                        parent = os.path.dirname(search_start)
                        if parent == search_start: break
                        search_start = parent

                    if p_name:
                        content, length = self.capture_block(lines, i)
                        raw_first = content[0]
                        bid_m = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', raw_first)
                        bid = bid_m.group(1) if bid_m else self.generate_block_id().replace('^', '')

                        final_tag_name = p_name
                        if routing_target:
                            final_tag_name = os.path.splitext(os.path.basename(routing_target))[0]

                        clean_pure = self.clean_task_text(raw_first, bid, final_tag_name)
                        indent_len = len(raw_first) - len(raw_first.lstrip())
                        indent_str = raw_first[:indent_len]
                        st_m = re.search(r'-\s*\[(.)\]', raw_first)
                        status = st_m.group(1) if st_m else ' '

                        ret_link = f"[[{date_tag}#^{bid}|⮐]]"
                        file_tag = f"[[{final_tag_name}]]"
                        new_line = f"{indent_str}- [{status}] {ret_link} {file_tag} {clean_pure} ^{bid}\n"

                        content[0] = new_line
                        tasks_to_move.append({'idx': i, 'len': length, 'proj': p_name, 'raw': content})
                        processed_bids.add(bid)
                        i += length; continue
            i += 1

        if not tasks_to_move: return set()

        tasks_to_move.sort(key=lambda x: x['idx'], reverse=True)
        for t in tasks_to_move: del lines[t['idx']:t['idx'] + t['len']]

        grouped = {}
        for t in tasks_to_move:
            if t['proj'] not in grouped: grouped[t['proj']] = []
            grouped[t['proj']].extend(t['raw'])

        try:
            j_idx = next(i for i, l in enumerate(lines) if l.strip() == "# Journey")
        except:
            j_idx = len(lines)
        ins_pt = len(lines)
        for i in range(j_idx + 1, len(lines)):
            if lines[i].startswith('# '): ins_pt = i; break

        offset = 0
        for proj, blocks in grouped.items():
            header = f"## [[{proj}]]"
            h_idx = -1
            for k in range(j_idx, ins_pt + offset):
                if lines[k].strip() == header: h_idx = k; break

            if blocks and not blocks[-1].endswith('\n'): blocks[-1] += '\n'

            if h_idx != -1:
                sub_ins = ins_pt + offset
                for k in range(h_idx + 1, ins_pt + offset):
                    if lines[k].startswith('#'): sub_ins = k; break
                lines[sub_ins:sub_ins] = blocks
                offset += len(blocks)
            else:
                chunk = [f"\n{header}\n"] + blocks
                lines[ins_pt + offset:ins_pt + offset] = chunk
                offset += len(chunk)

        Logger.info(f"归档 {len(tasks_to_move)} 个流浪任务", date_tag)
        Logger.info(f"   💾 [WRITE] 更新归档文件 (Orphans): {os.path.basename(filepath)}")
        if FileUtils.write_file(filepath, lines):
            return processed_bids
        return set()

    def process_date(self, target_date, src_tasks_for_date):
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{target_date}.md")

        organized_bids = set()
        if os.path.exists(daily_path):
            organized_bids = self.organize_orphans(daily_path, target_date)

        dn_tasks = {}
        new_dn_tasks = []
        dn_lines = []

        if os.path.exists(daily_path):
            dn_lines = FileUtils.read_file(daily_path) or []
            curr_ctx = None
            current_section = None
            i = 0
            while i < len(dn_lines):
                line = dn_lines[i]
                if line.startswith('# '): current_section = line.strip()
                h_m = re.match(r'^##\s*\[\[(.*?)\]\]', line.strip())
                if h_m: curr_ctx = h_m.group(1); i += 1; continue
                tm = re.match(r'^[\s>]*-\s*\[(.)\]', line)
                if tm:
                    is_allowed_section = False
                    if current_section in Config.DAILY_NOTE_SECTIONS: is_allowed_section = True
                    if not is_allowed_section: i += 1; continue

                    lm = re.search(r'\[\[(.*?)\#\^([a-zA-Z0-9]{6,})\|.*?\]\]', line)
                    if lm:
                        ctx_name = lm.group(1);
                        bid = lm.group(2)
                        raw, c = self.capture_block(dn_lines, i)
                        clean = self.clean_task_text(line, bid, context_name=ctx_name)
                        st = tm.group(1)
                        combined_text = clean + "|||" + self.normalize_block_content(raw[1:])
                        content_hash = self.sm.calc_hash(st, combined_text)

                        dn_tasks[bid] = {
                            'pure': clean, 'status': st, 'idx': i, 'len': c, 'raw': raw,
                            'hash': content_hash, 'proj': curr_ctx
                        }
                        i += c; continue
                    elif curr_ctx and curr_ctx in self.project_path_map:
                        if '^' not in line:
                            raw_indent = len(line) - len(line.lstrip())
                            raw, c = self.capture_block(dn_lines, i)
                            new_dn_tasks.append({'proj': curr_ctx, 'idx': i, 'len': c, 'raw': raw, 'st': tm.group(1),
                                                 'indent': raw_indent})
                            i += c; continue
                        else:
                            link_match = re.search(r'\[\[(.*?)(?:#|\||\]\])', line)
                            if link_match:
                                pot = link_match.group(1).strip()
                                pot = unicodedata.normalize('NFC', pot)
                                target_file = None
                                if pot in self.project_path_map:
                                    target_file = self.project_path_map[pot]
                                elif pot in self.file_path_map:
                                    target_file = self.file_path_map[pot]
                                if target_file:
                                    raw_indent = len(line) - len(line.lstrip())
                                    raw, c = self.capture_block(dn_lines, i)
                                    new_dn_tasks.append(
                                        {'proj': self.project_map.get(os.path.dirname(target_file), pot), 'idx': i,
                                         'len': c, 'raw': raw, 'st': tm.group(1), 'indent': raw_indent})
                                    i += c; continue
                i += 1

        dn_mod = False

        if new_dn_tasks:
            Logger.info(f"   [NEW] 发现 {len(new_dn_tasks)} 个待注册任务")
            for nt in reversed(new_dn_tasks):
                p_name = nt['proj']
                txt = nt['raw'][0]
                clean = self.clean_task_text(txt)
                tgt = self.extract_routing_target(txt) or self.project_path_map.get(p_name)
                if not tgt: continue

                bid = self.generate_block_id().replace('^', '')
                fname = os.path.splitext(os.path.basename(tgt))[0]

                Logger.info(f"   ➕ 注册任务 {bid}:")
                s_l = self.format_line(nt['indent'], nt['st'], clean, target_date, fname, bid, False)
                s_blk = [s_l] + self.normalize_child_lines(nt['raw'][1:], nt['indent'], as_quoted=True)

                d_l = self.format_line(nt['indent'], nt['st'], clean, "", fname, bid, True)
                d_blk = [d_l] + self.normalize_child_lines(nt['raw'][1:], nt['indent'], as_quoted=False)

                dn_lines[nt['idx']:nt['idx'] + nt['len']] = d_blk
                dn_mod = True

                sl = FileUtils.read_file(tgt) or []
                sl = self.inject_into_task_section(sl, s_blk)
                Logger.info(f"   💾 [WRITE] 写入源文件 (New Task): {os.path.basename(tgt)}")
                FileUtils.write_file(tgt, sl)
                self.trigger_delayed_verification(tgt)

                combined_text = clean + "|||" + self.normalize_block_content(nt['raw'][1:])
                h = self.sm.calc_hash(nt['st'], combined_text)
                self.sm.update_task(bid, h, tgt, target_date)

        if dn_mod:
            Logger.info(f"   💾 [WRITE] 更新日记文件 (Sync Pre-Save): {os.path.basename(daily_path)}")
            FileUtils.write_file(daily_path, dn_lines)
            self.sm.save()

        src_tasks = src_tasks_for_date
        all_ids = set(src_tasks.keys()) | set(dn_tasks.keys())
        append_to_dn = {}
        src_updates = {}
        src_deletes = {}

        for bid in all_ids:
            in_s = bid in src_tasks
            in_d = bid in dn_tasks
            last_hash = self.sm.get_task_hash(bid)
            last_date = self.sm.get_task_date(bid)

            if in_s:
                sd = src_tasks[bid]
                if in_d:
                    dd = dn_tasks[bid]
                    s_changed = (sd['hash'] != last_hash)
                    d_changed = (dd['hash'] != last_hash)

                    if s_changed and not d_changed:
                        Logger.info(f"   🔄 S->D 同步 ({bid}):")
                        blk = self.reconstruct_daily_block(sd, target_date)
                        dn_lines[dd['idx']:dd['idx'] + dd['len']] = blk
                        dn_mod = True
                        self.sm.update_task(bid, sd['hash'], sd['path'], target_date)

                    elif d_changed and not s_changed:
                        Logger.info(f"   🔄 D->S 同步 ({bid}):")
                        n_l = self.format_line(sd['indent'], dd['status'], dd['pure'], target_date, sd['fname'], bid, False)
                        blk = [n_l] + self.normalize_child_lines(dd['raw'][1:], sd['indent'], as_quoted=False)
                        if sd['path'] not in src_updates: src_updates[sd['path']] = {}
                        src_updates[sd['path']][bid] = blk
                        self.sm.update_task(bid, dd['hash'], sd['path'], target_date)

                    elif s_changed and d_changed:
                        if sd['hash'] != dd['hash']:
                            Logger.info(f"   ⚔️ 冲突 ({bid}): Daily 覆盖 Source")
                            n_l = self.format_line(sd['indent'], dd['status'], dd['pure'], target_date, sd['fname'], bid, False)
                            blk = [n_l] + self.normalize_child_lines(dd['raw'][1:], sd['indent'], as_quoted=False)
                            if sd['path'] not in src_updates: src_updates[sd['path']] = {}
                            src_updates[sd['path']][bid] = blk
                            self.sm.update_task(bid, dd['hash'], sd['path'], target_date)
                    else:
                        self.sm.update_task(bid, sd['hash'], sd['path'], target_date)

                else:
                    # [Source Only]
                    has_ghost_match = False
                    for d_val in dn_tasks.values():
                        if d_val['hash'] == sd['hash']:
                            has_ghost_match = True; break
                    if last_date == target_date and not has_ghost_match:
                        Logger.info(f"   🗑️ 删除 Source ({bid}): 因 Daily 移除")
                        if sd['path'] not in src_deletes: src_deletes[sd['path']] = {}
                        src_deletes[sd['path']][bid] = sd['path']
                        self.sm.remove_task(bid)
                    else:
                        if has_ghost_match:
                            Logger.info(f"   🛡️ 拦截删除 Source ({bid}): Daily 中发现同内容异号任务")
                        task_dates_str = sd.get('dates', '')
                        linked_dates = re.findall(r'(\d{4}-\d{2}-\d{2})', task_dates_str)
                        is_misjudged = False
                        if linked_dates and target_date not in linked_dates: is_misjudged = True
                        if is_misjudged:
                            Logger.info(f"   🛡️ 拦截追加 ({bid}): 归属 {linked_dates} != 当前 {target_date}")
                            continue
                        Logger.info(f"   ➕ 追加 Daily ({bid}): 来自 {sd['fname']}")
                        if sd['proj'] not in append_to_dn: append_to_dn[sd['proj']] = []
                        append_to_dn[sd['proj']].append(sd)
                        self.sm.update_task(bid, sd['hash'], sd['path'], target_date)

            elif in_d and not in_s:
                # [CRITICAL FIX] 归档任务晋升逻辑 (Graduate Logic)
                dd = dn_tasks[bid]
                raw_first = dd['raw'][0] # [Fix] 变量前置

                db_data = self.sm.state.get(bid, {})
                last_path = db_data.get('source_path', '')
                is_daily_native = (not last_path) or (Config.DAILY_NOTE_DIR in last_path)

                target_file_direct = self.extract_routing_target(raw_first)
                should_push = (bid in organized_bids) or is_daily_native or (
                            target_file_direct and os.path.exists(target_file_direct))

                if should_push:
                    target_file = None
                    if target_file_direct:
                        target_file = target_file_direct
                    else:
                        p_name = dd.get('proj')
                        target_file = self.project_path_map.get(p_name)

                    if target_file and os.path.exists(target_file):
                        Logger.info(f"   🚀 [GRADUATE] 归档任务晋升上行 ({bid}) -> {os.path.basename(target_file)}")
                        fname = os.path.splitext(os.path.basename(target_file))[0]
                        clean = dd['pure']
                        raw_no_quote = re.sub(r'^>\s?', '', raw_first)
                        raw_indent = 0
                        for char in raw_no_quote:
                            if char == '\t': raw_indent += 4
                            elif char == ' ': raw_indent += 1
                            else: break

                        n_l = self.format_line(raw_indent, dd['status'], clean, target_date, fname, bid, False)
                        blk = [n_l] + self.normalize_child_lines(dd['raw'][1:], raw_indent, as_quoted=False)

                        if target_file not in src_updates: src_updates[target_file] = {}
                        src_updates[target_file][bid] = blk
                        self.sm.update_task(bid, dd['hash'], target_file, target_date)
                    else:
                        Logger.info(f"   ⚠️ [ORPHAN] 无法同步，找不到目标文件")
                else:
                    Logger.info(f"   🗑️ 删除 Daily ({bid}): 因 Source 移除")
                    for k in range(dd['idx'], dd['idx'] + dd['len']): dn_lines[k] = "__DEL__\n"
                    dn_mod = True

        if dn_mod: dn_lines = [x for x in dn_lines if x != "__DEL__\n"]

        # --- 4. 执行写入 ---
        if src_deletes:
            for path, bids in src_deletes.items():
                sl = FileUtils.read_file(path)
                if not sl: continue
                out, i, chg = [], 0, False
                deleted_bids = list(bids.keys())
                while i < len(sl):
                    im = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', sl[i])
                    if not im: im = re.search(r'\(connect::.*?\^([a-zA-Z0-9]{6,})\)', sl[i])
                    if im and im.group(1) in deleted_bids:
                        _, c = self.capture_block(sl, i); i += c; chg = True
                    else:
                        out.append(sl[i]); i += 1
                if chg:
                    stem = os.path.splitext(os.path.basename(path))[0]
                    out = self.inject_into_task_section(out, [], stem)
                    out = [l for l in out if l is not None]
                    Logger.info(f"   💾 [WRITE] 写入源文件 (Delete): {os.path.basename(path)}")
                    FileUtils.write_file(path, out)

        # [CRITICAL FIX] 修复更新逻辑：同时支持"原地更新"和"新任务插入"
        if src_updates:
            for path, ups in src_updates.items():
                sl = FileUtils.read_file(path)
                if not sl: sl = []
                out, i, chg = [], 0, False
                handled_bids = set()

                # 1. 尝试原地更新 (Replace)
                while i < len(sl):
                    im = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', sl[i])
                    if not im: im = re.search(r'\(connect::.*?\^([a-zA-Z0-9]{6,})\)', sl[i])
                    if im and im.group(1) in ups:
                        bid = im.group(1)
                        _, c = self.capture_block(sl, i)
                        out.extend(ups[bid])
                        handled_bids.add(bid)
                        i += c; chg = True
                    else:
                        out.append(sl[i]); i += 1

                # 2. 收集漏网之鱼 (Insert)
                pending_inserts = []
                for bid, blk in ups.items():
                    if bid not in handled_bids:
                        pending_inserts.extend(blk)
                        chg = True

                if chg:
                    stem = os.path.splitext(os.path.basename(path))[0]
                    out = self.inject_into_task_section(out, pending_inserts, stem)
                    out = [l for l in out if l is not None]
                    Logger.info(f"   💾 [WRITE] 写入源文件 (Update/Insert): {os.path.basename(path)}")
                    FileUtils.write_file(path, out)
                    self.trigger_delayed_verification(path)

        if append_to_dn:
            try:
                j_idx = next(i for i, l in enumerate(dn_lines) if l.strip() == "# Journey")
            except:
                j_idx = 0
            end_pt = len(dn_lines)
            for i in range(j_idx + 1, len(dn_lines)):
                if dn_lines[i].startswith('# '): end_pt = i; break
            offset = 0
            for proj, tasks in append_to_dn.items():
                header = f"## [[{proj}]]"
                h_idx = -1
                curr_search_end = end_pt + offset
                for k in range(j_idx, curr_search_end):
                    if dn_lines[k].strip() == header: h_idx = k; break
                txt_blk = []
                for t in tasks:
                    txt = t['pure']
                    file_tag = f"[[{t['fname']}]]"
                    if file_tag not in txt: txt = f"{file_tag} {txt}"
                    l1 = self.format_line(t['indent'], t['status'], txt, "", t['fname'], t['bid'], True)
                    children = self.normalize_child_lines(t['raw'][1:], t['indent'], as_quoted=False)
                    txt_blk.extend([l1] + children)
                    if not txt_blk[-1].endswith('\n'): txt_blk[-1] += '\n'
                if h_idx != -1:
                    ins = curr_search_end
                    for k in range(h_idx + 1, curr_search_end):
                        if dn_lines[k].startswith('#'): ins = k; break
                    dn_lines[ins:ins] = txt_blk
                    offset += len(txt_blk)
                else:
                    chunk = [f"\n{header}\n"] + txt_blk
                    dn_lines[end_pt + offset:end_pt + offset] = chunk
                    offset += len(chunk)
            if offset > 0: dn_mod = True

        dn_lines, cleaned = self.cleanup_empty_headers(dn_lines, target_date)
        if cleaned: dn_mod = True
        original_len = len(dn_lines)
        dn_lines = self.aggressive_daily_clean(dn_lines)
        if len(dn_lines) != original_len: dn_mod = True

        if dn_mod:
            dn_lines = [l for l in dn_lines if l is not None]
            FileUtils.write_file(daily_path, dn_lines)
            Logger.info(f"   ✅ 日记文件已回写: {os.path.basename(daily_path)}")

        self.sm.save()