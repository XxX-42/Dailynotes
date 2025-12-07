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
            # 使用 FileUtils 读取内容
            content = FileUtils.read_file(filepath) or []
            # 使用独特的标题记录日志
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
        # [修复] 保守清理：仅针对特定模式，避免过于激进的全行正则替换
        
        # 1. 移除指向自身的内部链接 (例如 [[filename|...]])
        if context_name:
             # 使用特定模式仅匹配 [[context_name|...]] 或 [[context_name]]
             # 注意不要匹配通用的 [[...]]
             line = re.sub(rf'\[\[{re.escape(context_name)}(?:\|.*?)?\]\]', '', line)

        # 2. 状态标记：移除 "- [ ] " 前缀
        line = re.sub(r'^[\s>]*-\s*\[.\]\s?', '', line)
        
        # 3. 块 ID：移除末尾的严格 ID
        # (已严格：空格 + ^ + 6-7 个字母数字 + 结尾)
        clean_text = line
        if block_id:
             # 仅在严格精确匹配时移除
             # 使用 re.split 可能更好，或者是简单的字符串替换？
             # 正则表达式对于边界处理更安全
             clean_text = re.sub(rf'(?<=\s)\^{re.escape(block_id)}\s*$', '', clean_text)
        
        # 4. 移除日期/连接符 (针对性)
        clean_text = re.sub(r'📅\s*\d{4}-\d{2}-\d{2}', '', clean_text)
        clean_text = re.sub(r'✅\s*\d{4}-\d{2}-\d{2}', '', clean_text)
        clean_text = re.sub(r'\(connect::.*?\)', '', clean_text)
        clean_text = re.sub(r'\[\[[^\]]*?\|[⮐📅]\]\]', '', clean_text) # 符号链接
        clean_text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}\]\]', '', clean_text) # 日期链接

        return clean_text.strip()

    def normalize_block_content(self, block_lines):
        normalized = []
        for line in block_lines:
            clean = re.sub(r'^[\s>]+', '', line).strip()
            # [修复] 幽灵子弹过滤器：忽略空行或仅有子弹点的行
            if not clean or clean in ['-', '- ']: continue
            normalized.append(clean)
        # [修复] 物理防粘连：使用换行符连接，防止 # 号被吞噬
        # 原逻辑：return "".join(normalized) -> 危险！
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
            # 计算缩进，忽略 '>' 前缀
            # 1. 去除 '>' 和可选空格
            no_quote = re.sub(r'^>\s?', '', s)
            # 2. 计算相对于干净字符串的前导空格
            return len(no_quote) - len(no_quote.lstrip())

        base_indent = get_indent(lines[start_idx])
        block = [lines[start_idx]]
        consumed = 1
        j = start_idx + 1
        while j < len(lines):
            nl = lines[j]
            
            # 规则 A: 原始行检查 (如果原始行就是 # Header，即使被引用逻辑处理前也应中止)
            if nl.lstrip().startswith('#'): break

            # 规则 B: 剥离引用符号 (> 和空白) 后的检查
            # 必须先剥离引用符号（>）和空白，以捕捉像 ">   # Header" 这样的情况
            stripped_check = re.sub(r'^[>\s]+', '', nl)
            
            # 规则 B.1: 深度标题检查
            if stripped_check.startswith('#'): break
            
            # 规则 C: 分隔符检查
            if stripped_check.startswith('---'): break

            # 空行是块的一部分吗？是的，如果有缩进或在块逻辑内部。
            # 但这里我们只检查它是否“相对于基准缩进”。
            # 对于空行，get_indent 可能是 0。
            if nl.strip() == "": 
                block.append(nl); consumed += 1; j += 1; continue
            
            if get_indent(nl) > base_indent:
                block.append(nl); consumed += 1; j += 1
            else:
                break
        return block, consumed
    def normalize_raw_tasks(self, lines, filename_stem):
        """
        自动注册：检测没有 ID 的原始任务 '> - [ ]' 并转换为标准格式。
        """
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

    def inject_into_callout(self, file_lines, block_lines, filename_stem=None):
        """
        重写，包含深度追踪日志和硬限制尾部逻辑。
        """
        # --- 1. 提取 YAML 并分割正文 ---
        yaml_lines = []
        body_lines = []
        if file_lines and file_lines[0].strip() == '---':
            yaml_lines.append(file_lines[0])
            for i in range(1, len(file_lines)):
                yaml_lines.append(file_lines[i])
                if file_lines[i].strip() == '---':
                    body_lines = file_lines[i+1:]
                    break
            else:
                yaml_lines = []
                body_lines = file_lines
        else:
            body_lines = file_lines

        # --- 2. 收割阶段 ---
        harvested_tasks = []
        clean_body = []
        default_header = "> [!note]- Tasks"
        captured_header = None
        
        # [补丁] 鲁棒的标题正则 (支持 > [!note], > [!note]-, > [!note]+)
        TASK_HEADER_PATTERN = re.compile(r"^>\s*\[!note\]([-+]?)\s+Tasks", re.IGNORECASE)
        
        i = 0
        while i < len(body_lines):
            line = body_lines[i]
            stripped = line.strip()
            
            # 情况 A: 现有 Callout (正则检测)
            match = TASK_HEADER_PATTERN.match(stripped)
            if match:
                if not captured_header:
                     captured_header = line.strip() # 保留找到的第一个标题
                i += 1
                while i < len(body_lines):
                    cl = body_lines[i]
                    if cl.strip().startswith('>'):
                         harvested_tasks.append(cl)
                         i += 1
                    elif cl.strip() == '':
                         # 宽松格式启发式
                         if i + 1 < len(body_lines) and body_lines[i+1].strip().startswith('>'):
                             harvested_tasks.append(cl)
                             i += 1
                         else:
                             break 
                    else:
                         break 
                continue

            # 情况 B: 孤立任务
            if re.match(r'^[\s]*-\s*\[.\]', line):
                 has_id = re.search(r'\^[a-zA-Z0-9]{6,}\s*$', line)
                 if has_id:
                     block, consumed = self.capture_block(body_lines, i)
                     harvested_tasks.extend(block)
                     i += consumed
                     continue
            
            # 情况 C: 普通文本
            clean_body.append(line)
            i += 1

        # 日志 1: 已收割
        if block_lines or harvested_tasks:
             Logger.debug(f"DeepTrace: Harvested {len(harvested_tasks)} existing, {len(block_lines)} new.")

        # --- 3. 标准化与去重 ---
        candidates = harvested_tasks + block_lines
        processed_candidates = []
        seen_ids = set()
        
        for line in candidates:
            clean_l = re.sub(r'^>\s?', '', line)
            # 标准化空行
            if clean_l.strip() == '':
                processed_candidates.append("") 
                continue
            
            if '\t' in clean_l:
                clean_l = clean_l.replace('\t', '    ') 

            id_match = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', clean_l)
            if id_match:
                bid = id_match.group(1)
                if bid in seen_ids:
                    continue 
                seen_ids.add(bid)
            
            # [修复] 保留尾随空格 (例如 "- ") 供用户光标使用
            processed_candidates.append(clean_l.rstrip('\n\r')) 
        
        # 日志 2: 已处理
        # Logger.debug(f"DeepTrace: {len(processed_candidates)} candidates after norm.")

        # --- 4. 上下文感知安全压缩 ---
        final_task_lines = []
        
        def is_list_item(s):
            if not s: return False
            return re.match(r'^\s*([-\*]|\d+\.)\s', s) is not None

        last_content_line = "HEADER"

        for j, curr in enumerate(processed_candidates):
            if curr == "":
                next_l = processed_candidates[j+1] if j < len(processed_candidates) - 1 else None
                
                # 1. 塌缩重复的空行
                if next_l == "": continue 

                # 2. 列表项间隙 -> 移除
                prev_is_item = (last_content_line == "HEADER") or is_list_item(last_content_line)
                next_is_item = is_list_item(next_l)
                
                if prev_is_item and next_is_item:
                    continue # SKIP
                
                # 3. 保留段落中断 (带空格)
                # [修复] 输出 "> \n" 而不是 ">\n" 以保留 "等待输入" 的空格。
                # 这防止了 "空格分隔" 问题和 Obsidian 的对抗。
                final_task_lines.append("> \n")
            else:
                final_task_lines.append(f"> {curr}\n")
                last_content_line = curr

        # --- 5. 激进清理器 (零尾部) ---
        # 自动注册：将原始任务转换为标准格式
        if filename_stem:
            final_task_lines = self.normalize_raw_tasks(final_task_lines, filename_stem)
            
        # Apply Aggressive Callout Cleaner
        final_task_lines = self.aggressive_callout_clean(final_task_lines)

        # 日志 3: 最终结果
        if final_task_lines:
             Logger.debug(f"DeepTrace: Final Block has {len(final_task_lines)} lines.")

        # --- 6. 重建 ---
        final_header = captured_header if captured_header else default_header
        
        new_block = []
        if final_task_lines:
            new_block.append(f"{final_header}\n")
            new_block.extend(final_task_lines)
            # [CRITICAL FIX] 移除了重复的 extend 调用
            new_block.append("> \n") # [修复] 强制隔离：任务块后追加空引用行
            new_block.append("\n")   # [修复] 物理隔离：追加物理空行以区隔后续标题

        return yaml_lines + new_block + clean_body

    def aggressive_callout_clean(self, lines):
        """
        [热修复] 放宽的 Callout 清理器。
        仅当连续空行超过 2 行时移除。
        保留特殊字符如 '---' 和列表标记 '-'。
        记录删除操作以供调试。
        """
        if not lines: return []
        
        cleaned_lines = []
        empty_count = 0
        
        # "Callout 空行" 的正则：> 后跟可选空白
        # 不匹配 > - (子弹点) 或 > text
        empty_pattern = re.compile(r'^\s*>\s*$')
        
        for i, line in enumerate(lines):
            is_empty = bool(empty_pattern.fullmatch(line))
            
            # 特殊安全措施：如果行包含 '---' 或 '-'，视为内容
            # '-' 保护列表的输入流 (例如 "> -")
            if '---' in line or '-' in line:
                is_empty = False
            
            if is_empty:
                empty_count += 1
                if empty_count > 2:
                    # 过多空行 -> 跳过/删除
                    Logger.debug(f"[CLEAN] Removing excess callout line {i+1}: {repr(line)}")
                    continue 
                else:
                    cleaned_lines.append(line)
            else:
                # 发现内容 -> 重置计数器
                empty_count = 0
                cleaned_lines.append(line)
        
        return cleaned_lines

    def aggressive_daily_clean(self, lines: list) -> list:
        """
        [热修复] 放宽的每日清理器。
        仅当正文中连续空行超过 2 行时移除。
        保留特殊字符如 '---'。
        记录删除操作以供调试。
        """
        if not lines: return []

        # 1. 识别 "页脚" 索引
        footer_idx = len(lines)
        for i, line in enumerate(lines):
            if line.strip().startswith('# Day planner') or line.strip().startswith('# Journey'):
                footer_idx = i
                break
        
        # 2. 提取页脚上方的内容
        body = lines[:footer_idx]
        foot = lines[footer_idx:]
        
        # 3. 清理正文（由于内部垂直空白）
        cleaned_body = []
        empty_count = 0
        empty_pattern = re.compile(r'^\s*$') # Matches pure blank lines
        
        for i, line in enumerate(body):
            is_empty = bool(empty_pattern.fullmatch(line))
            
            # 安全：保护 '---' 和其他结构标记
            if '---' in line:
                is_empty = False
                
            if is_empty:
                empty_count += 1
                if empty_count > 2:
                    Logger.debug(f"[CLEAN] Removing excess daily line {i+1}: {repr(line)}")
                    continue
                else:
                    cleaned_body.append(line)
            else:
                empty_count = 0
                cleaned_body.append(line)
        
        # 4. 重新组装
        return cleaned_body + foot

    def format_line(self, indent, status, text, dates, fname, bid, is_daily):
        # [特性] 使用 TAB 进行缩进
        # 基于缩进级别计算制表符数量（假设 1 级 = 4 个空格或 1 个制表符）
        # 如果 'indent' 仅仅作为特定宽度传入，我们可能需要调整。
        # 但 'indent' 是通过计算字符数的 get_indent() 计算得出的。
        # 简单修复：如果我们更改输入逻辑，将 'indent' 视为制表符数量？
        # 不，'indent' 是原始整数。让我们转换：4 个空格 -> 1 个制表符。
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
            clean_text = re.sub(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', '', text)
            clean_text = re.sub(r'\d{1,2}:\d{2}', '', clean_text)
            clean_text = re.sub(rf'\[\[{re.escape(fname)}(\|.*?)?\]\]', '', clean_text)
            clean_text = clean_text.strip()

            creation_date = None
            # Extract simple date from dates string or complex link
            # dates string comes from scanner
            simple_match = re.search(r'\[\[(\d{4}-\d{2}-\d{2})\]\]', dates)
            if simple_match:
                creation_date = simple_match.group(1)
            else:
                 # Try finding from complex/emoji
                 m = re.search(r'(?:📅|\|📅\]\])\s*(\d{4}-\d{2}-\d{2})', dates)
                 if m: creation_date = m.group(1)
            
            if not creation_date:
                # Last resort fallback if date not found in dates string
                 m = re.search(r'(\d{4}-\d{2}-\d{2})', dates)
                 if m: creation_date = m.group(1)

            processed_dates = []
            done_date_match = re.search(r'✅\s*(\d{4}-\d{2}-\d{2})', dates)
            if done_date_match:
                processed_dates.append(f"✅ {done_date_match.group(1)}")

            meta_str = " ".join(processed_dates)
            
            # Construct Links
            self_link = f"[[{fname}#^{bid}|⮐]]"
            daily_link = f"[[{creation_date}]]" if creation_date else ""
            parts = [self_link]
            if daily_link: parts.append(daily_link)
            parts.append(clean_text)
            if meta_str: parts.append(meta_str)
            parts.append(f"^{bid}")
            
            content_str = " ".join(parts)
            return f"{indent_str}- [{status}] {content_str}\n"

    # [新] 统一格式化的辅助函数
    def normalize_child_lines(self, raw_lines, parent_indent, as_quoted=False):
        children = []
        child_indent_lvl = (parent_indent // 4) + 1
        child_indent_str = '\t' * child_indent_lvl
        
        for line in raw_lines:
             # 清理：移除 > 和空格
             content = re.sub(r'^[>\s]+', '', line).strip()
             
             # [修复] 幽灵子弹过滤器：跳过空行或纯短横线行
             if not content or content in ['-', '- ']: continue

             # 强制子弹点语法
             if content.startswith('-'):
                 if not content.startswith('- '):
                      final_content = "- " + content[1:].strip()
                 else:
                      final_content = content
             else:
                  final_content = f"- {content}"
             
             # 输出组装
             if as_quoted:
                 # 源文件：检查是否为空以避免尾随空格问题？
                 # 标准："> \t- content"
                 # 特殊："> " 用于空行？不，对于子弹点行我们使用语法。
                 children.append(f"> {child_indent_str}{final_content}\n")
             else:
                 # 每日笔记：纯文本
                 children.append(f"{child_indent_str}{final_content}\n")
                 
        return children

    def reconstruct_daily_block(self, sd, target_date):
        fname = sd['fname']
        bid = sd['bid']
        status = sd['status']
        
        # 1. 清理文本：移除日期链接
        text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}\]\]', '', sd['pure']).strip()
        
        # 2. 如果缺失，重新注入项目链接
        link_tag = f"[[{fname}]]"
        if link_tag not in text:
            text = f"{link_tag} {text}"
            
        # 3. 构建父行（每日格式）
        # 父缩进使用制表符？通常每日笔记是顶层还是缩进的？
        # 通常是顶层或 format_line 生成的任何内容。
        # 等等，sd['indent'] 是源缩进。每日笔记缩进应该是相对的吗？
        # 如果源是缩进的，每日笔记意味着扁平化？
        # 不，通常每日笔记聚合任务。
        # 但让我们坚持使用父级的 format_line 逻辑。
        parent_line = self.format_line(sd['indent'], status, text, "", fname, bid, True)
        
        # 4. 强制子项格式化（暴力）
        children = []
        raw_children = sd['raw'][1:]
        
        # 计算子缩进（严格比父级 +1 级）
        # 假设父级在 sd['indent']
        # 等等，每日笔记中的 parent_line 通常从 0 开始还是保留？
        # 如果我们直接对父级使用 sd['indent']，我们保留层级。
        # 那么子项在父级 +1 级。
        child_indent_str = '\t' * ((sd['indent'] // 4) + 1)
        
        for line in raw_children:
            # 4.1 移除 Callout 字符
            # 正则：移除开头的 '>' 和可选空格
            child_clean = re.sub(r'^>\s?', '', line)
            
            # 4.2 分析内容
            stripped = child_clean.strip()
            
            # 4.3 内容重构
            if not stripped or stripped == '-':
                # 情况：空子弹点
                final_content = "- "
            elif stripped.startswith('-'):
                # 检查粘连，例如 "-Text"
                # 如果匹配 "-[任何内容]"
                if len(stripped) > 1 and stripped[1] != ' ':
                     # 强制空格："-Text" -> "- Text"
                     final_content = f"- {stripped[1:].strip()}"
                elif stripped == '- ':
                     final_content = "- "
                else:
                     # 是 "- Text" 或 "- [ ] Text"
                     # 重建以确保安全
                     # 去除前导 "- " 并重新添加？
                     # 如果是 "- "，stripped[2:] 可能是空的
                     final_content = f"- {stripped[2:].strip()}"
            else:
                # 情况："Text"（缺少子弹点）
                final_content = f"- {stripped}"
                
            # 4.4 缩进注入
            # [关键] 确保 "- " 中保留空格
            formatted_line = f"{child_indent_str}{final_content}"
            # 双重检查空子弹点的尾随空格
            if formatted_line.strip() == '-': 
                 # 这不应该发生，由于上面的逻辑
                 formatted_line += " "
            elif formatted_line.endswith('-'):
                 formatted_line += " "

            children.append(formatted_line)

        # [优化压缩]
        # 允许末尾最多 1 个空子弹点
        if children:
            while children and children[-1].strip() == '-':
                children.pop()
            # If we popped everything or want to leave one breathing room?
            # 用户之前想要 "最多 1 个"。
            # 如果我弹出所有，那就是 0 个。
            # 如果有效列表不为空，我们要加回一个吗？
            # 还是保持紧凑。
            # "暴力" 通常意味着严格。
            # 让我们看看之前的行为："确保最多 1 个空子弹点"。
            # 如果我移除了任何子弹点，我会追加一个空子弹点吗？不。
            # 只是简单地：移除尾随子弹点。
            # 如果用户想要，他们可以输入。
            # 如果我自动添加，那就是 "幽灵子弹"。
            # 让我们清理所有尾随空子弹点。
            pass

        return [parent_line] + children

    def cleanup_empty_callouts(self, lines):
        """如果 '> [!note]- Tasks' (或变体) 块中不包含任务复选框，则将其移除。"""
        if lines is None: return [] # 卫语句
        
        output = []
        # 鲁棒的标题正则 (支持 > [!note], > [!note]-, > [!note]+)
        TASK_HEADER_PATTERN = re.compile(r"^>\s*\[!note\]([-+]?)\s+Tasks", re.IGNORECASE)
        
        in_callout = False
        callout_buffer = []
        has_task = False

        for line in lines:
            if TASK_HEADER_PATTERN.match(line.strip()):
                # 如果需要，刷新之前的（不应处理嵌套）
                if in_callout:
                     if has_task: output.extend(callout_buffer)
                in_callout = True
                callout_buffer = [line]
                has_task = False
            elif in_callout:
                if line.strip().startswith('>') or line.strip() == '':
                    callout_buffer.append(line)
                    if re.search(r'-\s*\[.\]', line):
                        has_task = True
                else:
                    # Callout 结束
                    if has_task: output.extend(callout_buffer)
                    in_callout = False
                    callout_buffer = []
                    output.append(line)
            else:
                output.append(line)
        
        if in_callout and has_task:
            output.extend(callout_buffer)

        return output

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
        # [修复] 阉割标题吞噬：
        # 仅确保结构，不要删除空标题。
        lines = self.ensure_structure(lines)
        return lines, False

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

    def organize_orphans(self, filepath, date_tag):
        lines = FileUtils.read_file(filepath)
        if not lines: return False

        lines = self.ensure_structure(lines)

        tasks_to_move = []
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
                    target = self.extract_routing_target(lines[i])
                    if target:
                        p_root = os.path.dirname(target)
                        p_name = None
                        curr = p_root
                        while curr.startswith(Config.ROOT_DIR):
                            if curr in self.project_map: p_name = self.project_map[curr]; break
                            parent = os.path.dirname(curr)
                            if parent == curr: break
                            curr = parent
                        if p_name:
                            content, length = self.capture_block(lines, i)
                            tasks_to_move.append({'idx': i, 'len': length, 'proj': p_name, 'raw': content})
                            i += length;
                            continue
            i += 1

        if not tasks_to_move: return False

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
        return FileUtils.write_file(filepath, lines)

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
                
                # 辅助函数：获取忽略 Callout 标记的原始缩进
                def get_raw_indent(s):
                    # 先移除引用标记，然后去除左侧空白以计算缩进
                    # re.sub(r'^>\s?', '', s) 处理开头的 '> ' 或 '>'
                    return len(s) - len(re.sub(r'^>\s?', '', s).lstrip())

                while i < len(lines):
                    line = lines[i]
                    # [核心] 检测任何任务标记（裸任务或带日期的）
                    # 检查 - [ ] 模式（允许 > 前缀）
                    if not re.match(r'^[\s>]*-\s*\[.\]', line):
                        i += 1
                        continue
                        
                    # --- 发现任务 ---
                    
                    # 1. 日期检测
                    task_date = None
                    date_match = re.search(r'[📅✅]\s*(\d{4}-\d{2}-\d{2})', line)
                    if date_match:
                        task_date = date_match.group(1)
                    else:
                        # 尝试新链接格式
                        link_match = re.search(r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\]\])', line)
                        if link_match: task_date = link_match.group(1)
                    
                    # [自动补全] 如果是裸任务（未找到日期），默认为今天
                    if not task_date:
                        task_date = today_str
                        mod = True
                        # Logger.info(f"Captured Naked Task in {fname}")
                        
                    # 2. Block ID
                    # 2. 块 ID
                    # 严格 ID 正则：空格 + ^ + 6-7 个字母数字 + 结尾
                    id_m = re.search(r'(?<=\s)\^([a-zA-Z0-9]{6,7})\s*$', line)
                    if id_m: bid = id_m.group(1)
                    else:
                        # 回退 / 自动生成
                        bid = self.generate_block_id().replace('^', '')
                        mod = True
                        
                    # 3. 属性与解析
                    indent = get_raw_indent(line)
                    status_match = re.search(r'-\s*\[(.)\]', line)
                    st = status_match.group(1) if status_match else ' '
                    clean_txt = self.clean_task_text(line, bid, context_name=fname)
                    
                    # 提取日期字符串（现有逻辑）
                    dates = " ".join(re.findall(r'([📅✅]\s*\d{4}-\d{2}-\d{2}|\[\[\d{4}-\d{2}-\d{2}#\^[a-zA-Z0-9]+\|📅\]\]|\[\[\d{4}-\d{2}-\d{2}\]\])', line))
                    
                    # [自动补全] 如果我们推断了日期，确保日期链接存在
                    # 仅当日期尚未以某种形式出现在文本中时才追加
                    if task_date not in line: 
                        if not dates: dates = f"[[{task_date}]]"
                        else: dates += f" [[{task_date}]]"
                        mod = True 

                    # 4. 格式化行并检查更新
                    new_line = self.format_line(indent, st, clean_txt, dates, fname, bid, False)
                    
                    # [修复] Callout 保护 / 警卫
                    # 如果通过原本有引用，确保 new_line 也有引用
                    is_quoted = line.strip().startswith('>')
                    if is_quoted:
                        if not new_line.strip().startswith('>'):
                            # 前置 > 并确保间距
                            # 如果 new_line 是 "\t- ..."，使其变为 "> \t- ..."
                            # 简单前置 "> " 是标准 Obsidian 语法
                            new_line = "> " + new_line
                    
                    if new_line.strip() != line.strip():
                        lines[i] = new_line
                        mod = True
                        
                    # 5. 捕获与哈希
                    block, consumed = self.capture_block(lines, i)
                    combined_text = clean_txt + "|||" + self.normalize_block_content(block[1:])
                    content_hash = self.sm.calc_hash(st, combined_text)
                    
                    # 6. 存储
                    if task_date not in source_data_by_date: source_data_by_date[task_date] = {}
                    source_data_by_date[task_date][bid] = {
                        'proj': curr_proj, 'bid': bid, 'pure': clean_txt, 'status': st,
                        'path': path, 'fname': fname, 'raw': block, 'hash': content_hash, 'indent': indent,
                        'dates': dates, 'is_quoted': is_quoted
                    }
                    
                    i += consumed
                
                if mod:
                    # 写入前清理 Callout
                    lines = self.inject_into_callout(lines, [])
                    lines = self.cleanup_empty_callouts(lines)
                    FileUtils.write_file(path, lines)

        return source_data_by_date

    def process_date(self, target_date, src_tasks_for_date):
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        is_past = target_date < today_str

        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{target_date}.md")

        if os.path.exists(daily_path):
            self.organize_orphans(daily_path, target_date)

        dn_tasks = {}
        new_dn_tasks = []
        dn_lines = []
        if os.path.exists(daily_path):
            dn_lines = FileUtils.read_file(daily_path) or []
            curr_ctx = None
            i = 0
            while i < len(dn_lines):
                line = dn_lines[i]
                h_m = re.match(r'^##\s*\[\[(.*?)\]\]', line.strip())
                if h_m: curr_ctx = h_m.group(1); i += 1; continue

                tm = re.match(r'^[\s>]*-\s*\[(.)\]', line)
                if tm:
                    lm = re.search(r'\[\[(.*?)\#\^([a-zA-Z0-9]{6,})\|.*?\]\]', line)
                    if lm:
                        ctx_name = lm.group(1)
                        bid = lm.group(2)
                        raw, c = self.capture_block(dn_lines, i)
                        clean = self.clean_task_text(line, bid, context_name=ctx_name)
                        st = tm.group(1)
                        # 开始修复：在哈希中包含子任务
                        combined_text = clean + "|||" + self.normalize_block_content(raw[1:])
                        content_hash = self.sm.calc_hash(st, combined_text)
                        # 结束修复
                        dn_tasks[bid] = {
                            'pure': clean, 'status': st, 'idx': i, 'len': c,
                            'raw': raw, 'hash': content_hash
                        }
                        i += c;
                        continue
                    elif curr_ctx and curr_ctx in self.project_path_map:
                        if '^' not in line:
                             # [修复] 每日笔记缩进计算（移除 > 即使不可见）
                             # 虽然 Daily 很少有 >，但以防万一
                            raw_indent = len(line) - len(line.lstrip())
                             
                            raw, c = self.capture_block(dn_lines, i)
                            new_dn_tasks.append({
                                'proj': curr_ctx, 'idx': i, 'len': c, 'raw': raw,
                                'st': tm.group(1), 'indent': raw_indent
                            })
                            i += c;
                            continue
                        else:
                            # 回退：检查该行是否有指向已知项目或文件的直接链接
                            link_match = re.search(r'\[\[(.*?)(?:#|\||\]\])', line)
                            if link_match:
                                pot = link_match.group(1).strip()
                                pot = unicodedata.normalize('NFC', pot)
                                # 检查项目映射，然后检查文件映射
                                target_file = None
                                if pot in self.project_path_map: target_file = self.project_path_map[pot]
                                elif pot in self.file_path_map: target_file = self.file_path_map[pot]
                                
                                if target_file:
                                    raw_indent = len(line) - len(line.lstrip())
                                    raw, c = self.capture_block(dn_lines, i)
                                    new_dn_tasks.append({
                                        # 如果可用，使用 'proj' 键作为项目名称，或者仅使用文件名
                                        'proj': self.project_map.get(os.path.dirname(target_file), pot), 
                                        'idx': i, 'len': c, 'raw': raw,
                                        'st': tm.group(1), 'indent': raw_indent
                                    })
                                    i += c;
                                    continue
                i += 1

        dn_mod = False
        if new_dn_tasks:
            Logger.info(f"处理新建任务: {len(new_dn_tasks)} 条", target_date)
            for nt in reversed(new_dn_tasks):
                p_name = nt['proj']
                txt = nt['raw'][0]
                clean = self.clean_task_text(txt)
                tgt = self.extract_routing_target(txt) or self.project_path_map.get(p_name)
                if not tgt: continue
                bid = self.generate_block_id().replace('^', '')
                fname = os.path.splitext(os.path.basename(tgt))[0]

                s_l = self.format_line(nt['indent'], nt['st'], clean, f"📅 {target_date}", fname, bid, False)
            
            # [修复] 源块：作为引用
            s_children = self.normalize_child_lines(nt['raw'][1:], nt['indent'], as_quoted=True)
            s_blk = [s_l] + s_children
            
            d_l = self.format_line(nt['indent'], nt['st'], clean, "", fname, bid, True)
            
            # [修复] 每日块：纯文本
            d_children = self.normalize_child_lines(nt['raw'][1:], nt['indent'], as_quoted=False)
            d_blk = [d_l] + d_children

            dn_lines[nt['idx']:nt['idx'] + nt['len']] = d_blk
            dn_mod = True

            sl = FileUtils.read_file(tgt) or []
            sl = self.inject_into_callout(sl, s_blk)
            
            # 探针 1: 注入新任务
            Logger.debug_block(f"Injecting New Task into {fname}", s_blk)
            
            FileUtils.write_file(tgt, sl)
            
            # 触发延迟验证
            self.trigger_delayed_verification(tgt)

            # 开始修复：在哈希中包含子任务
            combined_text = clean + "|||" + self.normalize_block_content(nt['raw'][1:])
            h = self.sm.calc_hash(nt['st'], combined_text)
            # 结束修复
            self.sm.update_task(bid, h, tgt)

            # 为每个新任务插入触发置顶
            # 虽然上面调用了 inject_into_callout，但用空列表调用它可以确保
            # 如果 Callout 不在顶部（例如旧文件），它会移动到那里。
            # 但等等，上面的调用 `sl = self.inject_into_callout(sl, s_blk)` 已经做了这个。
            # 所以这里不需要额外的调用。


        if dn_mod:
            FileUtils.write_file(daily_path, dn_lines)
            self.sm.save()
            return

        src_tasks = src_tasks_for_date
        all_ids = set(src_tasks.keys()) | set(dn_tasks.keys())
        append_to_dn = {}
        src_updates = {}
        src_deletes = {}

        for bid in all_ids:
            in_s = bid in src_tasks
            in_d = bid in dn_tasks
            last_hash = self.sm.get_task_hash(bid)

            if in_s and in_d:
                sd = src_tasks[bid]
                dd = dn_tasks[bid]
                s_changed = (sd['hash'] != last_hash)
                d_changed = (dd['hash'] != last_hash)

                if s_changed and not d_changed:
                    blk = self.reconstruct_daily_block(sd, target_date)
                    
                    # 探针 2: 从源更新每日笔记
                    Logger.debug_block(f"Updating Daily Note from Source {sd['fname']}", blk)
                    
                    dn_lines[dd['idx']:dd['idx'] + dd['len']] = blk
                    dn_mod = True
                    self.sm.update_task(bid, sd['hash'], sd['path'])

                elif d_changed and not s_changed:
                    n_l = self.format_line(sd['indent'], dd['status'], dd['pure'], f"📅 {target_date}", sd['fname'], bid,
                                           False)
                    was_quoted = sd.get('is_quoted', False)
                    if was_quoted and not n_l.strip().startswith('>'): n_l = f"> {n_l}"

                    # [修复] 为源标准化子项 (as_quoted=True)
                    blk = [n_l] + self.normalize_child_lines(dd['raw'][1:], sd['indent'], as_quoted=True)

                    if sd['path'] not in src_updates: src_updates[sd['path']] = {}
                    
                    # 探针 3: 准备源更新（批处理时记录，但也在此处记录内容？）
                    # 白盒：显示我们正在排队的内容。
                    Logger.debug_block(f"Queueing Update for Source {sd['fname']}", blk)
                    
                    src_updates[sd['path']][bid] = blk
                    self.sm.update_task(bid, dd['hash'], sd['path'])

                elif s_changed and d_changed:
                    if sd['hash'] != dd['hash']:
                        Logger.info(f"冲突检测 {bid}: 优先保留 Daily 修改", target_date)
                        n_l = self.format_line(sd['indent'], dd['status'], dd['pure'], f"📅 {target_date}", sd['fname'],
                                               bid, False)
                        was_quoted = sd.get('is_quoted', False)
                        if was_quoted and not n_l.strip().startswith('>'): n_l = f"> {n_l}"

                        # [修复] 为源标准化子项 (as_quoted=True)
                        blk = [n_l] + self.normalize_child_lines(dd['raw'][1:], sd['indent'], as_quoted=True)

                        if sd['path'] not in src_updates: src_updates[sd['path']] = {}
                        src_updates[sd['path']][bid] = blk
                        self.sm.update_task(bid, dd['hash'], sd['path'])
                else:
                    if last_hash is None: self.sm.update_task(bid, sd['hash'], sd['path'])

            elif in_s and not in_d:
                sd = src_tasks[bid]
                
                # 检查 1: 历史保护（过去日期）-> 强制恢复
                if is_past:
                    Logger.info(f"历史保护: 检测到旧日记({target_date})缺失任务 {bid}，强制回写", target_date)
                    if sd['proj'] not in append_to_dn: append_to_dn[sd['proj']] = []
                    append_to_dn[sd['proj']].append(sd)
                    self.sm.update_task(bid, sd['hash'], sd['path'])

                # 检查 2: 正常删除（今天或未来）-> 允许删除
                elif last_hash:
                    Logger.info(f"离线同步: 检测到 Daily 删除 {bid}，移除 Source", target_date)
                    if sd['path'] not in src_deletes: src_deletes[sd['path']] = {}
                    src_deletes[sd['path']][bid] = sd['path']
                    self.sm.remove_task(bid)

                # 检查 3: 源中的新任务 -> 添加到 Daily
                else:
                    if sd['proj'] not in append_to_dn: append_to_dn[sd['proj']] = []
                    append_to_dn[sd['proj']].append(sd)
                    self.sm.update_task(bid, sd['hash'], sd['path'])

            elif in_d and not in_s:
                dd = dn_tasks[bid]
                if last_hash:
                    Logger.info(f"离线同步: 检测到 Source 删除 {bid}，移除 Daily", target_date)
                    for k in range(dd['idx'], dd['idx'] + dd['len']): dn_lines[k] = "__DEL__\n"
                    dn_mod = True
                    self.sm.remove_task(bid)
                else:
                    self.sm.update_task(bid, dd['hash'], "UNKNOWN")

        if dn_mod: dn_lines = [x for x in dn_lines if x != "__DEL__\n"]

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
                    out.append(sl[i]); i += 1
            if chg:
                # 即使删除也强制置顶（以移动剩余任务）
                stem = os.path.splitext(os.path.basename(path))[0]
                out = self.inject_into_callout(out, [], stem)
                out = self.cleanup_empty_callouts(out)
                
                # [修复 1] 净化列表
                out = [l for l in out if l is not None]
                
                FileUtils.write_file(path, out)

        for path, ups in src_updates.items():
            sl = FileUtils.read_file(path)
            if not sl: continue
            out, i, chg = [], 0, False
            while i < len(sl):
                im = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', sl[i])
                if not im: im = re.search(r'\(connect::.*?\^([a-zA-Z0-9]{6,})\)', sl[i])
                if im and im.group(1) in ups:
                    _, c = self.capture_block(sl, i)
                    out.extend(ups[im.group(1)])
                    i += c;
                    chg = True
                else:
                    out.append(sl[i]); i += 1
            if chg:
                # 强制置顶（重新注入空）然后清理
                stem = os.path.splitext(os.path.basename(path))[0]
                out = self.inject_into_callout(out, [], stem)
                out = self.cleanup_empty_callouts(out)
                
                # 探针 4: 批量源更新
                Logger.debug_block(f"Batch Updating Source {os.path.basename(path)}", out)
                
                # [修复 1] 净化列表：移除 None 值以防止崩溃
                out = [l for l in out if l is not None]
                
                FileUtils.write_file(path, out)
                self.trigger_delayed_verification(path)
                Logger.info(f"源内容同步: {os.path.basename(path)}", target_date)

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
                    l1 = self.format_line(t['indent'], t['status'], t['pure'], "", t['fname'], t['bid'], True)
                    # [修复] 为 Daily 标准化子项 (as_quoted=False)
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
        
        # --- [修复开始] 防止 Ping-Pong 循环 ---
        # 强制清理 Daily Note 的尾部
        original_len = len(dn_lines)
        dn_lines = self.aggressive_daily_clean(dn_lines)
        if len(dn_lines) != original_len:
            dn_mod = True # 确保如果我们清理了某些内容则进行保存
        # --- [修复结束] ---

        if dn_mod:
            # [修复 1] 同样净化 Daily Note 行，以防万一
            dn_lines = [l for l in dn_lines if l is not None]

            FileUtils.write_file(daily_path, dn_lines)
            Logger.info("Daily Note 更新完成", target_date)

        self.sm.save()

