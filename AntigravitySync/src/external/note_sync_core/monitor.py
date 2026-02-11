"""
[v4.0] Apple Notes Monitor — 备忘录变更监听与自动同步模块

功能:
1. 轮询 Apple Notes 中当天的备忘录，检测内容变更
2. 识别以时间戳开头的新增行（如 "23:28:14"烟":"x1"）
3. 自动将其格式化并插入 Obsidian 今日日记的 ## #Water 章节
4. 格式: HH:MM<span id="HH:MM:SS"></span> Keyword::Value
5. 支持 Config.KEYWORD_MAPPING 中英文映射

用法:
    from external.note_sync_core.monitor import NoteMonitor
    monitor = NoteMonitor()
    monitor.start()  # 以 daemon 线程启动
    monitor.stop()   # 停止监听
"""

import os
import sys
import time
import datetime
import threading
import re
import difflib

# 确保能找到同目录下的 read_today_note
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from read_today_note import AppleNotesReader


class NoteMonitor:
    """
    Apple Notes 变更监听器。
    以 daemon 线程运行，检测备忘录变更并自动插入 Obsidian 日记。
    """

    def __init__(self, config=None, logger=None):
        """
        Args:
            config: Config 对象，需要有 DAILY_NOTE_DIR, TEMPLATE_FILE, KEYWORD_MAPPING 属性
            logger: Logger 对象，需要有 info() 方法。若 None 则使用 print
        """
        self._config = config
        self._log = logger.info if logger else print
        self._thread = None
        self._running = False
        self._reader = AppleNotesReader()
        self._polling_interval = 2.0  # 秒
        self._tomorrow_note_created = False  # 防重复创建次日日记

    # =====================
    # 公开接口
    # =====================

    def start(self):
        """以 daemon 线程启动监听"""
        if self._thread and self._thread.is_alive():
            self._log("⚠️ [NoteMonitor] 已在运行中，跳过重复启动")
            return

        self._running = True
        self._thread = threading.Thread(target=self._polling_loop, daemon=True, name="NoteMonitor")
        self._thread.start()
        self._log("📝 [NoteMonitor] 备忘录监听已启动 (daemon 线程)")

    def stop(self):
        """停止监听"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._log("🛑 [NoteMonitor] 备忘录监听已停止")

    # =====================
    # 核心轮询逻辑
    # =====================

    def _polling_loop(self):
        """后台轮询主循环"""
        self._log(f"📍 [NoteMonitor] 策略: Active Polling (每 {self._polling_interval}s)")

        # 确定今日备忘录标题
        today = datetime.date.today()
        note_name = f"{today.year}/{today.month}/{today.day}"
        self._log(f"🔎 [NoteMonitor] 追踪备忘录: '{note_name}'")

        # [v4.1] 启动检查：确保今日 Obsidian 日记和 Apple Note 存在
        self._check_and_create_today_notes(today)

        # 初始读取
        last_content = self._reader.get_note_content(note_name)
        if last_content is None or last_content == "NOT_FOUND":
            self._log(f"⚠️ [NoteMonitor] 备忘录未找到，等待出现...")
            last_hash = 0
        else:
            self._log(f"✅ [NoteMonitor] 初始内容已加载 ({len(last_content)} chars)")
            
            # [v4.2] 首次全量扫描：同步遗漏的未标记项
            self._log("🔄 [NoteMonitor] 正在执行首次全量扫描 (Sync missing items)...")
            initial_lines = last_content.splitlines()
            # 模拟从空到有的 Diff
            dummy_diff = list(difflib.unified_diff([], initial_lines, n=0, lineterm=''))
            monitor_thread_name = threading.current_thread().name
            
            # 调用处理逻辑 (会自动回写 ✅)
            self._process_diff(dummy_diff, initial_lines, note_name)
            
            # 如果发生了回写，刷新 last_content
            # 给一点时间让 Apple Notes 更新（虽然 AppleScript 是同步的，但保险起见）
            time.sleep(1)
            last_content = self._reader.get_note_content(note_name)
            last_hash = hash(last_content) if last_content else 0

        while self._running:
            try:
                time.sleep(self._polling_interval)

                # 跨日检测：如果日期变了，更新目标备忘录
                current_today = datetime.date.today()
                if current_today != today:
                    today = current_today
                    note_name = f"{today.year}/{today.month}/{today.day}"
                    self._log(f"🌙 [NoteMonitor] 跨日检测: 切换到 '{note_name}'")
                    last_hash = 0
                    last_content = ""
                    self._tomorrow_note_created = False  # 重置次日日记标记

                # [v4.0] 23:55 自动创建次日日记
                self._check_create_tomorrow_note()

                current_content = self._reader.get_note_content(note_name)

                # 备忘录消失
                if current_content is None or current_content == "NOT_FOUND":
                    if last_hash != 0:
                        self._log("❌ [NoteMonitor] 备忘录消失!")
                        last_hash = 0
                    continue

                current_hash = hash(current_content)

                if current_hash != last_hash:
                    now_str = datetime.datetime.now().strftime('%H:%M:%S')
                    self._log(f"\n⚡ [NoteMonitor] 变更检测 {now_str}")

                    # Diff 分析
                    safe_last = last_content if last_content and last_content != "NOT_FOUND" else ""
                    old_lines = safe_last.splitlines()
                    new_lines = current_content.splitlines()

                    diff = list(difflib.unified_diff(old_lines, new_lines, n=0, lineterm=''))
                    self._process_diff(diff, new_lines, note_name)

                    print("-" * 40)

                    last_hash = current_hash
                    last_content = current_content

            except Exception as e:
                self._log(f"⚠️ [NoteMonitor] 轮询异常: {e}")
                time.sleep(5)  # Backoff

    # =====================
    # 23:55 次日日记创建
    # =====================

    def _check_create_tomorrow_note(self):
        """
        [v4.0] 每天 23:55 自动创建次日日记文件
        使用项目模板 (Config.TEMPLATE_FILE) 生成标准格式
        """
        if self._tomorrow_note_created:
            return  # 今天已经创建过了

        if not self._config:
            return

        now = datetime.datetime.now()

        # 只在 23:56:00 ~ 23:59:59 之间触发
        if now.hour == 23 and now.minute >= 56:
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
            tomorrow_str = tomorrow.strftime('%Y-%m-%d')
            daily_note_dir = getattr(self._config, 'DAILY_NOTE_DIR', None)

            if not daily_note_dir:
                return

            tomorrow_path = os.path.join(daily_note_dir, f"{tomorrow_str}.md")

            if os.path.exists(tomorrow_path):
                self._tomorrow_note_created = True  # 已存在，标记跳过
                return

            # 读取模板
            template_content = self._read_template()

            try:
                with open(tomorrow_path, 'w', encoding='utf-8') as f:
                    f.write(template_content)

                self._tomorrow_note_created = True
                self._log(f"📅 [NoteMonitor] 次日日记已创建: {tomorrow_str}.md")
            except Exception as e:
                self._log(f"❌ [NoteMonitor] 创建次日日记失败: {e}")

    def _read_template(self):
        """
        读取 Config.TEMPLATE_FILE 模板内容。
        如果模板不存在，则使用内置的基础骨架。
        """
        template_path = getattr(self._config, 'TEMPLATE_FILE', None)

        if template_path and os.path.exists(template_path):
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                self._log(f"⚠️ [NoteMonitor] 模板读取失败，使用默认骨架: {e}")

        # 内置默认模板（与 DayPlanTemplate.md 一致）
        return """---
tags:
  - DayPlan
  - timecost
  - tradecost
---
# Day planner

# Journey

# Log
## #StateofMind
## #Eat
## #Sport

## #Water

## #Account
## #Account
"""

    def _check_and_create_today_notes(self, today):
        """
        [v4.1] 检查并创建今日所需的 Obsidian 日记和 Apple Notes
        """
        if not self._config:
            return

        # 1. Check/Create Obsidian Daily Note
        today_str = today.strftime('%Y-%m-%d')
        daily_note_dir = getattr(self._config, 'DAILY_NOTE_DIR', None)
        
        if daily_note_dir:
            today_path = os.path.join(daily_note_dir, f"{today_str}.md")
            if not os.path.exists(today_path):
                self._log(f"⚠️ [NoteMonitor] 今日日记缺失，正在创建: {today_str}.md")
                template_content = self._read_template()
                try:
                    with open(today_path, 'w', encoding='utf-8') as f:
                        f.write(template_content)
                    self._log(f"✅ [NoteMonitor] 今日日记创建成功")
                except Exception as e:
                    self._log(f"❌ [NoteMonitor] 创建今日日记失败: {e}")

        # 2. Check/Create Apple Note
        note_name = f"{today.year}/{today.month}/{today.day}"
        content = self._reader.get_note_content(note_name)
        
        if content == "NOT_FOUND" or content is None:
            self._log(f"⚠️ [NoteMonitor] 今日备忘录缺失，正在创建: '{note_name}'")
            # 默认内容可以是空白，或者简单的标题
            default_body = f"Daily Log {today_str}"
            result = self._reader.create_note(note_name, default_body)
            if result == "CREATED":
                self._log(f"✅ [NoteMonitor] 备忘录创建成功")
            elif result == "EXISTS":
                self._log(f"ℹ️ [NoteMonitor] 备忘录已存在 (并发创建?)")
            else:
                self._log(f"❌ [NoteMonitor] 创建备忘录失败")

    # =====================
    # Diff 处理逻辑
    # =====================

    def _process_diff(self, diff, current_lines, note_name):
        """
        处理 unified diff 输出，识别 ADD/DEL/MOD。
        如果成功同步到 Obsidian，则更新 Apple Notes 内容（添加 ✅）。
        """
        GREEN = '\033[92m'
        RED = '\033[91m'
        YELLOW = '\033[93m'
        RESET = '\033[0m'

        changes_found = False
        current_dels = []
        current_adds = []
        
        # 记录需要回写 Apple Notes 的标志
        notes_updated = False
        # 为了避免修改正在遍历的列表，使用索引或副本，但这里我们直接修改 current_lines List
        # 只要我们能找到对应的行即可。

        time_pat = re.compile(r'^\s*(\d{1,2}[:：]\d{2})')

        def flush_hunk(dels, adds):
            nonlocal changes_found, notes_updated
            used_adds = [False] * len(adds)

            for d_line in dels:
                d_match = time_pat.match(d_line.strip())
                matched_idx = -1

                if d_match:
                    d_time = d_match.group(1)
                    for i, a_line in enumerate(adds):
                        if not used_adds[i]:
                            a_match = time_pat.match(a_line.strip())
                            if a_match and a_match.group(1) == d_time:
                                matched_idx = i
                                break

                if matched_idx != -1:
                    print(f"{YELLOW}[MOD] {d_line} -> {adds[matched_idx]}{RESET}")
                    used_adds[matched_idx] = True
                else:
                    print(f"{RED}[DEL] {d_line}{RESET}")

            for i, a_line in enumerate(adds):
                if not used_adds[i]:
                    stripped_line = a_line.strip()
                    suffix = ""
                    processed = False
                    
                    # 1. Check Time Entries (Water/Log)
                    is_time_entry = time_pat.match(stripped_line)
                    if is_time_entry and "✅" not in stripped_line:
                        if self._append_to_daily_note(a_line):
                            suffix = " ✅"
                            processed = True

                    # 2. Check Account Entries (tradetype::...)
                    # Example: (tradetype::$食物)(tradename::鸡蛋)(tradecost::-858)(tradetime::2026/2/12 00:19:36)
                    if not processed and "(tradetype::" in stripped_line and "✅" not in stripped_line:
                        if self._append_to_account_section(a_line):
                            suffix = " ✅"
                            processed = True

                    if processed:
                        # [Write Back Logic] common for both types
                        try:
                            # Iterate to find the exact line to update
                            for idx, cl in enumerate(current_lines):
                                if cl == a_line: 
                                    current_lines[idx] = cl + " ✅"
                                    notes_updated = True
                                    break
                        except ValueError:
                            pass

                    print(f"{GREEN}[ADD] {a_line}{RESET}{suffix}")

        for line in diff:
            if line.startswith('---') or line.startswith('+++'):
                continue

            if line.startswith('@@'):
                if current_dels or current_adds:
                    flush_hunk(current_dels, current_adds)
                    current_dels = []
                    current_adds = []
                continue

            if line.startswith('+') or line.startswith('-'):
                changes_found = True
                if line.startswith('-'):
                    current_dels.append(line[1:])
                elif line.startswith('+'):
                    current_adds.append(line[1:])

        # Flush remaining
        if current_dels or current_adds:
            flush_hunk(current_dels, current_adds)

        if not changes_found:
            print("   (内容变化但 diff 为空 - 可能是空白符变更)")
            
        # 如果有回写需求，更新 Apple Notes
        if notes_updated:
            new_full_content = "\n".join(current_lines)
            self._reader.update_note_content(note_name, new_full_content)
            self._log(f"🔄 [NoteMonitor] 已回写 ✅ 标记到 Apple Notes")

    # =====================
    # Obsidian 日记写入
    # =====================

    def _append_to_daily_note(self, line_content):
        """
        将带时间戳的行追加到今日日记的 ## #Water 章节。
        格式: HH:MM<span id="HH:MM:SS"></span> Keyword::Value
        """
        RED = '\033[91m'
        RESET = '\033[0m'

        try:
            if not self._config or not hasattr(self._config, 'DAILY_NOTE_DIR'):
                print(f"{RED}❌ Config 缺少 DAILY_NOTE_DIR{RESET}")
                return False

            today_str = datetime.date.today().strftime('%Y-%m-%d')
            daily_note_path = os.path.join(self._config.DAILY_NOTE_DIR, f"{today_str}.md")

            if not os.path.exists(daily_note_path):
                print(f"{RED}❌ 日记文件未找到: {daily_note_path}{RESET}")
                return False

            with open(daily_note_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            new_line_clean = line_content.strip()

            # 读取并重组 ## #Water 章节
            final_lines = self._reorganize_water_section(lines, new_line_clean)
            
            with open(daily_note_path, 'w', encoding='utf-8') as f:
                f.writelines(final_lines)

            return True

        except Exception as e:
            print(f"{RED}❌ 写入日记异常: {e}{RESET}")
            return False

    def _reorganize_water_section(self, lines, new_raw_entry):
        """
        解析并重组 ## #Water 章节:
        1. 提取现有条目 + 新条目
        2. 解析时间、Key、内容
        3. 按 Key 分组，组内按时间倒序排序
        4. 生成新内容覆盖原章节
        """
        # 1. 解析新条目
        new_parsed = self._parse_entry(new_raw_entry)
        if not new_parsed:
            # 如果解析失败，直接追加（fallback）
            # 但这里我们尽量保证能处理。如果失败，返回原 lines + 追加
            # 为简单起见，若无法解析，暂不处理排序，直接返回追加逻辑
            # 但为了保持一致性，我们构造一个 dummy parsed
            new_parsed = {
                'time': '00:00', 'full_ts': '00:00:00', 
                'key': 'Unsorted', 'content': new_raw_entry,
                'raw': new_raw_entry # We will format it later
            }
            # 重新格式化新条目 (简单处理)
            # formatted_new = self._format_parsed_entry(new_parsed)
            # new_parsed['raw'] = formatted_new
            # Fallback raw line
            if not new_parsed['raw'].endswith('\n'):
                new_parsed['raw'] += '\n'

        # 2. 定位章节范围
        target_section = "## #Water"
        start_idx = -1
        end_idx = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == target_section:
                start_idx = i + 1
            elif start_idx != -1 and stripped.startswith('## '):
                end_idx = i
                break
        
        if start_idx == -1:
            # 章节不存在，追加到末尾
            if lines and not lines[-1].endswith('\n'):
                lines.append('\n')
            lines.append(f"\n{target_section}\n")
            lines.append(new_parsed['raw'])
            return lines

        if end_idx == -1:
            end_idx = len(lines)

        # 3. 提取现有条目
        existing_lines = lines[start_idx:end_idx]
        entries = []
        
        # 将新条目加入列表
        entries.append(new_parsed)

        # 解析旧条目
        # 预期格式: HH:MM<span id="HH:MM:SS"></span> Key::Value
        # 或者旧格式: - HH:MM...
        entry_pattern = re.compile(r'(\d{1,2}[:：]\d{2})<span id="([^"]+)"></span>\s*(.*)')

        for line in existing_lines:
            line = line.strip()
            if not line:
                continue
            
            # 尝试解析标准格式
            m = entry_pattern.match(line)
            if m:
                ts_display = m.group(1)
                ts_full = m.group(2)
                content_part = m.group(3)
                
                # 提取 Key
                if '::' in content_part:
                    key = content_part.split('::')[0].strip()
                else:
                    key = 'Unsorted'
                
                entries.append({
                    'time': ts_display,
                    'full_ts': ts_full,
                    'key': key,
                    'content': content_part, # 保留 Key::Val 部分
                    'raw': line + '\n'
                })
            else:
                # 无法解析的行（可能是手动输入的笔记），保留为 Unsorted 或 Ignore?
                # 为了不丢失数据，归类到 Unsorted
                # 尝试提取时间戳
                simple_time = re.match(r'^(\d{1,2}[:：]\d{2})', line)
                ts = simple_time.group(1) if simple_time else "00:00"
                entries.append({
                    'time': ts,
                    'full_ts': ts + ":00",
                    'key': 'Notes',
                    'content': line,
                    'raw': line + '\n'
                })

        # 4. 排序与分组
        # 先按 Key 字母序，再按 Time 倒序 (最新的在最前)
        entries.sort(key=lambda x: (x['key'], x['full_ts']), reverse=True)
        # 上面的排序结果是 Key 也是倒序 (Water -> Monster -> Cigarette)，这可能不是我们要的。
        # 我们想要 Key 升序 (C -> M -> W)，组内 Time 倒序。
        
        # 重新排序：
        # Primary: Key (Ascending)
        # Secondary: Time (Descending) -> 利用负数或者 reverse=True on subset?
        # Python sort is stable.
        
        # Step A: Sort by Time Descending (Global)
        entries.sort(key=lambda x: x['full_ts'], reverse=True)
        # Step B: Sort by Key Ascending (Global) -> Stable sort preserves relative order (Time Desc)
        entries.sort(key=lambda x: x['key'])

        # 5. 构建新内容块
        new_section_lines = []
        current_key = None
        
        for entry in entries:
            if current_key is not None and entry['key'] != current_key:
                new_section_lines.append('\n') # 组间空行
            
            current_key = entry['key']
            new_section_lines.append(entry['raw'])

        # 确保最后一行有换行
        if new_section_lines and not new_section_lines[-1].endswith('\n'):
            new_section_lines[-1] += '\n'

        # 6. 替换原文
        # start_idx 是内容开始，end_idx 是下一个标题开始
        # 我们需要保留 start_idx 之前的，和 end_idx 之后的
        
        # 修正：确保 start_idx 前的一行是标题
        # 我们在 start_idx 位置插入空行吗？原逻辑 append 有换行。
        # 简单处理：新内容覆盖旧内容
        
        final = lines[:start_idx] + new_section_lines + lines[end_idx:]
        return final

    def _parse_entry(self, raw_line):
        """
        将原始备忘录行 '23:54"烟":"x1"' 解析为结构化数据，并处理映射
        返回: {'time':..., 'full_ts':..., 'key':..., 'raw':...}
        """
        raw_line = raw_line.strip()
        match = re.match(r'^(\d{1,2}[:：]\d{2}(?:[:：]\d{2})?)', raw_line)
        if not match:
            return None
            
        ts_full = match.group(1)
        ts_end = match.end()
        
        # 用于显示的 HH:MM
        parts = re.split(r'[:：]', ts_full)
        ts_display = f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else ts_full
        
        content_part = raw_line[ts_end:]
        
        # 清理内容
        cleaned = content_part.replace('":"', '::')
        cleaned = cleaned.replace('"', '').replace("'", "").strip()
        
        # 映射
        mapping = getattr(self._config, 'KEYWORD_MAPPING', {})
        key = 'Unsorted'
        
        if '::' in cleaned:
            key_raw, val = cleaned.split('::', 1)
            key_raw = key_raw.strip()
            if key_raw in mapping:
                key = mapping[key_raw]
                cleaned = f"{key}::{val}"
            else:
                key = key_raw
        
        # 构造最终行
        span = f'<span id="{ts_full}"></span>'
        formatted_line = f"{ts_display}{span} {cleaned}\n"
        
        return {
            'time': ts_display,
            'full_ts': ts_full,
            'key': key,
            'content': cleaned,
            'raw': formatted_line
        }

    # =====================
    # Account 记账处理
    # =====================

    def _append_to_account_section(self, line_content):
        """
        处理记账条目并插入到 ## #Account 章节
        输入示例: (tradetype::$食物)(tradename::鸡蛋)(tradecost::-858)(tradetime::2026/2/12 00:19:36)
        目标格式:
        (tradetype::食物)
        (tradename::鸡蛋)
        (tradecost::-858)
        (tradetime::2026/2/12 00:19:36)
        """
        RED = '\033[91m'
        RESET = '\033[0m'

        try:
            if not self._config or not hasattr(self._config, 'DAILY_NOTE_DIR'):
                return False

            today_str = datetime.date.today().strftime('%Y-%m-%d')
            daily_note_path = os.path.join(self._config.DAILY_NOTE_DIR, f"{today_str}.md")

            if not os.path.exists(daily_note_path):
                return False

            # 解析并格式化
            groups = re.findall(r'\(([^)]+)\)', line_content)
            if not groups:
                return False

            formatted_lines = []
            
            # 使用字典暂存以便排序或过滤 (虽然这里顺序重要)
            # 用户期望顺序: type, name, cost, time
            
            for g in groups:
                if '::' in g:
                    k, v = g.split('::', 1)
                    k = k.strip()
                    v = v.strip()
                    
                    # 1. 清理 $ 符号
                    if '$' in v:
                        v = v.replace('$', '')
                    
                    # 2. 只有看到要求的字段才保留? 或者保留全量但格式化特定字段?
                    # 用户列出了 type, name, cost, time。如果有其他字段，暂且保留以免丢失数据。
                    
                    # 3. 格式化时间
                    if k == 'tradetime':
                        # v is like "2026/2/12 00:19:36"
                        # Extract HH:MM
                        # Try regex or split
                        time_match = re.search(r'(\d{1,2}[:：]\d{2})', v)
                        if time_match:
                            v = time_match.group(1) # 00:19
                    
                    formatted_lines.append(f"({k}::{v})\n")
                else:
                    formatted_lines.append(f"({g})\n")
            
            # 添加空行分隔 (Entry Spacer)
            formatted_lines.append('\n')

            # 读取文件并插入
            with open(daily_note_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            target_section = "## #Account"
            insert_idx = -1
            
            # 寻找章节
            for i, line in enumerate(lines):
                if line.strip() == target_section:
                    insert_idx = i + 1
                    break
            
            if insert_idx != -1:
                # 确保章节下有空行
                if insert_idx < len(lines) and lines[insert_idx].strip() != "":
                    lines.insert(insert_idx, '\n')
                    insert_idx += 1 # 移动插入点到空行之后
                elif insert_idx == len(lines):
                    lines.append('\n')
                    insert_idx += 1

                # 寻找下一个章节的位置
                next_section_idx = len(lines)
                for i in range(insert_idx, len(lines)):
                    if lines[i].strip().startswith("## "):
                        next_section_idx = i
                        break
                
                # 追加到该章节末尾（next_section_idx 之前）
                # 检查前一行是否为空行，如果不是则添加
                if next_section_idx > 0 and lines[next_section_idx - 1].strip() != "":
                    lines.insert(next_section_idx, '\n')
                    next_section_idx += 1
                
                # 插入内容
                for fl in reversed(formatted_lines):
                    lines.insert(next_section_idx, fl)
            else:
                # 章节不存在，追加
                # 确保前文有换行
                if lines and not lines[-1].endswith('\n'):
                    lines.append('\n')
                
                lines.append(f"\n{target_section}\n") # Section header
                lines.append('\n') # Spacer after header
                lines.extend(formatted_lines)
            
            with open(daily_note_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
            return True

        except Exception as e:
            print(f"{RED}❌ 写入账单异常: {e}{RESET}")
            return False
