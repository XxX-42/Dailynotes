import os
import sys
import time
import datetime
import threading
import re
import difflib
import random
import string

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
    
    @staticmethod
    def _generate_id(length=6):
        """生成随机 6 位字母数字 ID (Obsidian Block ID 风格)"""
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choices(chars, k=length))

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

    def _sync_obsidian_tasks_to_notes(self, note_name, current_notes_content):
        """
        [v5.4] 单向同步: Obsidian Unchecked Tasks -> Apple Notes
        机制:
        1. 格式: *ID*Content (*HH:MM:SS*Content)
        2. 扫描 Obsidian:
           - 收集所有 {ID: Content}。
           - 新任务自动生成 ID 并保存。
        3. 扫描 Apple Notes:
           - *ID*Content:
             - 若 ID 在 Obsidian 中:
               - 比较 Content。若不同 -> 更新 (Update)。
               - 若相同 -> 保持。
               - 标记该 ID 已处理。
             - 若 ID 不在 Obsidian 中 -> 删除 (Delete)。
        4. 追加 (Add):
           - 将 Obsidian 中未被处理的 ID 追加到 Apple Notes。
        """
        if not self._config or not hasattr(self._config, 'DAILY_NOTE_DIR'):
            return False, current_notes_content

        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_note_dir = getattr(self._config, 'DAILY_NOTE_DIR', None)
        if not daily_note_dir:
            return False, current_notes_content
            
        daily_note_path = os.path.join(daily_note_dir, f"{today_str}.md")
        if not os.path.exists(daily_note_path):
            return False, current_notes_content
            
        try:
            with open(daily_note_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            obsidian_changed = False
            # Key: ID, Value: Clean Content (Includes Checked & Unchecked)
            sync_target_tasks = {}
            # Set of all IDs found in Obsidian to detect manual deletions
            all_obsidian_task_ids = set()
            
            # Pattern for ANY task (checked or unchecked) to parse IDs and content
            # Group 1: Prefix (- [ ] or - [x])
            # Group 2: Content
            task_line_pat = re.compile(r'^(\s*-\s*\[[ xX]\]\s+)(.*)')
            # Specific pattern to identify brand new tasks that need IDs
            new_task_pat = re.compile(r'^\s*-\s*\[\s\]\s+(?!.*<span id=")')
            id_pat = re.compile(r'<span id="([^"]+)"(?: data-timestamps="[^"]*")?></span>')
            
            # [v7.0] Use Random ID for new tasks
            
            # [v4.0] 预扫描：检测到全新的待同步任务时()，延迟一定时间防打断打字
            has_new_task = False
            for line in lines:
                m = task_line_pat.match(line)
                if m:
                    content_tail = m.group(2)
                    is_unchecked = "[ ]" in m.group(1)
                    if is_unchecked and "#" in content_tail and not id_pat.search(content_tail):
                        has_new_task = True
                        break
            
            if has_new_task:
                delay = getattr(self._config, 'NEW_TASK_INJECTION_DELAY', 3.0)
                if delay > 0:
                    import time
                    self._log(f"⏳ 检测到新 Apple Notes 任务，为防打断打字，延迟 {delay} 秒后再注入主键...")
                    time.sleep(delay)
                    try:
                        with open(daily_note_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                    except Exception as e:
                        self._log(f"⚠️ 延迟后重新读取文件失败: {e}")
                        
            new_obsidian_lines = []
            
            # --- Step 1: Process Obsidian (Collect Data) ---
            for line in lines:
                m = task_line_pat.match(line)
                if m:
                    prefix = m.group(1)
                    content_tail = m.group(2)
                    id_match = id_pat.search(content_tail)
                    is_unchecked = "[ ]" in prefix
                    
                    if id_match:
                        # Case A: Existing Task (Checked or Unchecked) with ID
                        tid = id_match.group(1)
                        # [v7.4] Clean content: Remove ID span AND Timestamp
                        raw_clean = content_tail.replace(id_match.group(0), "")
                        # Remove leading timestamp (e.g. 01:34 or 01:59 - 02:31) to avoid "ID + Time + Content" in Apple Notes
                        clean_content = re.sub(r'^\s*\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})*\s*', '', raw_clean).strip()
                        if "#" in clean_content:
                            all_obsidian_task_ids.add(tid)
                            sync_target_tasks[tid] = clean_content
                        
                        new_obsidian_lines.append(line)
                    elif is_unchecked and "#" in content_tail:
                        # Case B: New Unchecked Task -> Assign RAND ID
                        # [v7.0] Random ID
                        rand_id = self._generate_id()
                        span = f'<span id="{rand_id}"></span>'
                        clean_content = content_tail.strip()
                        modified_line = f"{prefix}{span} {clean_content}"
                        if line.endswith('\n') and not modified_line.endswith('\n'):
                            modified_line += '\n'
                        
                        new_obsidian_lines.append(modified_line)
                        obsidian_changed = True
                        
                        sync_target_tasks[rand_id] = clean_content
                        all_obsidian_task_ids.add(rand_id)
                    else:
                        # Case C: Checked task without ID (Rare)
                        new_obsidian_lines.append(line)
                else:
                    new_obsidian_lines.append(line)

            # Update Obsidian File
            if obsidian_changed:
                with open(daily_note_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_obsidian_lines)
                self._log(f"📝 [Sync] Marked new tasks in Obsidian with IDs.")

            # --- Step 2: Process Apple Notes (Diff & Merge) ---
            if current_notes_content:
                note_lines = current_notes_content.splitlines()
            else:
                note_lines = []
                
            new_note_lines = []
            notes_changed = False
            
            # [v7.0] Regex to detect *ID*Content line.
            # ID can be Timestamp (OLD) or Alphanumeric (NEW).
            # We match strictly *ID* at start.
            note_line_pat = re.compile(r'^\*([a-zA-Z0-9:]+)\*(.*)')
            
            # Track which IDs we found in Apple Notes
            processed_ids = set()
            
            for nl in note_lines:
                strip_nl = nl.strip()
                m = note_line_pat.match(strip_nl)
                if m:
                    nid = m.group(1)
                    ncontent = m.group(2) # Content in Apple Notes
                    
                    if nid in sync_target_tasks:
                        # 1. Update Check (Checked or Unchecked)
                        obsidian_content = sync_target_tasks[nid].replace('\xa0', ' ').strip()
                        ncontent_clean = ncontent.replace('\xa0', ' ').strip()
                        
                        # [Fix] Normalize whitespace to avoid infinite loops (Apple Notes collapses spaces)
                        # Also remove HTML tags from Obsidian content before comparison/sync to avoid span loops.
                        clean_obsidian = re.sub(r'<[^>]+>', '', sync_target_tasks[nid]).strip()
                        
                        # [v8.6] 比较前剥离 Apple Notes 侧的 ✅，防止因 ✅ 差异触发覆写
                        ncontent_stripped_check = ncontent.replace('✅', '').strip()
                        norm_note = " ".join(ncontent_stripped_check.split())
                        norm_obsidian = " ".join(clean_obsidian.split())
                        
                        # *ID*Content 原始行永远不带 ✅，如果意外出现则剥离后重新比较
                        if '✅' in ncontent:
                            ncontent = ncontent.replace('✅', '').strip()
                            norm_note = " ".join(ncontent.split())
                        
                        if norm_note != norm_obsidian:
                            # Content changed in Obsidian -> Sync to Note
                            # We use the CLEAN content for Apple Notes update
                            self._log(f"✏️ [内容变更] 备忘录 VS Obsidian 内容不一致:\n   🍎 Note: {ncontent}\n   🟣 Obsid: {clean_obsidian}")
                            
                            updated_line = f"*{nid}*{clean_obsidian}"
                            new_note_lines.append(updated_line)
                            notes_changed = True
                            self._log(f"🔄 [同步] 正在更新任务 {nid} 到备忘录...")
                        elif ncontent != clean_obsidian:
                            # Same logical content, but different raw string (whitespace diff)
                            # We usually want to rewrite to match Obsidian perfectly
                            # But if it causes loop, we skip OR we log differently.
                            # Current logic: Skip update to avoid loop (since we use 'norm_' check above)
                            # Just keep the Note version to stabilize
                            new_note_lines.append(nl)
                            # self._log(f"📝 [格式忽略] 空白符差异 (已自动标准化): {nid}")
                        else:
                            # Same, keep
                            new_note_lines.append(nl)
                        
                        processed_ids.add(nid)
                    elif nid in all_obsidian_task_ids:
                        # 2. Safety Fallback (ID exists but content not in sync_target)
                        new_note_lines.append(nl)
                        processed_ids.add(nid)
                    else:
                        # 3. Validation from TaskRegistry (Global Archive Check)
                        roamer_task = None
                        try:
                            from dailynotes.sync.task_registry import get_registry
                            reg = get_registry()
                            if reg.is_initialized():
                                roamer_task = reg.get_task_by_id(nid)
                        except Exception as e:
                            self._log(f"⚠️ [NoteMonitor] 无法访问 TaskRegistry: {e}")
                        
                        if roamer_task:
                            # It's globally archived! Update Apple Notes content to match archived version
                            clean_obsidian = re.sub(r'<[^>]+>', '', roamer_task.get('pure', '')).strip()
                            norm_note = " ".join(ncontent.split())
                            norm_obsidian = " ".join(clean_obsidian.split())
                            
                            if norm_note != norm_obsidian and clean_obsidian:
                                self._log(f"✏️ [Roamer] 归档任务更新:\n   🍎 Note: {ncontent}\n   🟣 Obsid: {clean_obsidian}")
                                updated_line = f"*{nid}*{clean_obsidian}"
                                new_note_lines.append(updated_line)
                                notes_changed = True
                            elif ncontent != clean_obsidian and clean_obsidian:
                                new_note_lines.append(nl)
                            else:
                                new_note_lines.append(nl)
                            
                            processed_ids.add(nid)
                            self._log(f"🛡️ [Roamer] 保护了归档项目，避免在 Apple Notes 中被删: {nid}")
                        else:
                            # 4. Delete (ID is gone from Obsidian entirely)
                            self._log(f"🗑️ [Sync] 从 Apple Notes 移除任务 {nid} (包含 ID 的项目在全局已不存在)。")
                            notes_changed = True
                else:
                    # Regular line, keep
                    new_note_lines.append(nl)

            # --- Step 3: Append Missing Tasks ---
            added_count = 0
            restored_tasks = []
            
            # Iterate dict to preserve order
            for tid, tcontent in sync_target_tasks.items():
                if tid not in processed_ids:
                    # New in Obsidian OR Deleted in Notes -> Restore/Add
                    line_str = f"*{tid}*{tcontent}"
                    new_note_lines.append(line_str)
                    processed_ids.add(tid) # Mark as processed immediately
                    added_count += 1
                    restored_tasks.append(tid)
            
            if added_count > 0:
                notes_changed = True
                self._log(f"🔙 [Sync] Restoring/Adding missing tasks: {restored_tasks}")
            
            # --- Step 4: Write to Apple Notes ---
            if notes_changed:
                final_content = "\n".join(new_note_lines)
                if final_content and not final_content.endswith('\n'):
                     final_content += "\n"
                
                if self._reader.update_note_content(note_name, final_content):
                     msg = []
                     if added_count: msg.append(f"{added_count} Restored/Added")
                     self._log(f"📥 [Sync] Notes Updated: {', '.join(msg) or 'Modifications applied'}")
                     return True, final_content
            
            return False, current_notes_content

        except Exception as e:
            self._log(f"⚠️ [Sync Error] {e}")
            return False, current_notes_content

    # =====================
    # 核心轮询逻辑 (Modified)
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
            dummy_diff = list(difflib.unified_diff([], initial_lines, n=0, lineterm=''))
            
            # 调用处理逻辑 (会自动回写 ✅)
            self._process_diff(dummy_diff, initial_lines, note_name)
            
            # 如果发生了回写，刷新 last_content
            time.sleep(1)
            last_content = self._reader.get_note_content(note_name)
            
            # [v5.0] Initial Sync from Obsidian
            if last_content and last_content != "NOT_FOUND":
                 synced, new_text = self._sync_obsidian_tasks_to_notes(note_name, last_content)
                 if synced:
                     last_content = new_text
            
            last_hash = hash(last_content) if last_content else 0

        while self._running:
            try:
                time.sleep(self._polling_interval)

                # 跨日检测
                current_today = datetime.date.today()
                if current_today != today:
                    today = current_today
                    note_name = f"{today.year}/{today.month}/{today.day}"
                    self._log(f"🌙 [NoteMonitor] 跨日检测: 切换到 '{note_name}'")
                    last_hash = 0
                    last_content = ""
                    self._tomorrow_note_created = False
                    # 跨天后先确保新一天的 Obsidian 日记和 Apple Note 已存在，
                    # 否则后续 get_note_content 会一直拿到 NOT_FOUND，导致当天无法进入同步流程。
                    self._check_and_create_today_notes(today)

                # [v4.0] 23:55 自动创建次日日记
                self._check_create_tomorrow_note()

                current_content = self._reader.get_note_content(note_name)

                # 备忘录消失
                if current_content is None or current_content == "NOT_FOUND":
                    if last_hash != 0:
                        self._log("❌ [NoteMonitor] 备忘录消失!")
                        last_hash = 0
                    continue

                # [v5.0] 每一轮都检查 Obsidian 是否有新任务推送到 Apple Notes
                # 注意: 这会增加一次文件读操作，但对于单机环境通常可接受
                synced, new_text_v5 = self._sync_obsidian_tasks_to_notes(note_name, current_content)
                if synced:
                    current_content = new_text_v5

                current_hash = hash(current_content)
                # 使用 ANSI 清行序列来执行干净的行内刷新，防残影
                print(f"\r\033[2K   [DEBUG] Loop Tick - last_hash: {last_hash}, current_hash: {current_hash}, len: {len(current_content if current_content else '')}", end="", flush=True)

                if current_hash != last_hash:
                    print() # 退出单行刷新状态，补一个换行，防其他日志粘连
                    # [v8.9] 1s 延迟只在出现真正的心跳标记时触发
                    # 注意: 不检测 *ID* 格式（那是同步行，永远存在，会导致误触发）
                    if "(id=" in current_content or "（id=" in current_content:
                        self._log(f"⏳ [NoteMonitor] 检测到心跳特征变更，延迟 1.0 秒等待写入缓冲...")
                        time.sleep(1.0)
                        current_content = self._reader.get_note_content(note_name)
                        current_hash = hash(current_content)
                        
                        # 如果缓冲后内容又弹回了上一次的旧状态（极其罕见），跳过本次
                        if current_hash == last_hash:
                            self._log(f"⚠️ [NoteMonitor] 缓冲期后内容回跳，忽略本次心跳...")
                            continue

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
                import traceback
                self._log(f"⚠️ [NoteMonitor] 轮询异常: {e}")
                self._log(f"   [CRITICAL TRACEBACK]\n{traceback.format_exc()}")
                time.sleep(5)  # Backoff

    # =====================
    # 23:55 次日日记创建
    # =====================

    def _check_create_tomorrow_note(self):
        """
        [v4.0] 每天 23:55 自动创建次日日记文件
        [v4.3] 同时自动创建次日 Apple Note
        """
        if self._tomorrow_note_created:
            return  # 今天已经创建过了

        if not self._config:
            return

        now = datetime.datetime.now()

        # 只在 23:55:00 ~ 23:59:59 之间触发
        if now.hour == 23 and now.minute >= 55:
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
            tomorrow_str = tomorrow.strftime('%Y-%m-%d')
            # Apple Notes 标题格式: 2026/2/12 (无零填充)
            tomorrow_apple_title = f"{tomorrow.year}/{tomorrow.month}/{tomorrow.day}"
            
            daily_note_dir = getattr(self._config, 'DAILY_NOTE_DIR', None)

            # 1. 创建 Obsidian 日记
            if daily_note_dir:
                tomorrow_path = os.path.join(daily_note_dir, f"{tomorrow_str}.md")

                if not os.path.exists(tomorrow_path):
                    # 读取模板
                    template_content = self._read_template()

                    try:
                        with open(tomorrow_path, 'w', encoding='utf-8') as f:
                            f.write(template_content)
                        self._log(f"📅 [NoteMonitor] 次日 Obsidian 日记已创建: {tomorrow_str}.md")
                    except Exception as e:
                        self._log(f"❌ [NoteMonitor] 创建次日日记失败: {e}")
                else:
                    self._log(f"ℹ️ [NoteMonitor] 次日 Obsidian 日记已存在，跳过创建")

            # 2. 创建 Apple Note
            try:
                # 默认内容
                default_body = f"Daily Log {tomorrow_str}<br><br>"
                result = self._reader.create_note(tomorrow_apple_title, default_body)
                
                if result == "CREATED":
                    self._log(f"🍏 [NoteMonitor] 次日 Apple Note 已创建: '{tomorrow_apple_title}'")
                elif result == "EXISTS":
                    self._log(f"ℹ️ [NoteMonitor] 次日 Apple Note 已存在，跳过")
                else:
                    self._log(f"❌ [NoteMonitor] 创建次日 Apple Note 失败")
            except Exception as e:
                self._log(f"❌ [NoteMonitor] 调用 Apple Notes 接口异常: {e}")

            # 无论成功与否，标记为已尝试，避免在 23:55-23:59 期间重复疯狂调用
            self._tomorrow_note_created = True

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
## #stateofmind

## #takein

## #exercice

## #account
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
    # Obsidian Task Helper
    # =====================

    def _mark_obsidian_task_completed_with_time(self, task_id, completion_time):
        """
        [v7.0] 标记 Obsidian 任务完成，并使用双 ID 格式更新时间。
        [v8.0] 基于 TaskRegistry 实现对归档/流浪者任务的跨稳健追踪。
        Target Format: - [x] HH:MM<span id="RANDOM_ID"></span><span id="OLD_ID"></span> Content
        注意: 使用随机 ID 避免重复。
        """
        if not self._config or not hasattr(self._config, 'DAILY_NOTE_DIR'):
            return False

        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_note_dir = getattr(self._config, 'DAILY_NOTE_DIR', None)
        if not daily_note_dir:
            return False
            
        target_file_path = os.path.join(daily_note_dir, f"{today_str}.md")
        
        # [v8.0] Cross-file tracking using TaskRegistry
        try:
            from dailynotes.sync.task_registry import get_registry
            reg = get_registry()
            if reg.is_initialized():
                roamer_task = reg.get_task_by_id(task_id)
                if roamer_task and 'path' in roamer_task:
                    target_file_path = roamer_task['path']
        except Exception as e:
            self._log(f"⚠️ [NoteMonitor] Registry 寻址失败, 降级为当日志记: {e}")
            
        if not os.path.exists(target_file_path):
            self._log(f"⚠️ [NoteMonitor] 无法定位包含任务 {task_id} 的文件: {os.path.basename(target_file_path)}")
            return False
        
        self._log(f"   [DEBUG] 心跳写入目标: {os.path.basename(target_file_path)}")
            
        try:
            with open(target_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            updated = False
            
            # [v7.0] Use Random ID for completion event
            full_time_id = self._generate_id()
            disp_time = completion_time[:5] # HH:MM (Floor)
            
            try:
                dt = datetime.datetime.strptime(completion_time[:8], "%H:%M:%S")
                if dt.second > 0:
                    dt += datetime.timedelta(minutes=1)
                ceiled_time = dt.strftime("%H:%M")
            except Exception:
                ceiled_time = disp_time

            # Pattern to match the specific task ID, either in a span or a div
            target_id_pat = re.compile(rf'(<span id="{task_id}"(?: data-timestamps="([^"]*)")?></span>)')
            
            # Pattern to match EXISTING completion timestamp in gap
            existing_ts_pat = re.compile(r'^\s*(\d{2}:\d{2})<span id="([^"]+)"(?: data-timestamps="[^"]*")?></span>\s*$')

            new_lines = []
            for line in lines:
                id_search = target_id_pat.search(line)
                if id_search and ("- [ ]" in line or "- [x]" in line):
                    self._log(f"   [DEBUG] 找到目标行: {line.strip()[:80]}")
                    # We found the line.
                    full_id_tag = id_search.group(1)
                    div_timestamps = id_search.group(2) or ""
                    
                    parts = line.split(full_id_tag, 1)
                    pre_part = parts[0]
                    post_part = parts[1]
                    
                    cb_match = re.search(r'^(\s*)(-\s*\[.)\](.*)', pre_part)
                    
                    if cb_match:
                        indent = cb_match.group(1)
                        new_box = "- [x]"
                        gap_content = cb_match.group(3) 
                        
                        # [v7.0] Check if gap_content already has THIS time.
                        # If so, we do NOT generate a new random ID, to avoid flipping IDs on every poll.
                        gm = existing_ts_pat.match(gap_content)
                        if gm:
                            existing_time = gm.group(1)
                            existing_id = gm.group(2)
                            
                            # If the displayed time is same as completion time, we assume no change needed.
                            # This prevents infinite loops of "Replace ID A with ID B" if time matches.
                            if existing_time == disp_time:
                                # Just ensure Checked
                                if "- [ ]" in line:
                                    new_line = line.replace("- [ ]", "- [x]")
                                    if new_line != line:
                                        updated = True
                                        new_lines.append(new_line)
                                        self._log(f"✅ [同步] 修正任务状态 (时间一致，保持原 ID): {task_id}")
                                    else:
                                        new_lines.append(line)
                                else:
                                    new_lines.append(line)
                                continue

                        # [v7.9] Multi-Span & Start-End Logic -> [v9.0] div data-timestamps
                        # [v9.1] 首次完成不显示时间，但后续更新会加上时间 (形如 Start - End)
                        
                        full_span_id = completion_time # Use full time (possibly with seconds) as ID
                        
                        # Check what time string is currently displayed before the span tag
                        tm = re.match(r'^\s*([\d: -]+)\s*$', gap_content)
                        should_update = False
                        
                        if tm and any(c.isdigit() for c in tm.group(1)):
                             # Already has a visible time string (e.g. "10:00" or "10:00 - 10:05")
                             existing_time_str = tm.group(1).strip()
                             
                             parts = existing_time_str.split('-')
                             start_time = parts[0].strip()
                             last_time = parts[-1].strip()

                             if ceiled_time == last_time:
                                 # 可视化时间不变，但仍需更新 data-timestamps 记录新心跳
                                 new_insert = f" {start_time} - {ceiled_time}"
                                 should_update = True
                             else:
                                 # Update End Time (向上取整)
                                 new_insert = f" {start_time} - {ceiled_time}"
                                 self._log(f"   ⏱️ 时间覆盖: {existing_time_str} -> {new_insert.strip()}")
                                 should_update = True
                        else:
                             # No visible time string yet.
                             if div_timestamps:
                                 ts_list = [t.strip() for t in div_timestamps.split(',') if t.strip()]
                                 if len(ts_list) >= 2:
                                     # This is a subsequent heartbeat without currently visible time
                                     # We extract the SECOND timestamp as the true heartbeat start time
                                     start_ts = ts_list[1][:5]
                                     if ceiled_time != start_ts:
                                         new_insert = f" {start_ts} - {ceiled_time}"
                                         self._log(f"   ⏱️ 重建心跳时间区间 (从第二跳): {start_ts} -> {ceiled_time}")
                                     else:
                                         new_insert = f" {start_ts}"
                                     should_update = True
                                 elif len(ts_list) == 1:
                                     # Currently only 1 timestamp (the "creation/placeholder"). This is the 2nd overall (first true heartbeat).
                                     new_insert = f" {ceiled_time}"
                                     self._log(f"   ⏱️ 首次真实心跳打卡起点: {ceiled_time}")
                                     should_update = True
                                 else:
                                     new_insert = gap_content
                                     should_update = True
                             else:
                                 # Initial Time (向下取整), explicitly hiding the display time
                                 new_insert = gap_content
                                 self._log(f"   ⏱️ 首次完成任务，隐藏可视化时间")
                                 should_update = True
                            
                        # Reassemble
                        if should_update:
                            # 1. Parse existing trailing spans in post_part
                            trailing_span_pat = re.compile(r'^((?:<span id="[^"]+"></span>)+)')
                            ts_match = trailing_span_pat.match(post_part)
                            
                            collected_ids = [t.strip() for t in div_timestamps.split(',') if t.strip()]
                            
                            if ts_match:
                                spans_str = ts_match.group(1)
                                span_ids = re.findall(r'<span id="([^"]+)"></span>', spans_str)
                                collected_ids.extend(span_ids)
                                post_part = post_part[ts_match.end():]
                            
                            # 追加新时间戳（去重，保持顺序）
                            if full_span_id not in collected_ids:
                                collected_ids.append(full_span_id)
                            # 最终去重（防止历史数据中已有重复）
                            collected_ids = list(dict.fromkeys(collected_ids))
                            new_ts_str = ",".join(collected_ids)
                            
                            new_id_tag = f'<span id="{task_id}" data-timestamps="{new_ts_str}"></span>'
                            
                            new_line = f"{indent}{new_box}{new_insert}{new_id_tag}{post_part}"
                            
                            updated = True
                            new_lines.append(new_line)
                            self._log(f"✅ [同步] 更新 Obsidian 任务状态: {task_id}")
                            self._log(f"   ➕ 时间戳整合写入 div data-timestamps: {new_ts_str}")

                        else:
                             # Just ensure Checked
                            if "- [ ]" in line:
                                new_line = line.replace("- [ ]", "- [x]")
                                if new_line != line:
                                    updated = True
                                    new_lines.append(new_line)
                                    self._log(f"✅ [同步] 修正任务状态 (时间已存在): {task_id}")
        
                                else:
                                    new_lines.append(line)
                            else:
                                new_lines.append(line)
                            continue 
                            
                        # Skip appending original line since we handled it
                        continue

                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            if updated:
                with open(target_file_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                return True
            self._log(f"   [DEBUG] 心跳写入未触发 updated=True，返回 False")
            return False
        except Exception as e:
            self._log(f"❌ [Sync Error] 更新 Obsidian 任务失败: {e}")
            return False

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

        time_pat = re.compile(r'^\s*(\d{1,2}[:：]\d{2}(?:[:：]\d{2})?)')
        # [v7.0] Heartbeat Completion Pattern (Enhanced)
        # Supported formats:
        # 1. StartTime *ID* Content -> 22:24:24 *21:25:38*#B 打扫
        # 2. Content (id=*ID*)      -> #A 厄尔 （id=*21:25:38*
        # 3. StartTime Content (id=ID) -> 00:22:26 #A 厄尔 (id=22:46:52)
        # 4. Also support Chinese parens （id=...）
        # 5. [v7.0] Supports Random Alphanumeric IDs (e.g. a1b2c3)
        # 6. [v7.3] Supports Underscores in manual IDs
        
        # Regex explanation:
        # ^\s*                     : Start of line
        # (?:(\d{1,2}:\d{2}(?::\d{2})?)\s+)? : Group 1: Optional Time (e.g. 23:06:31)
        # .*?                      : Content
        # (?: ... )                : Non-capturing group for OR logic
        #   \*([a-zA-Z0-9:_]+)\*          : Group 2: *ID* (timestamp or random or manual)
        #   |
        #   \(\s*id=([a-zA-Z0-9:_]+)\s*\) : Group 3: (id=ID)
        #   |
        #   （\s*id=([a-zA-Z0-9:_]+)\s*） : Group 4: （id=ID）
        
        # Note: Time group removed from this pattern to decouple extraction
        completion_pat = re.compile(
            r'(?:\*([a-zA-Z0-9:_]+)\*?|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)'
        )

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
                    # Even if it's a MOD, the new content might need processing (e.g. heartbeat)
                    # We mark it as NOT used so it falls through to the ADD handler loop below?
                    # No, better to process it right here or force it to be checked.
                    # Simplest hack: Don't mark used_adds[matched_idx] = True if we want it processed.
                    # BUT we printed [MOD], so usually that implies we handled it visually.
                    
                    # Check if the NEW line has completion markers
                    # [v8.7] 只有旧行也含 ✅ 才跳过（说明上一轮已处理过）
                    # 如果旧行没有 ✅ 但新行有 ✅，说明是 Shortcut 刚打的卡，必须处理
                    if '✅' in adds[matched_idx] and '✅' in d_line:
                         self._log(f"   [DEBUG] MOD 旧行已含 ✅，跳过重复心跳处理: {adds[matched_idx].strip()[:60]}")
                         used_adds[matched_idx] = True
                    else:
                         # 排除 *ID*Content 原始同步行
                         if adds[matched_idx].strip().startswith('*'):
                              self._log(f"   [DEBUG] MOD 行是 *ID* 原始同步行，跳过心跳: {adds[matched_idx].strip()[:60]}")
                              used_adds[matched_idx] = True
                         else:
                              _mod_match = completion_pat.search(adds[matched_idx].strip())
                              if _mod_match:
                                   self._log(f"   [DEBUG] MOD Line Matched Heartbeat: {adds[matched_idx].strip()} -> fall through to ADD")
                                   used_adds[matched_idx] = False # Let it fall through to ADD loop
                              else:
                                   self._log(f"   [DEBUG] MOD Line DID NOT match Heartbeat: {adds[matched_idx].strip()}")
                                   used_adds[matched_idx] = True
                else:
                    self._log(f"{RED}[DEL] {d_line}{RESET}")

            for i, a_line in enumerate(adds):
                if not used_adds[i]:
                    stripped_line = a_line.strip()
                    suffix = ""
                    processed = False
                    
                    # 0. Check Completion Heartbeat (Highest Priority)
                    # e.g. 22:24:24 *21:25:38*#B 打扫
                    # 排除 *ID*Content 原始同步行（以 * 开头）
                    if stripped_line.startswith('*'):
                        comp_match = None
                    else:
                        comp_match = completion_pat.search(stripped_line)
                    if comp_match:
                        self._log(f"   [DEBUG] Heartbeat ADD Loop match: True, task extracted.")
                        
                        # Extract Time independently to avoid regex anchoring issues with invisible chars
                        time_match = time_pat.search(stripped_line)
                        comp_time = time_match.group(1) if time_match else None
                        
                        # Group 1, 2, 3: ID variants
                         # *ID* or (id=ID) or （id=ID）
                        task_id = comp_match.group(1) or comp_match.group(2) or comp_match.group(3)
                        
                        # Fallback for time if not present at start of line
                        if not comp_time:
                            # [v7.9] Use seconds for ID generation
                            comp_time = datetime.datetime.now().strftime('%H:%M:%S')
                        
                        # Action 1: Mark Obsidian Task Complete AND Update Time
                        marked = self._mark_obsidian_task_completed_with_time(task_id, comp_time)
                        
                        # [Changed] Do NOT append new line to Day Planner section.
                        # We only update the existing task line in place.
                        
                        if marked:
                            # 心跳更新成功，追加 ✅（避免重复）
                            if '✅' not in stripped_line:
                                suffix = " ✅"
                            processed = True
                            self._log(f"💓 [Heartbeat] Task {task_id} completed at {comp_time}")
                        else:
                            self._log(f"❌ [Heartbeat] Obsidian 写入失败! task_id={task_id}, comp_time={comp_time}")
                            processed = True  # 标记为已处理，避免 fallback 到 #takein

                    # 1. Check Time Entries (Water/Log/DayPlan)
                    is_time_entry = time_pat.search(stripped_line)
                    if not processed and is_time_entry and "✅" not in stripped_line:
                        # Prevent appending empty line states (just time with no content) from Shortcuts
                        # "15:35:12" or "15:35:12 ✅" -> Do not spam #takein
                        bare_text = time_pat.sub('', stripped_line).replace('✅', '').strip()
                        if not bare_text:
                            # It's an empty line marker, just skip it to avoid polluting #takein
                            processed = True
                        else:
                            # [v4.4] Day Planner Check (starts with "*")
                            # e.g. 17:55:48"*打游戏"
                            if self._is_day_plan_entry(stripped_line):
                                 if self._append_to_day_plan_section(a_line):
                                    suffix = " ✅"
                                    processed = True
                            
                            # Fallback to Water/Log (Takein)
                            elif self._append_to_daily_note(a_line):
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
                                    if suffix:
                                        current_lines[idx] = cl + suffix
                                        notes_updated = True
                                    break
                        except ValueError:
                            pass
                    
                    # [Removed duplicate print] We rely on _log for feedback.
                    if not processed:
                         # Only print valid ADDs that weren't processed (unknown lines)
                         # or maybe just debug output.
                         # print(f"{GREEN}[ADD] {a_line}{RESET}")
                         pass

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
        YELLOW = '\033[93m'
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

            # [v7.12] Defense: Prevent Heartbeat Data from entering Takein
            # Check if line looks like a heartbeat (contains *ID* or (id=...))
            # Ref: completion_pat from _process_diff
            import re
            is_heartbeat = re.search(r'(?:\*([a-zA-Z0-9:_]+)\*?|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)', line_content)
            if is_heartbeat:
                print(f"{YELLOW}⚠️ [Takein Skip] Detected Heartbeat Data, ignoring: {line_content.strip()}{RESET}")
                return False

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
        target_section = "## #takein"
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
        
        # **修复策略：先解析旧条目，然后开启严格的复合指纹匹配**
        # 取消对新条目的无脑追加，转而验证是否重复
        
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

        # **去重拦截核心逻辑**：检查是否已有完全一样的数据
        is_duplicate = False
        new_ts = new_parsed.get('full_ts', '')
        new_content = new_parsed.get('content', '')
        
        for e in entries:
            if e.get('full_ts') == new_ts and e.get('content') == new_content:
                is_duplicate = True
                break
                
        # 通过验证：无重复历史档案，方可加入合并序列
        if not is_duplicate:
            entries.append(new_parsed)

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
    # Day Planner 处理 (v4.4)
    # =====================

    def _is_day_plan_entry(self, line):
        """
        判断是否为 Day Planner 条目
        特征: 时间戳后跟随 "* (如 17:55:48"*打游戏")
        """
        return '"*' in line or '“*' in line

    def _append_to_day_plan_section(self, line_content):
        """
        [v4.8] 处理 # Day planner
        核心逻辑: 全局重组与合并
        1. 读取所有现有条目 + 新条目
        2. 按时间排序
        3. 遍历列表，合并连续且内容相同的条目
           - 判断逻辑: 内容相同则合并
        4. 格式化:
           - 单条目: 20:51
           - 多条目(即使同分): 20:51 -20:51 (如果有时间跨度)
           - 格式: "Start -End"
        """
        RED = '\033[91m'
        RESET = '\033[0m'

        try:
            if not self._config or not hasattr(self._config, 'DAILY_NOTE_DIR'):
                return False

            today_str = datetime.date.today().strftime('%Y-%m-%d')
            daily_note_dir = getattr(self._config, 'DAILY_NOTE_DIR', None)
            if not daily_note_dir:
                return False
                
            daily_note_path = os.path.join(daily_note_dir, f"{today_str}.md")

            if not os.path.exists(daily_note_path):
                return False

            # 1. 解析输入行 (New Entry)
            parsed_new = self._parse_day_plan_line(line_content)
            if not parsed_new:
                return False
            parsed_new['status'] = 'x'
            parsed_new['is_new'] = True

            # 2. 读取现有文件
            with open(daily_note_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 3. 定位 # Day planner 章节
            target_section = "# Day planner"
            start_idx = -1
            end_idx = -1

            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped == target_section:
                    start_idx = i + 1
                elif start_idx != -1:
                    if stripped.startswith('# ') or stripped.startswith('## '):
                        end_idx = i
                        break
            
            if start_idx == -1:
                return False

            if end_idx == -1:
                end_idx = len(lines)

            # 4. 提取章节内容并解析 existing entries
            section_lines = lines[start_idx:end_idx]
            all_entries = []
            
            # 正则: 支持 "HH:MM" 或 "HH:MM -HH:MM"
            ptn = re.compile(r'^(?:-\s*\[([xX\s])\]\s+)?(.+?)<span id="([^"]+)"></span>\s*(.*)')

            for sl in section_lines:
                sl_strip = sl.strip()
                if not sl_strip: continue
                
                m = ptn.match(sl_strip)
                if m:
                    status_char = m.group(1) if m.group(1) else 'x'
                    display_str = m.group(2).strip()
                    full_id = m.group(3)
                    content = m.group(4)
                    
                    all_entries.append({
                        'status': status_char,
                        'time_display': display_str,
                        'time_full': full_id, # Assumed to be start_id
                        'content': content,
                        'raw': sl,
                        'is_new': False
                    })
            
            # 加入新条目
            all_entries.append(parsed_new)

            # 5. 全局排序 (按 Start ID)
            all_entries.sort(key=lambda x: x['time_full'])

            # 6. 合并连续相同内容的条目
            final_entries = []
            
            def get_end_time(display_str):
                # "20:51" -> "20:51"
                # "20:51 -20:56" -> "20:56"
                parts = display_str.split('-')
                return parts[-1].strip()

            if all_entries:
                curr = all_entries[0]
                curr_content = curr['content'].strip()
                curr_start_display = curr['time_display'].split('-')[0].strip()
                curr_end_display = get_end_time(curr['time_display'])
                curr_status = curr.get('status', 'x')
                curr_start_id = curr['time_full']
                curr_end_id = curr['time_full'] # Track end ID to detect merge span

                for i in range(1, len(all_entries)):
                    next_e = all_entries[i]
                    next_content = next_e['content'].strip()
                    
                    if next_content == curr_content:
                        # Merge! 
                        curr_end_display = get_end_time(next_e['time_display'])
                        # Update end_id to the NEWEST entry's ID
                        # Note: all_entries is sorted by time_full (Start ID).
                        # We assume next_e is later than curr.
                        # But wait, next_e['time_full'] is ITS start time.
                        # If next_e was a range, we don't know ITS end time ID strictly from struct unless we parsed it.
                        # But we re-parse from scratch mostly.
                        # Let's assume next_e['time_full'] is sufficient to prove "difference".
                        curr_end_id = next_e['time_full'] 
                    else:
                        # Flush
                        final_entries.append({
                            'start': curr_start_display,
                            'end': curr_end_display,
                            'status': curr_status,
                            'start_id': curr_start_id,
                            'end_id': curr_end_id,
                            'content': curr_content
                        })
                        
                        # New
                        curr = next_e
                        curr_content = curr['content'].strip()
                        curr_start_display = curr['time_display'].split('-')[0].strip()
                        curr_end_display = get_end_time(curr['time_display'])
                        curr_status = curr.get('status', 'x')
                        curr_start_id = curr['time_full']
                        curr_end_id = curr['time_full']
                
                # Flush last
                final_entries.append({
                    'start': curr_start_display,
                    'end': curr_end_display,
                    'status': curr_status,
                    'start_id': curr_start_id,
                    'end_id': curr_end_id,
                    'content': curr_content
                })

            # 7. 生成最终行
            new_content_lines = []
            if section_lines and section_lines[0].strip() == "":
                new_content_lines.append("\n")
            
            def get_ceiling_end_time(full_ts):
                """
                根据完整时间戳 HH:MM:SS 计算结束时间
                逻辑: 秒数向上取整。如果 SS > 0，则 MM + 1。
                """
                try:
                    parts = full_ts.split(':')
                    if len(parts) >= 3:
                        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
                        if s > 0:
                            m += 1
                            if m >= 60:
                                m = 0
                                h += 1
                            if h >= 24:
                                h = 0
                        return f"{h:02d}:{m:02d}"
                    return full_ts[:5] # HH:MM
                except:
                    return full_ts

            for e in final_entries:
                # Decide Format
                # If IDs differ, it means we merged something -> Show Range
                if e['start_id'] != e['end_id']:
                     # Range Format: "Start - Ceiling(EndID)"
                     # Start uses existing display to preserve manual edits if any, or simple HH:MM
                     # End is recalculated based on Seconds Ceiling logic
                     new_end = get_ceiling_end_time(e['end_id'])
                     time_str = f"{e['start']} - {new_end}"
                else:
                     # Single Entry
                     time_str = e['start']
                
                # Format: - [x] Time <span...> Content
                line_str = f"- [{e['status']}] {time_str}<span id=\"{e['start_id']}\"></span> {e['content']}\n"
                new_content_lines.append(line_str)
            
            if new_content_lines and not new_content_lines[-1].endswith('\n'):
                new_content_lines[-1] += '\n'
            new_content_lines.append('\n')

            # 8. Replace in file
            final_lines = lines[:start_idx] + new_content_lines + lines[end_idx:]
            
            with open(daily_note_path, 'w', encoding='utf-8') as f:
                f.writelines(final_lines)

            return True

        except Exception as e:
            print(f"{RED}❌ 写入 Day Planner 异常: {e}{RESET}")
            return False

    def _parse_day_plan_line(self, raw_line):
        """
        解析: 17:55:48"*打游戏"
        """
        raw_line = raw_line.strip()
        match = re.match(r'^(\d{1,2}[:：]\d{2}(?:[:：]\d{2})?)', raw_line)
        if not match: return None
        
        ts_full = match.group(1)
        ts_end = match.end()
        
        parts = re.split(r'[:：]', ts_full)
        ts_display = f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else ts_full
        
        remain = raw_line[ts_end:].strip()
        content = remain
        if content.startswith('"') or content.startswith('“'):
             content = content[1:]
        if content.startswith('*'):
             content = content[1:]
             
        content = content.replace('"', '').replace('”', '').strip()
        
        return {
            'time_display': ts_display,
            'time_full': ts_full,
            'content': content
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
            # 解析并提取数据
            groups = re.findall(r'\(([^)]+)\)', line_content)
            if not groups:
                return False

            data = {}
            for g in groups:
                if '::' in g:
                    k, v = g.split('::', 1)
                    k = k.strip()
                    v = v.strip().replace('$', '')
                    
                    # [v2.1] 保留原始名称，不进行 KEYWORD_MAPPING 映射 (除非用户明确要求)
                    # 之前由于解析逻辑可能会误触映射，这里显式保留原始格式
                    data[k] = v
            
            # 必须包含核心字段
            if 'tradetype' not in data and 'tradecost' not in data:
                return False

            # 字段预处理
            t_time = data.get('tradetime', datetime.datetime.now().strftime('%H:%M'))
            time_match = re.search(r'(\d{1,2}[:：]\d{2})', t_time)
            if time_match:
                t_time = time_match.group(1)

            t_type = data.get('tradetype', '').strip()
            t_name = data.get('tradename', '').strip()
            t_cost = data.get('tradecost', '0').strip()

            # 构造表格行字符串 (Markdown 风格)
            new_table_row = f"| {t_time} | {t_type} | {t_name} | {t_cost} |\n"

            # 读取文件并插入
            with open(daily_note_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 二、防重复检测与清洗
            # 1. 检查表格行是否已存在
            row_content_to_check = f"| {t_time} | {t_type} | {t_name} | {t_cost} |"
            is_duplicate = False
            
            # 2. 构建需要清洗的原始括号行匹配集合
            # 原始数据是多行格式, 每行一个 (tradeXXX::value), 需要逐行匹配
            raw_patterns_to_clean = set()
            for field_key, field_val in data.items():
                raw_patterns_to_clean.add(f"({field_key}::{field_val})")
            
            new_doc_lines = []
            cleaned_any_raw = False
            
            for line in lines:
                # 检查是否是表格行重复
                if row_content_to_check in line:
                    is_duplicate = True
                
                # 检查当前行是否是残留的原始括号行 (逐行独立匹配)
                # 例如: "(tradetype::-食物)\n" 或 "(tradename::99)\n"
                line_stripped = line.strip()
                if line_stripped in raw_patterns_to_clean:
                    cleaned_any_raw = True
                    continue  # 剔除此行
                
                new_doc_lines.append(line)
            
            # 如果剔除了原始行，需要写回文件
            if cleaned_any_raw:
                lines = new_doc_lines
                self._log(f"🧹 [Account] 已清洗 {len(raw_patterns_to_clean)} 条残留原始括号行")
            
            if is_duplicate:
                # 表格行已存在，不需要再插入
                if cleaned_any_raw:
                    # 虽然表格已存在，但需要写回清洗结果
                    with open(daily_note_path, 'w', encoding='utf-8') as f:
                        f.writelines(lines)
                self._log(f"⏭️ [Account] 跳过重复记账: {t_time} - {t_name} ({t_cost})")
                return True


            target_section = "## #account"
            section_start_idx = -1
            
            # 寻找章节
            for i, line in enumerate(lines):
                if line.strip().lower() == target_section.lower():
                    section_start_idx = i
                    break
            
            if section_start_idx == -1:
                # 章节不存在，追加
                if lines and not lines[-1].endswith('\n'):
                    lines.append('\n')
                lines.append(f"\n{target_section}\n\n")
                lines.append("| 时间 | 类型 | 名称 | 金额 |\n")
                lines.append("| --- | --- | --- | --- |\n")
                lines.append(new_table_row)
                self._log(f"📝 [Account] 已创建 #account 章节并写入: {t_name}")
            else:
                # 章节存在，寻找表格或在章节下方创建
                # 扫描章节下方内容
                table_header_idx = -1
                last_table_row_idx = -1
                
                next_header_idx = len(lines)
                for i in range(section_start_idx + 1, len(lines)):
                    l_strip = lines[i].strip()
                    if l_strip.startswith("## "):
                        next_header_idx = i
                        break
                    if l_strip.startswith("| 时间 |") or (l_strip.startswith("|") and "金额" in l_strip):
                        table_header_idx = i
                    elif table_header_idx != -1 and l_strip.startswith("|"):
                        last_table_row_idx = i
                
                if table_header_idx == -1:
                    # 没找到表格，在章节下方插入新表格
                    insert_pos = section_start_idx + 1
                    # 确保有一个空行
                    if insert_pos < len(lines) and lines[insert_pos].strip() != "":
                         lines.insert(insert_pos, "\n")
                         insert_pos += 1
                    
                    lines.insert(insert_pos, "| 时间 | 类型 | 名称 | 金额 |\n")
                    lines.insert(insert_pos + 1, "| --- | --- | --- | --- |\n")
                    lines.insert(insert_pos + 2, new_table_row)
                    self._log(f"📝 [Account] 已新建表格并写入: {t_name}")
                else:
                    # 找到表格，追加到末尾
                    if last_table_row_idx != -1:
                        # 在原有表格最后一行之后插入
                        lines.insert(last_table_row_idx + 1, new_table_row)
                    else:
                        # 只有表头和分隔行，在分隔行 (table_header_idx + 1) 后插入
                        lines.insert(table_header_idx + 2, new_table_row)
                    self._log(f"📝 [Account] 已同步至表格: {t_name}")
            
            with open(daily_note_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

                
            return True

        except Exception as e:
            print(f"{RED}❌ 写入账单异常: {e}{RESET}")
            return False
