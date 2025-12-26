import re
import os
import hashlib
import difflib
import unicodedata  # [NEW] 引入 unicode 支持
from config import Config
from .utils import FileUtils, Logger


class FormatCore:
    @staticmethod
    def _enforce_hyphen_space(line: str, context: str = "", filename: str = "") -> str:
        return line

    @staticmethod
    def normalize_indentation(content: str) -> str:
        return re.sub(r'(?m)^( +)', lambda m: m.group(1).replace('    ', '\t'), content)

    @staticmethod
    def auto_format_links(content: str) -> str:
        # [FIX] Escape brackets properly to avoid "nested set" warning
        pattern = r'(?<![\[\(\<])(https?://([^/\s\n]+)(?:/[^\s\n]*)?)'

        def _replacer(match): return f"[{match.group(2)}]({match.group(1)})"

        return re.sub(pattern, _replacer, content)

    @staticmethod
    def format_image_links(content: str) -> str:
        ext_pattern = re.compile(r'\.(png|jpe?g|gif|bmp|svg|pdf)$', re.IGNORECASE)

        def _replacer(match):
            inner = match.group(1)
            base = inner.split('|')[0]
            if ext_pattern.search(base): return f"![[{base}{Config.IMAGE_PARAM_SUFFIX}]]"
            return match.group(0)

        return re.sub(r'!\[\[([^\]]+)\]\]', _replacer, content)

    @staticmethod
    def sanitize_markdown_links(content: str) -> str:
        invalid_chars = r'[\\:]'

        def _clean_wiki(m): return f"[[{re.sub(invalid_chars, '', m.group(1)).strip()}]]"

        content = re.sub(r'\[\[(.*?)\]\]', _clean_wiki, content)

        def _clean_std(m): return f"[{re.sub(invalid_chars, '', m.group(1)).strip()}]({m.group(2)})"

        return re.sub(r'\[([^\]]+?)\]\(([^)]+?)\)', _clean_std, content)

    @staticmethod
    def get_header_sorting_key(title_line: str) -> str:
        """
        [FIX] 修复中文标题被过滤为空字符串导致排序混乱的问题
        """
        # 1. 移除 Markdown 标记 (#, [[, ]])
        clean_title = re.sub(r'[#\[\]]', '', title_line).strip().lower()
        # 2. 如果清理后不为空，直接使用；否则（纯符号标题）使用原字符串
        # 这样确保 "测试" 和 "调试" 有不同的 Key
        return clean_title if clean_title else title_line.strip()

    @staticmethod
    def _extract_sort_key(block_lines: list) -> tuple:
        """
        [SyncCore 一致性保证]
        严格对齐 SyncCore 的 _calculate_sort_key 逻辑
        返回: (has_time_bool, time_val, block_id)
        """
        if not block_lines: return (1, "99:99", "zzzzzz")
        first_line = block_lines[0].strip()

        # 1. Block ID
        id_match = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', first_line)
        bid = id_match.group(1) if id_match else "zzzzzz"

        # 2. Time
        time_match = re.search(r'(\d{1,2}:\d{2})', first_line)
        if time_match:
            has_time = 0  # 有时间排前面
            time_val = time_match.group(1).zfill(5)
        else:
            has_time = 1  # 无时间排后面
            time_val = "99:99"

        return (has_time, time_val, bid)

    @classmethod
    def sort_day_planner_content(cls, content: str) -> str:
        if not content.strip(): return ""
        lines = content.split('\n')
        preamble = []
        blocks = []
        current_block = []
        in_task_block = False

        # [FIX] 仅匹配行首顶格的任务作为块的起点 (移除 ^[\t\s]*)
        # 这样缩进的子任务、图片会作为"内容"留在当前块中，不会被拆分
        task_start_pattern = re.compile(r'^-\s+\[[xX\s]\]')

        for line in lines:
            is_task_start = bool(task_start_pattern.match(line))
            if is_task_start:
                if current_block: blocks.append(current_block)
                current_block = [line]
                in_task_block = True
            elif in_task_block:
                # 遇到空行或分隔符才结束当前块
                if line.strip() == "" or line.strip().startswith('---'):
                    if current_block: blocks.append(current_block)
                    current_block = []
                    in_task_block = False
                    if line.strip(): preamble.append(line)
                else:
                    current_block.append(line)
            else:
                preamble.append(line)

        if current_block: blocks.append(current_block)

        # 排序 (使用更新后的 Key)
        sorted_blocks = sorted(blocks, key=cls._extract_sort_key)

        output = []
        p_text = "\n".join(preamble).strip()
        if p_text: output.append(p_text)

        for blk in sorted_blocks:
            # 块内部使用单换行拼接，保持紧凑
            blk_text = "\n".join(blk).rstrip()
            output.append(blk_text)

        # 块之间使用双换行拼接 (顶层任务之间留空)
        return "\n\n".join(output).strip()

    @classmethod
    def sort_markdown_sections(cls, text: str, filename: str = "") -> str:
        if not text.strip(): return text

        sections = re.split(r'^(#\s.*)$', text.strip(), flags=re.MULTILINE)
        output = []

        start_idx = 0
        if sections and not sections[0].startswith('#'):
            output.append(sections[0].strip())
            start_idx = 1

        i = start_idx
        while i < len(sections):
            title = sections[i].strip() if i < len(sections) else ""
            content = sections[i + 1] if i + 1 < len(sections) else ""

            l1_key = cls.get_header_sorting_key(title)
            is_target_section = "dayplanner" in l1_key or "journey" in l1_key

            # [FIX] 使用 unicodedata.normalize 确保内容处理的一致性
            sub_blocks = re.split(r'^(##\s.*)$', content, flags=re.MULTILINE)

            processed_sub_sections = []

            pre_l2 = sub_blocks[0].strip()
            if pre_l2:
                if is_target_section:
                    processed_sub_sections.append(cls.sort_day_planner_content(pre_l2))
                else:
                    processed_sub_sections.append(pre_l2)

            j = 1
            while j < len(sub_blocks):
                l2_title = sub_blocks[j].strip()
                l2_content = sub_blocks[j + 1].strip() if j + 1 < len(sub_blocks) else ""

                final_l2_content = ""
                if l2_content:
                    if is_target_section:
                        final_l2_content = cls.sort_day_planner_content(l2_content)
                    else:
                        final_l2_content = l2_content

                if final_l2_content:
                    processed_sub_sections.append(f"{l2_title}\n\n{final_l2_content}")
                else:
                    processed_sub_sections.append(l2_title)

                j += 2

            full_section_content = "\n\n".join(processed_sub_sections).strip()

            if full_section_content:
                output.append(f"{title}\n\n{full_section_content}")
            else:
                output.append(title)

            i += 2

        return "\n\n".join(output).strip()

    @staticmethod
    def _log_diff(step_name: str, old_content: str, new_content: str):
        if old_content == new_content: return
        if Config.DEBUG_MODE:
            d = difflib.Differ()
            diff = list(d.compare(old_content.splitlines(), new_content.splitlines()))
            changed_lines = [line.strip() for line in diff if line.startswith('+ ') or line.startswith('- ')]
            if len(changed_lines) > 0:
                Logger.debug(f"=== [{step_name}] Format Changes ===")
                for l in changed_lines[:5]: Logger.debug(l)

    @classmethod
    def execute(cls, filepath: str) -> bool:
        if not os.path.exists(filepath): return False
        content = FileUtils.read_content(filepath)
        if not content: return False

        # [CRITICAL] 1. 立即强制 NFC 标准化
        # 这一步是为了消除 macOS NFD 文件名和 Python 字符串之间的隐形差异
        content = unicodedata.normalize('NFC', content)

        orig_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

        # Step 2: 标准化处理
        c = cls.normalize_indentation(content)
        c = cls.auto_format_links(c)
        c = cls.sanitize_markdown_links(c)
        c = cls.format_image_links(c)

        # Step 3: 排序与排版
        fname = os.path.basename(filepath)
        prev_text = c
        c = cls.sort_markdown_sections(c, filename=fname)

        cls._log_diff("FormatCore", prev_text, c)

        c = c.strip() + "\n"
        new_hash = hashlib.md5(c.encode('utf-8')).hexdigest()

        if orig_hash != new_hash:
            Logger.info(f"✨ [Format] 优化日记排版与间距: {fname}")
            return FileUtils.write_file(filepath, c)
        return False

    @staticmethod
    def fix_broken_tab_bullets_global():
        if not os.path.exists(Config.DAILY_NOTE_DIR): return
        pattern = re.compile(r'(?m)^(\t+)-(?![ \t])')
        for filename in os.listdir(Config.DAILY_NOTE_DIR):
            if not filename.endswith('.md'): continue
            filepath = os.path.join(Config.DAILY_NOTE_DIR, filename)
            try:
                content = FileUtils.read_content(filepath)
                if not content: continue
                new_content = pattern.sub(r'\1- ', content)
                if new_content != content:
                    FileUtils.write_file(filepath, new_content)
                    Logger.info(f"🔧 [Fix] 修复列表缩进格式: {filename}")
            except Exception as e:
                Logger.debug(f"Global Fix Error {filename}: {e}")
