import re
import os
import hashlib
import difflib  # 新增引用用于比对行差异
from config import Config
from utils import FileUtils, Logger


class FormatCore:
    @staticmethod
    def _enforce_hyphen_space(line: str, context: str = "", filename: str = "") -> str:
        """
        [已阉割] 最初用于强制 "- " 格式，但导致了无限循环。
        现在委托给 'fix_broken_tab_bullets_global' 进行更安全的批处理。
        """
        return line

    @staticmethod
    def normalize_indentation(content: str) -> str:
        return re.sub(r'(?m)^( +)', lambda m: m.group(1).replace('    ', '\t'), content)

    @staticmethod
    def auto_format_links(content: str) -> str:
        pattern = r'(?<![\[\(\<])(https?://([^/\s\n]+)(?:/[^\s\n]*)?)'

        def _replacer(match):
            return f"[{match.group(2)}]({match.group(1)})"

        return re.sub(pattern, _replacer, content)

    @staticmethod
    def format_image_links(content: str) -> str:
        ext_pattern = re.compile(r'\.(png|jpe?g|gif|bmp|svg|pdf)$', re.IGNORECASE)

        def _replacer(match):
            inner = match.group(1)
            base = inner.split('|')[0]
            if ext_pattern.search(base):
                return f"![[{base}{Config.IMAGE_PARAM_SUFFIX}]]"
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
        return re.sub(r'[^a-zA-Z0-9]', '', title_line.lstrip('#')).lower()

    @classmethod
    def sort_day_planner_content(cls, content: str, context: str = "", filename: str = "") -> str:
        if not content.strip(): return ""
        lines = [line.rstrip('\n\r') for line in content.split('\n')]
        blocks = []
        preamble = []
        current_block = None
        task_start_pattern = re.compile(r'^-\s+\[[xX\s]\]')
        time_extract_pattern = re.compile(r'(\d{1,2}:\d{2})')

        for line in lines:
            if not line.strip(): continue

            # [暴力] 首先强制标准列表语法
            line = cls._enforce_hyphen_space(line, context=context, filename=filename)

            if task_start_pattern.match(line.strip()):
                if current_block: blocks.append(current_block)
                time_match = time_extract_pattern.search(line)
                sort_time = time_match.group(1).zfill(5) if time_match else None
                current_block = {'sort_key': sort_time, 'lines': [line]}
            else:
                if current_block:
                    current_block['lines'].append(line)
                else:
                    preamble.append(line)

        if current_block: blocks.append(current_block)
        timed = sorted([b for b in blocks if b['sort_key']], key=lambda x: x['sort_key'])
        untimed = [b for b in blocks if not b['sort_key']]

        output = []
        if preamble: output.append("\n".join(preamble))
        for b in untimed: output.append("\n".join(b['lines']))
        for b in timed: output.append("\n".join(b['lines']))
        return "\n\n".join(output).strip()

    @classmethod
    def sort_general_content(cls, content: str, context: str = "", filename: str = "") -> str:
        """
        [v6.10 Safe-Sort]
        修复了旧版对列表项进行字母排序导致父子结构被打乱的问题。
        现在仅按类型分组，但在组内严格保持原始行顺序。
        """
        if not content: return ""
        lines = [l.rstrip('\n\r') for l in content.split('\n') if l.strip()]
        if not lines: return ""

        # 1. 列表 (Tasks/Bullets)
        # 2. 编号列表
        # 3. 引用
        # 4. 普通文本
        groups = {1: [], 2: [], 3: [], 4: []}

        for line in lines:
            line = cls._enforce_hyphen_space(line, context=context, filename=filename)

            cleaned = line.strip()
            if cleaned.startswith(('- ', '* ')):
                k = 1
            elif re.match(r'^\d+', cleaned):
                k = 2
            elif cleaned.startswith('>'):
                k = 3
            else:
                k = 4
            groups[k].append(line)

        final = []
        sorted_keys = sorted(groups.keys())
        for k in sorted_keys:
            # [CRITICAL FIX] 移除了 groups[k].sort()
            # 保持用户输入的物理顺序，防止父子任务颠倒
            final.extend(groups[k])

            if k != sorted_keys[-1] and groups[k]:
                final.append("")

        return "\n".join(final).strip()

    @classmethod
    def sort_markdown_sections(cls, text: str, filename: str = "") -> str:
        if not text.strip(): return text
        sections = re.split(r'^(#\s.*)$', text.strip(), flags=re.MULTILINE)
        output = []
        i = 0
        if sections and not sections[0].startswith('#'):
            output.append(sections[0].strip())
            i = 1

        while i < len(sections):
            title = sections[i].strip() if i < len(sections) else ""
            content = sections[i + 1] if i + 1 < len(sections) else ""
            content = content.strip()
            l1_key = cls.get_header_sorting_key(title)
            is_planner = "dayplanner" in l1_key or "journey" in l1_key

            sub_blocks = re.split(r'^(##\s.*)$', content, flags=re.MULTILINE)
            pre_l2 = sub_blocks[0].strip()
            if pre_l2:
                if is_planner:
                    pre_l2 = cls.sort_day_planner_content(pre_l2, context=title, filename=filename)
                else:
                    pre_l2 = cls.sort_general_content(pre_l2, context=title, filename=filename)
                pre_l2 = pre_l2.strip()

            l2_blocks = []
            for j in range(1, len(sub_blocks), 2):
                if j + 1 < len(sub_blocks):
                    l2_t = sub_blocks[j].strip()
                    raw_c = sub_blocks[j + 1].strip()
                    l2_k = cls.get_header_sorting_key(l2_t)

                    if is_planner or "dayplanner" in l2_k:
                        l2_c = cls.sort_day_planner_content(raw_c, context=l2_t, filename=filename)
                    else:
                        l2_c = cls.sort_general_content(raw_c, context=l2_t, filename=filename)
                    l2_c = l2_c.strip()
                    l2_blocks.append((l2_t, l2_c))

            rebuilt = [title]
            if pre_l2: rebuilt.append(pre_l2)
            for t, c in l2_blocks:
                if c:
                    rebuilt.append(f"{t}\n\n{c}")
                else:
                    rebuilt.append(t)

            output.append("\n\n".join(rebuilt))
            i += 2
        return "\n\n".join(output).strip()

    @staticmethod
    def _log_diff(step_name: str, old_content: str, new_content: str):
        """
        [Helper] 仅在内容不同时，输出变更后的行。
        """
        if old_content == new_content:
            return

        # 使用 difflib 比较，生成差异流
        d = difflib.Differ()
        diff = list(d.compare(old_content.splitlines(), new_content.splitlines()))

        # 筛选：只获取以 '+ ' 开头的行（即修改后/新增的行），并去掉 '+ ' 前缀
        changed_lines = [line[2:] for line in diff if line.startswith('+ ')]

        if changed_lines:
            Logger.debug(f"=== [{step_name}] Modified Lines ===\n" + "\n".join(changed_lines))

    @classmethod
    def execute(cls, filepath: str) -> bool:
        if not os.path.exists(filepath): return False
        content = FileUtils.read_content(filepath)
        if not content: return False

        orig_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

        # Step 1: Normalize Indentation
        prev_text = content
        c = cls.normalize_indentation(content)
        cls._log_diff("normalize_indentation", prev_text, c)

        # Step 2: Auto Format Links
        prev_text = c
        c = cls.auto_format_links(c)
        cls._log_diff("auto_format_links", prev_text, c)

        # Step 3: Sanitize Markdown Links
        prev_text = c
        c = cls.sanitize_markdown_links(c)
        cls._log_diff("sanitize_markdown_links", prev_text, c)

        # Step 4: Format Image Links
        prev_text = c
        c = cls.format_image_links(c)
        cls._log_diff("format_image_links", prev_text, c)

        # Step 5: Sort Markdown Sections
        fname = os.path.basename(filepath)
        prev_text = c
        c = cls.sort_markdown_sections(c, filename=fname)
        cls._log_diff("sort_markdown_sections", prev_text, c)

        # 确保最后的换行符
        c = c.strip() + "\n"

        new_hash = hashlib.md5(c.encode('utf-8')).hexdigest()
        if orig_hash != new_hash:
            Logger.info(f"格式化生效，正在重写文件: {fname}")
            return FileUtils.write_file(filepath, c)
        return False

    @staticmethod
    def fix_broken_tab_bullets_global():
        r"""
        [全局修复] 全局扫描并修复 'Tab-Hyphen-NoSpace' 模式。
        """
        if not os.path.exists(Config.DAILY_NOTE_DIR): return

        pattern = re.compile(r'(?m)^(\t+)-(?!\s)')

        for filename in os.listdir(Config.DAILY_NOTE_DIR):
            if not filename.endswith('.md'): continue

            filepath = os.path.join(Config.DAILY_NOTE_DIR, filename)
            try:
                content = FileUtils.read_content(filepath)
                if not content: continue

                new_content = pattern.sub(r'\1- ', content)

                # Logger Output for Fix Global using Helper
                FormatCore._log_diff(f"Fix Global Tabs: {filename}", content, new_content)

                if new_content != content:
                    FileUtils.write_file(filepath, new_content)
                    Logger.info(f"全局修复幽灵列表项: {filename}")
            except Exception as e:
                Logger.debug(f"Global Fix Error {filename}: {e}")