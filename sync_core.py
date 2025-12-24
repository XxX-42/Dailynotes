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
        [v10.8 Time Strip] 增加时间段剥离，防止 07:00 - 11:20 污染源文件。
        """
        # 1. 移除 Checkbox (保留)
        line = re.sub(r'^\s*-\s*\[.\]\s?', '', line)

        # === [新增] 2. 移除 Day Planner 时间段 ===
        # 匹配: "07:00 " 或 "07:00 - 11:20 "
        # 逻辑: 只有位于行首（去除 checkbox 后）的时间才会被视为调度信息
        line = re.sub(r'^\s*\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?\s+', '', line)

        clean_text = line

        # 3. 移除指定块 ID (原逻辑)
        if block_id:
            clean_text = re.sub(rf'(?<=\s)\^{re.escape(block_id)}\s*$', '', clean_text)

        # 4. 通用尾部清理 (原逻辑)
        clean_text = re.sub(r'\s+\^[a-zA-Z0-9]*$', '', clean_text)

        # 5. 移除日期链接 (原逻辑)
        clean_text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}(?:#\^[a-zA-Z0-9]+)?(?:\|.*?)?\]\]', '', clean_text)

        # 6. 移除文件自身链接 (原逻辑)
        if context_name:
            clean_text = re.sub(rf'\[\[{re.escape(context_name)}(?:#\^[a-zA-Z0-9]+)?(?:\|.*?)?\]\]', '', clean_text)

        # 7. 移除 Emoji 日期 (原逻辑)
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

    # === [NEW] Helper for robust indentation ===
    def _get_indent_depth(self, line):
        """
        [Helper] 统一计算缩进视觉深度 (Tab=4 spaces)
        解决 Tab/Space 混用导致的层级判断失效问题。
        """
        no_quote = re.sub(r'^>\s?', '', line)
        expanded = no_quote.expandtabs(4)
        return len(expanded) - len(expanded.lstrip())

    # === [MODIFIED] Robust Capture Block ===
    def capture_block(self, lines, start_idx):
        """
        [v14.2 Indent-Priority Capture]
        修复双重缩进任务 (- [ ]) 被截断的 Bug。
        核心逻辑变更：确立【缩进霸权】。
        只要当前行缩进 > 父级缩进，无条件视为子内容，跳过任何内容检查（如 # 或 ---）。
        只有缩进 <= 父级时，才进行结束判定。
        """
        if start_idx >= len(lines): return [], 0

        # 1. 获取父级（锚点）的视觉缩进深度
        base_depth = self._get_indent_depth(lines[start_idx])

        block = [lines[start_idx]]
        consumed = 1
        j = start_idx + 1

        while j < len(lines):
            nl = lines[j]

            # 1. 空行处理：始终保留，不作为判定依据
            if not nl.strip():
                block.append(nl)
                consumed += 1
                j += 1
                continue

            # 2. 强分隔符：唯一的例外，必须截断
            if nl.strip() == '----------': break

            # 3. 计算当前行缩进
            curr_depth = self._get_indent_depth(nl)

            # === [核心修复] 缩进优先原则 ===
            # 如果当前行比父级缩进深，它就是子元素。
            # 不检查它是否以 '#' 开头，也不做任何正则清洗。
            # 这保证了 `      - [ ]` 这种结构绝对会被捕获。
            if curr_depth > base_depth:
                block.append(nl)
                consumed += 1
                j += 1
                continue

            # 4. 只有当缩进 <= 父级时，才视为潜在的结束
            # 此时遇到同级任务、同级标题或更浅的内容，均结束捕获
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

    def _calculate_sort_key(self, block_data):
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

    def inject_into_task_section(self, file_lines, block_lines, filename_stem=None):
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
            group_blocks.sort(key=self._calculate_sort_key)

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
            clean_text = self.clean_task_text(text, bid, fname)
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

    # === [MODIFIED] Anchor-Based Normalization ===
    def normalize_child_lines(self, raw_lines, target_parent_indent, source_parent_indent=None, as_quoted=False):
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
                source_parent_indent = max(0, self._get_indent_depth(raw_lines[0]) - 4)
            else:
                source_parent_indent = 0

        children = []
        for line in raw_lines:
            content_cleaned = re.sub(r'^[>\s]+', '', line).strip()
            if not content_cleaned:
                children.append(("> \n" if as_quoted else "\n"))
                continue

            # 1. 计算当前行相对于“原父级”的偏移量
            current_depth = self._get_indent_depth(line)
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

    # === [MODIFIED] Bridge with Anchor ===
    def reconstruct_daily_block(self, sd, target_date):
        fname = sd['fname']
        bid = sd['bid']
        status = sd['status']
        text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}\]\]', '', sd['pure']).strip()
        link_tag = f"[[{fname}]]"
        if link_tag not in text: text = f"{link_tag} {text}"

        # 传递 sd['indent'] 作为 source_parent_indent
        parent_line = self.format_line(sd['indent'], status, text, "", fname, bid, True)
        children = self.normalize_child_lines(
            sd['raw'][1:],
            target_parent_indent=sd['indent'],
            source_parent_indent=sd['indent'],
            as_quoted=False
        )
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
                lines.insert(0, "# Day planner\n\n");
                lines.append("\n# Journey\n")
        if has_dp and j_idx == -1: lines.append("\n# Journey\n")
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

    def scan_projects(self):
        self.project_map = {}
        self.project_path_map = {}
        self.file_path_map = {}

        # 预处理：标准化聚合目录路径，避免不同系统的斜杠差异
        forced_dirs = [os.path.normpath(p) for p in Config.FORCED_AGGREGATION_DIRS]

        for root, dirs, files in os.walk(Config.ROOT_DIR):
            dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
            if FileUtils.is_excluded(root): continue

            main_files = []
            for f in files:
                if f.endswith('.md'):
                    path = os.path.join(root, f)
                    f_name = unicodedata.normalize('NFC', os.path.splitext(f)[0])
                    self.file_path_map[f_name] = path

                    # 依然读取 tags，保持文件级别的识别能力
                    if 'main' in self.parse_yaml_tags(FileUtils.read_file(path) or []):
                        main_files.append(f)

            # === [核心修改 START] ===
            is_shadowed = False
            norm_root = os.path.normpath(root)

            for parent_dir in forced_dirs:
                if norm_root.startswith(parent_dir) and len(norm_root) > len(parent_dir):
                    rel_path = norm_root[len(parent_dir):]
                    if rel_path.startswith(os.sep):
                        is_shadowed = True
                        break

            if is_shadowed:
                continue
            # === [核心修改 END] ===

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

                in_task_section = False
                current_section_date = None
                seen_section_dates = set()
                while i < len(lines):
                    line = lines[i]
                    stripped = line.strip()
                    if stripped == '# Tasks':
                        in_task_section = True;
                        current_section_date = None;
                        seen_section_dates.clear();
                        i += 1;
                        continue
                    if stripped == '----------':
                        in_task_section = False;
                        current_section_date = None;
                        i += 1;
                        continue
                    if not in_task_section: i += 1; continue
                    header_match = re.match(r'^#+\s*\[\[\s*(\d{4}-\d{2}-\d{2})\s*\]\]', stripped)
                    if header_match:
                        date_str = header_match.group(1)
                        if date_str in seen_section_dates:
                            Logger.info(f"   🔍 发现重复标题 {date_str}，将触发重组...");
                            mod = True
                        else:
                            seen_section_dates.add(date_str)
                        current_section_date = date_str;
                        i += 1;
                        continue
                    if stripped.startswith('#'): current_section_date = None; i += 1; continue
                    if not re.match(r'^\s*-\s*\[.\]', line): i += 1; continue
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
                    if is_in_inbox_area and not task_date: i += 1; continue
                    if not task_date: task_date = today_str; mod = True

                    # [MODIFIED] Use visual depth
                    indent = self._get_indent_depth(line)

                    status_match = re.search(r'-\s*\[(.)\]', line)
                    st = status_match.group(1) if status_match else ' '
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
                            bid = found_id;
                            mod = True
                        else:
                            bid = self.generate_block_id().replace('^', '');
                            mod = True
                    clean_txt = self.clean_task_text(line, bid, context_name=fname)
                    dates_pattern = r'([📅✅]\s*\d{4}-\d{2}-\d{2}|\[\[\d{4}-\d{2}-\d{2}(?:#\^[a-zA-Z0-9]+)?(?:\|[📅⮐])?\]\])'
                    dates = " ".join(re.findall(dates_pattern, line))
                    if current_section_date and current_section_date not in dates: dates = f"[[{task_date}]]"; mod = True
                    if task_date not in line and not dates: dates = f"[[{task_date}]]"; mod = True
                    new_line = self.format_line(indent, st, clean_txt, dates, fname, bid, False)
                    if new_line.strip() != line.strip(): lines[i] = new_line; mod = True

                    # [TIME GATE]
                    if task_date < Config.SYNC_START_DATE:
                        _, consumed = self.capture_block(lines, i)
                        i += consumed
                        continue

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
                    # [CHECK] 比对磁盘文件，防止死循环
                    orig = FileUtils.read_file(path)
                    new_c = "".join(lines)
                    old_c = "".join(orig) if orig else ""
                    if new_c != old_c:
                        Logger.info(f"   💾 [WRITE] 自动格式化源文件 (Scan): {os.path.basename(path)}")
                        FileUtils.write_file(path, lines)
        for delta in range(3):
            target_d = datetime.date.today() - datetime.timedelta(days=delta)
            target_s = target_d.strftime('%Y-%m-%d')
            if target_s not in source_data_by_date: source_data_by_date[target_s] = {}
        return source_data_by_date

    def organize_orphans(self, filepath, date_tag):
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
                i += 1;
                continue
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
                        if routing_target: final_tag_name = os.path.splitext(os.path.basename(routing_target))[0]

                        # [MODIFIED] 保留时间并修改链接指向
                        clean_pure = self.clean_task_text(raw_first, bid, final_tag_name)

                        # Use raw string slicing for preservation, but logic relies on capture_block
                        indent_len = len(raw_first) - len(raw_first.lstrip())
                        indent_str = raw_first[:indent_len]

                        st_m = re.search(r'-\s*\[(.)\]', raw_first)
                        status = st_m.group(1) if st_m else ' '

                        # 1. 提取时间 (防止 clean_task_text 把时间吞掉)
                        time_part = ""
                        body_only = re.sub(r'^\s*-\s*\[.\]\s?', '', raw_first)
                        tm = re.match(r'^(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)', body_only)
                        if tm: time_part = tm.group(1) + " "

                        # 2. 链接指向项目文件 (Target) 而非 日期 (Date)
                        ret_link = f"[[{final_tag_name}#^{bid}|⮐]]"

                        file_tag = f"[[{final_tag_name}]]"
                        # 3. 组装：缩进 - [x] 时间 链接 文件标签 内容 ID
                        new_line = f"{indent_str}- [{status}] {time_part}{ret_link} {file_tag} {clean_pure} ^{bid}\n"

                        content[0] = new_line
                        tasks_to_move.append({'idx': i, 'len': length, 'proj': p_name, 'raw': content})
                        processed_bids.add(bid)
                        i += length;
                        continue
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
        if FileUtils.write_file(filepath, lines): return processed_bids
        return set()

    def process_date(self, target_date, src_tasks_for_date):
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{target_date}.md")

        # [NEW] 模版初始化
        if not os.path.exists(daily_path) and src_tasks_for_date:
            if os.path.exists(Config.TEMPLATE_FILE):
                try:
                    tmpl_lines = FileUtils.read_file(Config.TEMPLATE_FILE)
                    if tmpl_lines:
                        Logger.info(f"   📄 [TEMPLATE] 检测到未来/缺失日记，正在从模版创建: {target_date}.md")
                        FileUtils.write_file(daily_path, tmpl_lines)
                        time.sleep(0.1)
                except Exception as e:
                    Logger.error_once(f"tmpl_fail_{target_date}", f"模版创建失败: {e}")
            else:
                Logger.info(f"   ⚠️ 未找到模版文件 ({Config.REL_TEMPLATE_FILE})，创建基础骨架: {target_date}.md")
                base_scaffold = ["# Day planner\n", "\n", "# Journey\n", "\n"]
                FileUtils.write_file(daily_path, base_scaffold)

        organized_bids = set()
        if os.path.exists(daily_path): organized_bids = self.organize_orphans(daily_path, target_date)
        dn_tasks = {}
        new_dn_tasks = []
        dn_lines = []
        if os.path.exists(daily_path):
            dn_lines = FileUtils.read_file(daily_path) or []
            curr_ctx = None;
            current_section = None;
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

                        # [MODIFIED] Store indent for reconstruction
                        indent_val = self._get_indent_depth(line)
                        dn_tasks[bid] = {'pure': clean, 'status': st, 'idx': i, 'len': c, 'raw': raw,
                                         'hash': content_hash, 'proj': curr_ctx, 'indent': indent_val}
                        i += c;
                        continue
                    elif curr_ctx and curr_ctx in self.project_path_map:
                        if '^' not in line:
                            raw_indent = self._get_indent_depth(line)  # [MODIFIED]
                            raw, c = self.capture_block(dn_lines, i)
                            new_dn_tasks.append({'proj': curr_ctx, 'idx': i, 'len': c, 'raw': raw, 'st': tm.group(1),
                                                 'indent': raw_indent})
                            i += c;
                            continue
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
                                    raw_indent = self._get_indent_depth(line)  # [MODIFIED]
                                    raw, c = self.capture_block(dn_lines, i)
                                    new_dn_tasks.append(
                                        {'proj': self.project_map.get(os.path.dirname(target_file), pot), 'idx': i,
                                         'len': c, 'raw': raw, 'st': tm.group(1), 'indent': raw_indent})
                                    i += c;
                                    continue
                i += 1

        dn_mod = False
        if new_dn_tasks:
            Logger.info(f"   [NEW] 发现 {len(new_dn_tasks)} 个待注册任务")
            for nt in reversed(new_dn_tasks):
                p_name = nt['proj'];
                txt = nt['raw'][0];
                clean = self.clean_task_text(txt)
                tgt = self.extract_routing_target(txt) or self.project_path_map.get(p_name)
                if not tgt: continue
                bid = self.generate_block_id().replace('^', '')
                fname = os.path.splitext(os.path.basename(tgt))[0]
                Logger.info(f"   ➕ 注册任务 {bid}:")
                s_l = self.format_line(nt['indent'], nt['st'], clean, target_date, fname, bid, False)
                # [MODIFIED] Pass source_parent_indent
                s_blk = [s_l] + self.normalize_child_lines(nt['raw'][1:], nt['indent'],
                                                           source_parent_indent=nt['indent'], as_quoted=True)
                d_l = self.format_line(nt['indent'], nt['st'], clean, "", fname, bid, True)
                d_blk = [d_l] + self.normalize_child_lines(nt['raw'][1:], nt['indent'],
                                                           source_parent_indent=nt['indent'], as_quoted=False)

                dn_lines[nt['idx']:nt['idx'] + nt['len']] = d_blk
                dn_mod = True
                sl = FileUtils.read_file(tgt) or []
                sl = self.inject_into_task_section(sl, s_blk)
                # [FIX] 显式比对，防止 None 导致丢包
                orig_sl = FileUtils.read_file(tgt) or []
                if "".join(sl) != "".join(orig_sl):
                    # === 🎯 第一次日志修改 (New Task) ===
                    Logger.info(f"   💾 [WRITE] 写入源文件 (New Task) (from {target_date}): {os.path.basename(tgt)}")
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
            in_s = bid in src_tasks;
            in_d = bid in dn_tasks
            last_hash = self.sm.get_task_hash(bid);
            last_date = self.sm.get_task_date(bid)
            if in_s:
                sd = src_tasks[bid]
                if in_d:
                    dd = dn_tasks[bid]
                    s_changed = (sd['hash'] != last_hash);
                    d_changed = (dd['hash'] != last_hash)
                    if s_changed and not d_changed:
                        Logger.info(f"   🔄 S->D 同步 ({bid}):")
                        blk = self.reconstruct_daily_block(sd, target_date)
                        dn_lines[dd['idx']:dd['idx'] + dd['len']] = blk
                        dn_mod = True
                        self.sm.update_task(bid, sd['hash'], sd['path'], target_date)
                    elif d_changed and not s_changed:
                        Logger.info(f"   🔄 D->S 同步 ({bid}):")
                        n_l = self.format_line(sd['indent'], dd['status'], dd['pure'], target_date, sd['fname'], bid,
                                               False)
                        # [MODIFIED] Pass source_parent_indent (using daily indent)
                        blk = [n_l] + self.normalize_child_lines(dd['raw'][1:], sd['indent'],
                                                                 source_parent_indent=dd['indent'], as_quoted=False)
                        if sd['path'] not in src_updates: src_updates[sd['path']] = {}
                        src_updates[sd['path']][bid] = blk
                        self.sm.update_task(bid, dd['hash'], sd['path'], target_date)
                    elif s_changed and d_changed:
                        if sd['hash'] != dd['hash']:
                            Logger.info(f"   ⚔️ 冲突 ({bid}): Daily 覆盖 Source")
                            n_l = self.format_line(sd['indent'], dd['status'], dd['pure'], target_date, sd['fname'],
                                                   bid, False)
                            # [MODIFIED] Conflict resolution using Daily structure
                            blk = [n_l] + self.normalize_child_lines(dd['raw'][1:], sd['indent'],
                                                                     source_parent_indent=dd['indent'], as_quoted=False)
                            if sd['path'] not in src_updates: src_updates[sd['path']] = {}
                            src_updates[sd['path']][bid] = blk
                            self.sm.update_task(bid, dd['hash'], sd['path'], target_date)

                        else:
                            # [Fixed] 状态稳定时仅更新心跳，不触发文件写入
                            # if sd['path'] not in src_updates: src_updates[sd['path']] = {}
                            # src_updates[sd['path']][bid] = sd['raw']
                            self.sm.update_task(bid, sd['hash'], sd['path'], target_date)
                else:
                    if last_date == target_date:
                        Logger.info(f"   🗑️ 删除 Source ({bid}): 因 Daily 移除")
                        if sd['path'] not in src_deletes: src_deletes[sd['path']] = {}
                        src_deletes[sd['path']][bid] = sd['path']
                        self.sm.remove_task(bid)
                    else:
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
                dd = dn_tasks[bid];
                raw_first = dd['raw'][0]
                db_data = self.sm.state.get(bid, {})
                last_path = db_data.get('source_path', '')
                is_daily_native = (not last_path) or (Config.DAILY_NOTE_DIR in last_path)
                target_file_direct = self.extract_routing_target(raw_first)
                is_deleted_from_source = False
                if target_file_direct and last_path:
                    p1 = os.path.normcase(os.path.abspath(target_file_direct))
                    p2 = os.path.normcase(os.path.abspath(last_path))
                    if p1 == p2: is_deleted_from_source = True
                should_push = (bid in organized_bids) or is_daily_native or (
                        target_file_direct and os.path.exists(target_file_direct) and not is_deleted_from_source)
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

                        # [MODIFIED] Use visual depth
                        raw_indent = self._get_indent_depth(raw_no_quote)

                        n_l = self.format_line(raw_indent, dd['status'], clean, target_date, fname, bid, False)

                        # [MODIFIED] Pass source_parent_indent using dd['indent']
                        blk = [n_l] + self.normalize_child_lines(dd['raw'][1:], raw_indent,
                                                                 source_parent_indent=dd['indent'], as_quoted=False)

                        if target_file not in src_updates: src_updates[target_file] = {}
                        src_updates[target_file][bid] = blk
                        self.sm.update_task(bid, dd['hash'], target_file, target_date)
                    else:
                        Logger.info(f"   ⚠️ [ORPHAN] 无法同步，找不到目标文件")
                else:
                    Logger.info(f"   🗑️ 删除 Daily ({bid}): 因 Source 移除")
                    for k in range(dd['idx'], dd['idx'] + dd['len']): dn_lines[k] = None
                    dn_mod = True

        if dn_mod:
            # [CRITICAL FIX] 写入日记文件前的幂等性检查
            final_dn_lines = [l for l in dn_lines if l is not None]
            original_dn_content = FileUtils.read_content(daily_path) or ""
            new_dn_content = "".join(final_dn_lines)

            if original_dn_content != new_dn_content:
                FileUtils.write_file(daily_path, final_dn_lines)
                Logger.info(f"   ✅ 日记文件已回写: {os.path.basename(daily_path)}")

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
                        _, c = self.capture_block(sl, i);
                        i += c;
                        chg = True
                    else:
                        out.append(sl[i]);
                        i += 1
                if chg:
                    stem = os.path.splitext(os.path.basename(path))[0]
                    out = self.inject_into_task_section(out, [], stem)

                    # [FIX] 显式比对
                    orig_content = "".join(sl)
                    new_content = "".join(out)
                    if orig_content != new_content:
                        # === 🎯 第二次日志修改 (Delete) ===
                        Logger.info(f"   💾 [WRITE] 写入源文件 (Delete) (from {target_date}): {os.path.basename(path)}")
                        FileUtils.write_file(path, out)

        if src_updates:
            for path, ups in src_updates.items():
                sl = FileUtils.read_file(path)
                if not sl: sl = []
                out, i, chg = [], 0, False
                handled_bids = set()
                while i < len(sl):
                    im = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', sl[i])
                    if not im: im = re.search(r'\(connect::.*?\^([a-zA-Z0-9]{6,})\)', sl[i])
                    if im and im.group(1) in ups:
                        bid = im.group(1)
                        _, c = self.capture_block(sl, i)
                        out.extend(ups[bid])
                        handled_bids.add(bid)
                        i += c;
                        chg = True
                    else:
                        out.append(sl[i]);
                        i += 1
                pending_inserts = []
                for bid, blk in ups.items():
                    if bid not in handled_bids: pending_inserts.extend(blk); chg = True

                if chg:
                    stem = os.path.splitext(os.path.basename(path))[0]
                    out = self.inject_into_task_section(out, pending_inserts, stem)

                    # [FIX] 显式比对，防止死循环
                    orig_content = "".join(sl)
                    new_content = "".join(out)

                    if orig_content != new_content:
                        # === 🎯 第三次日志修改 (Update/Insert) - 你的主要需求 ===
                        Logger.info(
                            f"   💾 [WRITE] 写入源文件 (Update/Insert) (from {target_date}): {os.path.basename(path)}")
                        FileUtils.write_file(path, out)
                        self.trigger_delayed_verification(path)

        self.sm.save()