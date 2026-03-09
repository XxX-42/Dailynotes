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
        [vX] 剥离尾部的百分比数值（如 %100），防止标题名变化引发分类组重复扩散
        """
        # 0. 剥离进度标识符（百分比）
        title_line = re.sub(r'(?:\s+\d+%)+[ \t]*$', '', title_line)
        
        # 1. 移除 Markdown 标记 (#, [[, ]])
        clean_title = re.sub(r'[#\[\]]', '', title_line).strip().lower()
        # 2. 如果清理后不为空，直接使用；否则（纯符号标题）使用原字符串
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
        p_text = cls._safe_strip("\n".join(preamble))
        if p_text: output.append(p_text)

        for blk in sorted_blocks:
            # 块内部使用单换行拼接，保持紧凑
            # [FIX] 使用 _safe_strip 而非 rstrip，保留行尾有意义的空格
            blk_text = cls._safe_strip("\n".join(blk))
            output.append(blk_text)

        # 块之间使用双换行拼接 (顶层任务之间留空)
        return cls._safe_strip("\n\n".join(output))

    @staticmethod
    def _safe_strip(content: str) -> str:
        """
        [FIX] 安全的 strip：只移除首尾的空白行，不移除行内尾部空格
        这样可以保留 Obsidian 列表语法 "- " 中的空格
        """
        if not content:
            return content
        lines = content.split('\n')
        # 移除首部空行
        while lines and not lines[0].strip():
            lines.pop(0)
        # 移除尾部空行
        while lines and not lines[-1].strip():
            lines.pop()
        return '\n'.join(lines)

    @classmethod
    def sort_markdown_sections(cls, text: str, filename: str = "") -> str:
        if not text.strip(): return text

        sections = re.split(r'^(#\s.*)$', cls._safe_strip(text), flags=re.MULTILINE)
        output = []

        start_idx = 0
        if sections and not sections[0].startswith('#'):
            output.append(cls._safe_strip(sections[0]))
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

            pre_l2 = cls._safe_strip(sub_blocks[0])
            if pre_l2:
                if is_target_section:
                    processed_sub_sections.append(cls.sort_day_planner_content(pre_l2))
                else:
                    processed_sub_sections.append(pre_l2)

            j = 1
            while j < len(sub_blocks):
                l2_title = sub_blocks[j].strip()
                l2_content = cls._safe_strip(sub_blocks[j + 1]) if j + 1 < len(sub_blocks) else ""

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

            full_section_content = cls._safe_strip("\n\n".join(processed_sub_sections))

            if full_section_content:
                output.append(f"{title}\n\n{full_section_content}")
            else:
                output.append(title)

            i += 2

        # [FIX] 智能拼接：如果第一个元素是 YAML frontmatter，则用单换行连接
        # YAML frontmatter 以 "---" 开头，其后应紧跟标题而非空行
        if output and len(output) >= 2 and output[0].strip().startswith('---'):
            # Frontmatter + 单换行 + 其余内容（双换行分隔）
            frontmatter = output[0]
            rest = "\n\n".join(output[1:])
            return cls._safe_strip(f"{frontmatter}\n{rest}")
        
        return cls._safe_strip("\n\n".join(output))

    @classmethod
    def update_progress_percentage(cls, content: str) -> str:
        """
        [vX] 自动基于最深任务（叶子节点）打卡状态计算上级与根项目（### 标题）的进度比率。
        """
        lines = content.splitlines()
        
        # [ICE加权] 前置步骤：从 Insights 表格解析 ICE Score 映射
        ice_map = cls._parse_ice_scores(content)
        
        class Node:
            def __init__(self, idx, indent, text, is_header):
                self.idx = idx
                self.indent = indent
                self.text = text
                self.children = []
                self.is_header = is_header
                self.is_task = text.lstrip().startswith("- [")
                self.is_checked = "[x]" in text.lower() if self.is_task else False

        forest = []
        stack = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            # [MOD] 增加对 ## Archive 的识别，使其参与汇总
            if stripped.startswith("## Archive"):
                # 二级标题深度设为 -2，使其成为 ### (深度-1) 的父级
                node = Node(i, -2, line, is_header=True)
                forest.append(node)
                stack = [(-2, node)]
            elif line.startswith("### "):
                node = Node(i, -1, line, is_header=True)
                # 如果栈里有 ## Archive，则作为其子节点
                while stack and stack[-1][0] >= -1:
                    stack.pop()
                if stack:
                    stack[-1][1].children.append(node)
                else:
                    forest.append(node)
                stack.append((-1, node))
            elif stripped.startswith("- ["):
                indent_match = re.match(r'^([ \t]*)- \[[xX\s]\]', line)
                if indent_match:
                    indent = len(indent_match.group(1).replace('\t', '    '))
                    node = Node(i, indent, line, is_header=False)
                    
                    while stack and stack[-1][0] >= indent:
                        stack.pop()
                    
                    if stack:
                        stack[-1][1].children.append(node)
                    else:
                        forest.append(node)
                    
                    stack.append((indent, node))
            else:
                pass 

        def get_stats(node):
            # 时间统计累加器
            node_time_mins = 0
            
            # 提取自身可能包含的时间段 (hh:mm - hh:mm)
            if node.is_task:
                tm = re.search(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})', node.text)
                if tm:
                    t_start, t_end = tm.groups()
                    try:
                        h1, m1 = map(int, t_start.split(':'))
                        h2, m2 = map(int, t_end.split(':'))
                        mins = (h2 * 60 + m2) - (h1 * 60 + m1)
                        if mins < 0: mins += 24 * 60
                        node_time_mins += mins
                    except:
                        pass
                        
            if not node.is_task and not node.children:
                return (0, 0, 0)
            if node.is_task and not node.children:
                return (1, 1 if node.is_checked else 0, node_time_mins)
                
            total, checked, total_mins = 0, 0, node_time_mins
            for child in node.children:
                t, c, mins = get_stats(child)
                total += t
                checked += c
                total_mins += mins
            return (total, checked, total_mins)
            
        updates = {}
        # 为了给外部报表提供数据，挂载节点对象的信息
        cls._last_calculated_costs = getattr(cls, '_last_calculated_costs', {})
        cls._last_calculated_costs.clear()
        
        def traverse(node):
            total, checked, total_mins = get_stats(node)
            # 剥开可能遗留的百分比数值
            # 支持旧格式: "Text 100%"
            # 支持新格式: "[[...|⮐ 100%]]"
            base_text = re.sub(r'(?:\s+\d+%)+[ \t]*$', '', node.text)
            # 针对新格式的剥离：将 [[...|⮐ 100%]] 还原为 [[...|⮐]]
            base_text = re.sub(r'(\|⮐)\s+\d+%', r'\1', base_text)
            
            # [FIX] 反向链接去重：如果同一个 [[xxx#^bid|⮐]] 出现多次，只保留第一个
            seen_backlinks = set()
            def _dedup_backlink(m):
                link = m.group(0)
                if link in seen_backlinks:
                    return ''  # 删除重复的
                seen_backlinks.add(link)
                return link
            base_text = re.sub(r'\[\[[^\]]+\|⮐\]\]', _dedup_backlink, base_text)
            base_text = re.sub(r'\s{2,}', ' ', base_text)  # 清理多余空格
            
            if total > 0 and node.children:
                # [ICE加权 v4.4] 逐任务独立加权：通过 block ID 查找每个任务的 ICE 分数
                if node.is_header and ice_map:
                    weighted_sum = 0
                    weight_total = 0
                    
                    def collect_weighted_tasks(n):
                        nonlocal weighted_sum, weight_total
                        if n.is_task:
                            t, c, _ = get_stats(n)
                            if t > 0:
                                # 尝试从 span id 提取 block ID
                                bid_m = re.search(r'<span id="([a-zA-Z0-9]{6,})"', n.text)
                                block_id = bid_m.group(1) if bid_m else None
                                
                                # 查找权重：优先 block ID，其次文件名，默认 1
                                weight = 1
                                if block_id and block_id in ice_map:
                                    weight = ice_map[block_id]
                                else:
                                    link_m = re.search(r'\[\[(.*?)(?:[#|])', n.text)
                                    link = link_m.group(1).strip() if link_m else None
                                    if link and link in ice_map:
                                        weight = ice_map[link]
                                
                                task_pct = c / t
                                weighted_sum += task_pct * weight
                                weight_total += weight
                        else:
                            for ch in n.children:
                                collect_weighted_tasks(ch)
                    
                    collect_weighted_tasks(node)
                    
                    if weight_total > 0:
                        pct = int(round(weighted_sum / weight_total * 100))
                    else:
                        pct = int(round(checked / total * 100))
                else:
                    pct = int(round(checked / total * 100))
                
                # [新功能] 寻找 [[测试aaa#^2qss78|⮐]] 这种反向链接语法
                # 如果存在，则把百分比塞进链接文字里，形如 [[...|⮐ 67%]]
                backlink_pattern = r'(\[\[[^\]]+\|⮐)\]\]'
                if node.is_task and re.search(backlink_pattern, base_text):
                    updates[node.idx] = re.sub(backlink_pattern, rf'\1 {pct}%]]', base_text)
                else:
                    updates[node.idx] = f"{base_text.rstrip()} {pct}%"
                
                # 记录对于顶级标题级项目的 cost
                if node.is_header:
                    m_title = re.search(r'\[\[(.*?)\]\]', base_text)
                    if m_title:
                        cls._last_calculated_costs[m_title.group(1).split('|')[0]] = total_mins
            elif node.is_header or node.is_task:
                # 已经是独立的、没有子任务的项，去除了旧百分比，恢复原状
                updates[node.idx] = base_text
                
            for child in node.children:
                traverse(child)

        for f in forest:
            traverse(f)
        
        new_lines = []
        for i, line in enumerate(lines):
            if i in updates:
                new_lines.append(updates[i])
            else:
                new_lines.append(line)
        
        return "\n".join(new_lines)

    @staticmethod
    def _parse_ice_scores(content: str) -> dict:
        """
        [ICE加权] 从 ## Insights 表格中萃取 ICE Score 映射。
        返回: {项目名(str): ICE数值(float)}
        """
        lines = content.splitlines()
        ice_map = {}
        in_insights = False
        rows_seen = 0
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## "):
                if stripped.replace(" ", "") == "##Insights":
                    in_insights = True
                    rows_seen = 0
                    continue
                elif in_insights:
                    break
            
            if in_insights and stripped.startswith("|"):
                rows_seen += 1
                if rows_seen <= 2:
                    continue  # 跳过表头和分隔线
                
                # [v4.3] 使用链接感知的切分，避免 [[xxx\|yyy]] 中的 | 被错误切割
                parts = []
                last = 0
                for match in re.finditer(r'\[\[.*?\]\]', stripped):
                    parts.append(stripped[last:match.start()])
                    parts.append(match.group(0).replace('|', '\x00'))
                    last = match.end()
                parts.append(stripped[last:])
                processed = "".join(parts)
                cols = [c.replace('\x00', '|').strip() for c in processed.split('|')[1:-1]]
                
                if len(cols) >= 8:
                    # 规范化项目名：去掉 [[]]、去掉 \| 的反斜杠
                    proj_name = re.sub(r'[\[\]]', '', cols[0]).replace('\\|', '|').strip()
                    ice_raw = cols[7]
                    # 萃取 HTML/Markdown 中的纯数字 (如 <font color='red'>**16**</font>)
                    m = re.search(r'(\d+(?:\.\d+)?)', ice_raw)
                    if m and proj_name:
                        score = float(m.group(1))
                        ice_map[proj_name] = score
                        # [v4.4] 同时按 block ID 存储，让逐任务加权能通过 span id 查找
                        bid_m = re.search(r'#\^([a-zA-Z0-9]{6,})', cols[0])
                        if bid_m:
                            ice_map[bid_m.group(1)] = score
        
        return ice_map

    @classmethod
    def update_insights_table(cls, content: str, instant: bool = False) -> str:
        """
        [vX] 自动扫描 `## Archive` 下的三级标题及其进度，将其映射更新到 `## Insights` 的表格中。
        """
        # 1. 扫描出所有的统计数据，放开视野限制，遍历全文所有 `### [[xxx]]`
        lines = content.splitlines()
        
        archive_projects = {}
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("### "):
                continue # 禁止将三级标题本身作为项目计入 Insights
            elif stripped.lstrip().startswith("- ["):
                # [FIX] 如果存在散养任务，但带有独立的主键id，也抓进 Insights 表格中
                id_m = re.search(r'<span id="([a-zA-Z0-9]{6,})"', stripped)
                if id_m:
                    # [v4.2] 提取时间跨度 (HH:mm - HH:mm) 并计算 cost 时长
                    cost_str = ""
                    time_m = re.search(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})', stripped)
                    if time_m:
                        try:
                            t1, t2 = time_m.group(1), time_m.group(2)
                            def _to_m(s):
                                h, m = map(int, s.split(':'))
                                return h * 60 + m
                            diff = _to_m(t2) - _to_m(t1)
                            if diff < 0: diff += 24 * 60 # 跨天
                            cost_str = f"{diff // 60:02d}:{diff % 60:02d}"
                        except: pass

                    m_pct = re.search(r'(\d+)%$', stripped)
                    if m_pct:
                        pct = m_pct.group(1) + "%"
                    else:
                        is_checked = "[x]" in stripped.lower()
                        pct = "100%" if is_checked else "0%"
                        
                    content = re.sub(r'^[ \t]*- \[[xX\s]\]\s*', '', stripped)
                    # [v4.2] 移除时间前缀，让 id 列变干净
                    content = re.sub(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*', '', content)
                    content = re.sub(r'<span id="[a-zA-Z0-9]{6,}"></span>\s*', '', content)
                    content = re.sub(r'\s*\d+%$', '', content)
                    
                    pattern = r'\[\[(.*?)#\^([a-zA-Z0-9]{6,})\|⮐.*?\]\](?:\s*\[\[\1\]\])?'
                    def repl(m):
                        file_name = m.group(1).strip()
                        return f"[[{file_name}#^{m.group(2)}|{file_name}]]"
                    
                    display_label = re.sub(pattern, repl, content).strip()
                    
                    # 无论它原先带不带转义或⮐，统一强制将内嵌 | 转换为 \| 格式以兼容 Obsidian Table
                    def _force_escape_pipe(tm):
                        inner = tm.group(1).replace('\\|', '|').replace('|', '\\|')
                        return f"[[{inner}]]"
                    display_label = re.sub(r'\[\[(.*?)\]\]', _force_escape_pipe, display_label)
                    
                    archive_projects[display_label] = {"pct": pct, "cost": cost_str}
                    
        if not archive_projects:
            return content
            
        # 2. 寻找与替换 Insights 区域中的表格
        in_insights = False
        in_table = False
        table_start_idx = -1
        table_end_idx = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("## "):
                if stripped.replace(" ", "") == "##Insights":
                    in_insights = True
                else:
                    if in_insights and in_table:
                        table_end_idx = i
                        break
                    in_insights = False
            elif in_insights:
                if stripped.startswith("|"):
                    if not in_table:
                        table_start_idx = i
                        in_table = True
                else:
                    if in_table and stripped == "":
                         table_end_idx = i
                         break
                    
        # 如果达到了文件尾部仍未找到终点
        if in_table and table_end_idx == -1:
            table_end_idx = len(lines)
            
        if table_start_idx != -1 and table_end_idx != -1:
            
            def _split_table_row(r_text: str) -> list:
                # 暂时把 [[...|...]] 里的 '|' 替换掉以免被切割
                parts = []
                last = 0
                for match in re.finditer(r'\[\[.*?\]\]', r_text):
                    parts.append(r_text[last:match.start()])
                    parts.append(match.group(0).replace('|', '\x00'))
                    last = match.end()
                parts.append(r_text[last:])
                processed = "".join(parts)
                # 切割后恢复
                return [c.replace('\x00', '|').strip() for c in processed.split('|')[1:-1]]

            # 提取现有的表格保留 id(项目名)、cost、aim to 等手工字段
            old_table_lines = lines[table_start_idx:table_end_idx]
            old_data_map = {}
            header = []
            divider = []
            
            for row in old_table_lines:
                if not row.strip().startswith('|'): continue
                cols = _split_table_row(row)
                if not cols: continue
                
                if not header:
                    header = cols
                elif not divider:
                    divider = cols
                else:
                    # Data row
                    if len(cols) > 0 and cols[0]:
                         # 第一列默认为 id / project name
                         proj_name_cleaned = re.sub(r'[\[\]]', '', cols[0]).strip()
                         old_data_map[proj_name_cleaned] = cols
                         
            # 重新构建表格内容
            new_table_lines = []
            
            # [行内刷新逻辑] 动态检查旧表头是否可用，保留排版以防 Obsidian 无限格式化死循环
            if len(old_table_lines) >= 2 and old_table_lines[0].count('|') >= 9:
                new_table_lines.append(old_table_lines[0])
                new_table_lines.append(old_table_lines[1])
            else:
                new_header = ["id", "cost", "aim to", "progress", "Impact", "Confidence", "Ease", "ICE Score", "complete"]
                new_table_lines.append("| " + " | ".join(new_header) + " |")
                new_table_lines.append("| --- | ---- | ------ | -------- | ------ | ---------- | ---- | --------- | -------- |")
            
             # 使用 Archive 扫描到的数据为主键遍历
            for display_label, data_obj in archive_projects.items():
                pct = data_obj["pct"]
                captured_cost = data_obj["cost"]
                # [v4.3] 规范化 clean_proj：去掉 [[]]、去掉 \| 的反斜杠，用于松散匹配
                clean_proj = re.sub(r'[\[\]]', '', display_label).replace('\\|', '|').strip()
                
                # 寻找旧表中的对应行，以便尽量复用它的空格
                old_row_line = None
                old_cols = []
                for row in old_table_lines[2:]:
                    if not row.strip().startswith('|'): continue
                    cols_tmp = _split_table_row(row)
                    if cols_tmp:
                        # [v4.3] 同样规范化：去掉 [[]]、去掉 \| 的反斜杠
                        row_key = re.sub(r'[\[\]]', '', cols_tmp[0]).replace('\\|', '|').strip()
                        if row_key == clean_proj:
                            old_row_line = row
                            old_cols = cols_tmp
                            break
                        
                if not old_cols:
                    old_cols = []
                
                # 更新传承或覆盖旧的手工数据
                # 优先级: 抓取到的 cost > 统计计算的 cost > 旧表数据
                if captured_cost:
                    cost = captured_cost
                else:
                    cost_mins = cls._last_calculated_costs.get(clean_proj, 0) if hasattr(cls, '_last_calculated_costs') else 0
                    if cost_mins > 0:
                        cost = f"{cost_mins // 60:02d}:{cost_mins % 60:02d}"
                    else:
                        cost = old_cols[1] if len(old_cols) > 1 else ""
                    
                aim = old_cols[2] if len(old_cols) > 2 else ""
                
                # 构建进度列
                progress_col = ""
                if pct:
                    pct_val = pct.replace('%', '')
                    progress_col = f"{pct_val}%"
                
                # 读取新建的四个列（容错）
                impact_val = old_cols[4] if len(old_cols) > 4 else ""
                confidence_val = old_cols[5] if len(old_cols) > 5 else ""
                ease_val = old_cols[6] if len(old_cols) > 6 else ""
                
                # 尝试计算 ICE Score
                ice_score = ""
                i_str, c_str, e_str = impact_val.strip(), confidence_val.strip(), ease_val.strip()
                
                if instant:
                    # 即时更新模式下，不计算ICE，不抛出报错警告，避免影响打字体验
                    ice_score = old_cols[7] if len(old_cols) > 7 else ""
                else:
                    # 如果有任意一个填写了，我们就进行严格校验
                    if i_str or c_str or e_str:
                        try:
                            def _extract_score(text: str, name: str) -> float:
                                if not text: raise ValueError(f"缺{name}")
                                # 试图匹配文本中的第一个数字（允许小数点）
                                m = re.search(r'(\d+(?:\.\d+)?)', text)
                                if m: return float(m.group(1))
                                raise ValueError(f"{name}无数字")
                                
                            # 逐层萃取，即使夹杂长文章批注，我们也能把数字抠出来
                            i_val = _extract_score(i_str, "I")
                            c_val = _extract_score(c_str, "C")
                            e_val = _extract_score(e_str, "E")
                            
                            if not (1 <= i_val <= 10) or not (1 <= c_val <= 10) or not (1 <= e_val <= 10):
                                ice_score = "⚠️越界(1-10)"
                            else:
                                score_num = int(i_val * c_val * e_val)
                                # 使用 HTML font 标签渲染红色粗体
                                ice_score = f"<font color='red'>**{score_num}**</font>"
                        except ValueError as e:
                            # 抛出具体的缺失或异常错误原因代替死板的“数据无效”
                            ice_score = f"⚠️{str(e)}"
                    else:
                        ice_score = old_cols[7] if len(old_cols) > 7 else ""
                
                # 判断是否读取了 complete 列，旧表格可能没有该列
                old_complete = old_cols[8] if len(old_cols) > 8 else ""
                
                # 新增计算 complete 逻辑。默认如果 pct 达到 100% 则输出 ✅，否则输出 ❌或空，此处我们先设为空，您可以自行修改
                complete_val = "✅" if progress_col == "100%" else old_complete
                
                # === 判断是否发生实质性变动 ===
                old_cost = old_cols[1] if len(old_cols) > 1 else ""
                old_progress = old_cols[3] if len(old_cols) > 3 else ""
                old_impact = old_cols[4] if len(old_cols) > 4 else ""
                old_confidence = old_cols[5] if len(old_cols) > 5 else ""
                old_ease = old_cols[6] if len(old_cols) > 6 else ""
                old_ice_score = old_cols[7] if len(old_cols) > 7 else ""
                
                if old_row_line and cost == old_cost and progress_col == old_progress and impact_val == old_impact and confidence_val == old_confidence and ease_val == old_ease and ice_score == old_ice_score and complete_val == old_complete:
                    # 原行参数未变（无实质变更），复用旧行但确保链接内 | 已转义
                    def _escape_row_links(row_text):
                        def _esc(tm):
                            inner = tm.group(1).replace('\\|', '|').replace('|', '\\|')
                            return f"[[{inner}]]"
                        return re.sub(r'\[\[(.*?)\]\]', _esc, row_text)
                    new_table_lines.append(_escape_row_links(old_row_line))
                else:
                    # 如果这行真的需要刷新（例如你刚填入了 Ease 的值），就重组成精简紧凑的一行
                    # (下一次脚本再读此文件的时候就会变成无实质变更，从而停止修改死循环)
                    row_str = f"| {display_label} | {cost} | {aim} | {progress_col} | {impact_val} | {confidence_val} | {ease_val} | {ice_score} | {complete_val} |"
                    new_table_lines.append(row_str)
                
            # 执行文本替换
            new_content_lines = lines[:table_start_idx] + new_table_lines + lines[table_end_idx:]
            return "\n".join(new_content_lines)
            
        else:
            # === 如果表格甚至 Insights 标题不存在，我们自动生成 ===
            # 构建一个由底层向上渲染的全新空表格
            new_table_lines = []
            new_header = ["id", "cost", "aim to", "progress", "Impact", "Confidence", "Ease", "ICE Score", "complete"]
            new_table_lines.append("| " + " | ".join(new_header) + " |")
            new_table_lines.append("| --- | ---- | ------ | -------- | ------ | ---------- | ---- | --------- | -------- |")
            
            for display_label, data_obj in archive_projects.items():
                pct = data_obj["pct"]
                captured_cost = data_obj["cost"]
                clean_proj = re.sub(r'[\[\]]', '', display_label).strip()
                
                if captured_cost:
                    cost = captured_cost
                else:
                    cost_mins = cls._last_calculated_costs.get(clean_proj, 0) if hasattr(cls, '_last_calculated_costs') else 0
                    cost = f"{cost_mins // 60:02d}:{cost_mins % 60:02d}" if cost_mins > 0 else ""
                
                aim = ""
                progress_col = ""
                complete_val = ""
                if pct:
                    pct_val = pct.replace('%', '')
                    progress_col = f"{pct_val}%"
                    if progress_col == "100%":
                        complete_val = "✅"
                    
                row_str = f"| {display_label} | {cost} | {aim} | {progress_col} |  |  |  |  | {complete_val} |"
                new_table_lines.append(row_str)
            new_table_lines.append("") # 行尾空行缓冲
            
            insights_line_idx = -1
            log_line_idx = -1
            
            for i, line in enumerate(lines):
                stripped = line.strip().replace(" ", "")
                if stripped == "##Insights":
                    insights_line_idx = i
                elif stripped == "#Log":
                    log_line_idx = i
                    
            if insights_line_idx != -1:
                # 存在 Insights，无表，插入在下一行并且给足换行
                new_lines = lines[:insights_line_idx+1] + [""] + new_table_lines + [""] + lines[insights_line_idx+1:]
                return "\n".join(new_lines)
            elif log_line_idx != -1:
                # 存在 Log，无 Insights
                new_lines = lines[:log_line_idx+1] + ["", "## Insights", ""] + new_table_lines + [""] + lines[log_line_idx+1:]
                return "\n".join(new_lines)
            else:
                # 都没找到，作为顶级块附加
                new_lines = lines + ["", "# Log", "", "## Insights", ""] + new_table_lines + [""]
                return "\n".join(new_lines)
                
        return content

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
    def execute(cls, filepath: str, instant: bool = False) -> bool:
        if not os.path.exists(filepath): return False
        content = FileUtils.read_content(filepath)
        if not content: return False

        # [CRITICAL] 1. 立即强制 NFC 标准化
        # 这一步是为了消除 macOS NFD 文件名和 Python 字符串之间的隐形差异
        content = unicodedata.normalize('NFC', content)

        orig_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

        c = content

        if not instant:
            # Step 2: 标准化处理
            c = cls.normalize_indentation(c)
            c = cls.auto_format_links(c)
            c = cls.sanitize_markdown_links(c)
            c = cls.format_image_links(c)

            # Step 3: 排序与排版
            fname = os.path.basename(filepath)
            prev_text = c
            c = cls.sort_markdown_sections(c, filename=fname)

        # Step 4: 注入并计算任务深度的百分比进度
        c = cls.update_progress_percentage(c)
        
        # Step 5: 更新 Insights 数据报表
        c = cls.update_insights_table(c, instant=instant)

        if not instant:
            cls._log_diff("FormatCore", prev_text, c)

        c = c.strip() + "\n"
        new_hash = hashlib.md5(c.encode('utf-8')).hexdigest()

        if orig_hash != new_hash:
            tag = "Instant" if instant else "Format"
            Logger.info(f"✨ [{tag}] 优化日记排版与间距/进度更新: {os.path.basename(filepath)}")
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
