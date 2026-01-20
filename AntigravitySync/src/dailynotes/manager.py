"""
Fusion Manager - Antigravity Architecture
Unified single-threaded pipeline with priority-based execution.

Priority Order:
1. Internal (Dailynotes): Obsidian formatting, task sync - HIGH PRIORITY
2. External (Apple Sync): Apple Calendar sync - LOW PRIORITY, only when stable

Key Features:
- Dirty Flag Blocking: If internal modified file, skip external sync for this tick
- Tick-Based Scheduling: Fast for today, slow for historical/future dates
- [REFACTORED] Content-Hash Self-Awareness: Uses content identity instead of mtime
"""
import os
import sys
import time
import datetime
import signal
from config import Config
from .utils import Logger, FileUtils
from .format_core import FormatCore
from .state_manager import StateManager
from .sync import SyncCore
from external.apple_sync_adapter import AppleSyncAdapter


class FusionManager:
    """
    Unified sync manager implementing Antigravity Architecture.
    
    Core Logic:
    - 主权在内 (Sovereignty Inside): Dailynotes runs first
    - 脏标志阻断 (Dirty Flag): If internal modified, skip external
    - Tick分频调度 (Tick-Based Frequency): Today fast, others slow
    """
    
    def __init__(self):
        self.sm = StateManager()
        self.sync_core = SyncCore(self.sm)
        
        # [NEW] Initialize Apple Sync adapter (lazy, platform-safe)
        self.apple_sync = AppleSyncAdapter()
        
        # State tracking
        self.last_active_time = time.time()
        
        # [NEW] Tick-based scheduling for full date range scan
        self.tick_counter = 0  # Counts ticks since last full scan
        self.today_last_hash = None  # Track today's diary hash for change detection
        
        # [NEW] Track the date when tomorrow's note was last created (to avoid duplicates)
        self._tomorrow_note_created_date = None

    def check_debounce(self, filepath):
        """
        Check if file is stable for processing.
        [REFACTORED] Uses content-hash to distinguish system writes from user edits.
        """
        if not os.path.exists(filepath):
            return False
        
        # Read current content and calculate its hash
        content = FileUtils.read_content(filepath)
        if content is None:
            return False
        
        content_hash = FileUtils.calculate_hash(content)
        
        # If hash matches a system write, file is "self-owned" -> stable
        # Note: is_system_write() consumes the hash (one-time use)
        if FileUtils.is_system_write(content_hash):
            return True
        
        # Otherwise, check mtime-based cooldown (user is typing)
        mtime = FileUtils.get_mtime(filepath)
        idle = time.time() - mtime
        return idle >= Config.TYPING_COOLDOWN_SECONDS

    def is_user_active(self):
        """
        [Activity Detection] Check for "hot" files.
        If user is editing today's diary or recently modified any file, consider active.
        [REFACTORED] Uses content-hash to ignore system edits.
        """
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{today_str}.md")

        if os.path.exists(daily_path):
            # Check if this is a system write (don't consume the hash)
            content = FileUtils.read_content(daily_path)
            if content:
                content_hash = FileUtils.calculate_hash(content)
                if FileUtils.check_system_write(content_hash):
                    return False  # System edit, not user activity

            # If file was modified by USER in the last 60 seconds, user is in "flow" state
            mtime = FileUtils.get_mtime(daily_path)
            if time.time() - mtime < 60:
                return True

        return False

    def check_today_changed(self) -> bool:
        """
        Check if today's diary content has changed since last check.
        Used to reset the tick counter for full date range scans.
        """
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{today_str}.md")
        
        if not os.path.exists(daily_path):
            return False
        
        content = FileUtils.read_content(daily_path)
        if content is None:
            return False
        
        current_hash = FileUtils.calculate_hash(content)
        
        if self.today_last_hash is None:
            # First check, initialize
            self.today_last_hash = current_hash
            return False
        
        if current_hash != self.today_last_hash:
            self.today_last_hash = current_hash
            return True
        
        return False

    def _maybe_create_tomorrow_note(self):
        """
        [NEW] Auto-create tomorrow's diary at 23:30.
        Only creates if:
        1. Current time is 23:30 or later (before midnight)
        2. Tomorrow's diary does not already exist
        3. Haven't already created it today (prevents duplicate creation in same day)
        """
        now = datetime.datetime.now()
        today_str = now.strftime('%Y-%m-%d')
        
        # Check if we've already created tomorrow's note today
        if self._tomorrow_note_created_date == today_str:
            return  # Already created today, skip
        
        # Only trigger at 23:30 or later (hour=23, minute>=30)
        if now.hour != 23 or now.minute < 30:
            return  # Not yet 23:30
        
        # Calculate tomorrow's date
        tomorrow = now.date() + datetime.timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        tomorrow_path = os.path.join(Config.DAILY_NOTE_DIR, f"{tomorrow_str}.md")
        
        # Skip if tomorrow's diary already exists
        if os.path.exists(tomorrow_path):
            Logger.info(f"📅 [预创建] 明天的日记已存在，跳过: {tomorrow_str}.md")
            self._tomorrow_note_created_date = today_str
            return
        
        # Create from template or basic scaffold
        if os.path.exists(Config.TEMPLATE_FILE):
            try:
                tmpl_lines = FileUtils.read_file(Config.TEMPLATE_FILE)
                if tmpl_lines:
                    Logger.info(f"📅 [预创建] 23:30 定时任务 - 从模板创建明天的日记: {tomorrow_str}.md")
                    FileUtils.write_file(tomorrow_path, tmpl_lines)
                    self._tomorrow_note_created_date = today_str
            except Exception as e:
                Logger.error_once(f"pre_create_fail_{tomorrow_str}", f"预创建明天日记失败: {e}")
        else:
            Logger.info(f"📅 [预创建] 未找到模版，创建基础骨架: {tomorrow_str}.md")
            base_scaffold = ["# Day planner\n", "\n", "# Journey\n", "\n"]
            FileUtils.write_file(tomorrow_path, base_scaffold)
            self._tomorrow_note_created_date = today_str

    def get_date_range(self) -> list:
        """
        Generate date strings from DAY_START to DAY_END relative to today.
        DAY_START = -1 means yesterday
        DAY_END = 6 means 6 days in the future
        """
        today = datetime.date.today()
        dates = []
        for delta in range(Config.DAY_START, Config.DAY_END + 1):
            target_date = today + datetime.timedelta(days=delta)
            date_str = target_date.strftime('%Y-%m-%d')
            # Skip dates before sync start date
            if date_str >= Config.SYNC_START_DATE:
                dates.append(date_str)
        return dates

    def process_single_date(self, date_str):
        """
        Process a single date: internal sync + formatting + Apple sync.
        Returns detailed result dict.
        """
        results = {
            "internal_mod": False,       # SyncCore/FormatCore logic changed Obsidian file
            "apple_to_obsidian": False,  # Apple sync changed Obsidian file (C->O)
            "obsidian_to_apple": False,  # Obsidian sync changed Apple Calendar (O->C)
            "skipped": False
        }

        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{date_str}.md")
        
        # Debounce check
        if os.path.exists(daily_path):
            content = FileUtils.read_content(daily_path)
            is_system_edit = False
            if content:
                content_hash = FileUtils.calculate_hash(content)
                is_system_edit = FileUtils.check_system_write(content_hash)
            
            if not is_system_edit:
                idle_duration = time.time() - FileUtils.get_mtime(daily_path)
                if idle_duration < Config.TYPING_COOLDOWN_SECONDS:
                    # User is typing, skip
                    results["skipped"] = True
                    return results

        # --- [PRIORITY 1] Obsidian Internal Processing ---
        if self.check_debounce(daily_path) or not os.path.exists(daily_path):
            try:
                # A. Task Flow (Projects <-> Daily)
                source_data_by_date = self.sync_core.scan_all_source_tasks()
                tasks_for_date = source_data_by_date.get(date_str, {})
                # Note: SyncCore.process_date currently doesn't return boolean, assuming it might modify tasks
                # but currently task movement logic is mainly in dispatch_project_tasks which is not called here directly?
                # Wait, SyncCore.process_date might invoke task movement if implemented.
                # Assuming scan_all_source_tasks + process_date covers internal logic.
                self.sync_core.process_date(date_str, tasks_for_date)

                # B. Formatting (FormatCore)
                if os.path.exists(daily_path):
                    if FormatCore.execute(daily_path):
                        results["internal_mod"] = True
                        Logger.info(f"   ✨ [Internal] 格式化完成: {date_str}")

            except Exception as e:
                Logger.error_once(f"sync_fail_{date_str}", f"内部同步异常 [{date_str}]: {e}")

        # --- [PRIORITY 2] Apple Calendar Sync ---
        should_sync_apple = False
        
        if results["internal_mod"]:
            should_sync_apple = True
            Logger.info(f"   ⚡ [Trigger] 内部修改触发立即同步: {date_str}")
        elif os.path.exists(daily_path) and self.check_debounce(daily_path):
            should_sync_apple = True

        if should_sync_apple:
            try:
                obs_mod, apple_mod = self.apple_sync.sync_day(date_str)
                results["apple_to_obsidian"] = obs_mod
                results["obsidian_to_apple"] = apple_mod
                
                if obs_mod or apple_mod:
                    Logger.info(f"   🍏 [Apple] {date_str} 同步成功")
                else:
                    Logger.info(f"   🍏 [Apple] {date_str} 未检测到任何改动")
            except Exception as e:
                Logger.error_once(f"apple_exec_fail_{date_str}", f"外部同步异常: {e}")

        return results

    def run(self):
        """
        Main event loop with tick-based scheduling.
        """
        def _term_handler(signum, frame):
            raise SystemExit("Received SIGTERM")

        signal.signal(signal.SIGTERM, _term_handler)

        TICK_INTERVAL = Config.TICK_INTERVAL
        FULL_SCAN_MULTIPLIER = Config.COMPLETE_TASKS_SYNC_INTERVAL

        Logger.info(f"🚀 融合引擎启动: Obsidian (Priority High) + Apple Calendar (Priority Low)")
        Logger.info(f"   Tick间隔: {TICK_INTERVAL}s | 全量扫描倍率: {FULL_SCAN_MULTIPLIER}x")
        Logger.info(f"   日期范围: DAY_START={Config.DAY_START} ~ DAY_END={Config.DAY_END}")

        try:
            while True:
                self.tick_counter += 1
                today_str = datetime.date.today().strftime('%Y-%m-%d')

                # --- [EVERY TICK] Fix global formatting issues ---
                FormatCore.fix_broken_tab_bullets_global()
                
                # --- [EVERY TICK] Check if it's 23:30 to pre-create tomorrow's diary ---
                self._maybe_create_tomorrow_note()

                # --- [EVERY TICK] Process today's diary ---
                res = self.process_single_date(today_str)

                # --- [CHECK] Change Detection & Reset ---
                reset_needed = False
                reset_reasons = []

                if res["internal_mod"]: reset_reasons.append("Obsidian 内部整理")
                if res["apple_to_obsidian"]: reset_reasons.append("Apple 日历变更")
                if res["obsidian_to_apple"]: reset_reasons.append("Obsidian 推送变更")

                if len(reset_reasons) > 0:
                    reset_needed = True
                    # Update local tracker to match the new state immediately, 
                    # preventing check_today_changed from flagging system writes as manual edits.
                    today_path = os.path.join(Config.DAILY_NOTE_DIR, f"{today_str}.md")
                    if os.path.exists(today_path):
                        content = FileUtils.read_content(today_path)
                        if content:
                            self.today_last_hash = FileUtils.calculate_hash(content)

                # Check for manual edits (User typed something)
                # check_today_changed will return True if hash is different from self.today_last_hash
                if self.check_today_changed():
                    if not reset_needed:
                        # Only report if it wasn't already covered by system actions
                        reset_needed = True
                        reset_reasons.append("今日日记变更(手动)")

                if reset_needed:
                    reason_str = " + ".join(reset_reasons)
                    Logger.info(f"   🔄 [Reset] {reason_str}，重置全量扫描倒计时")
                    self.tick_counter = 0

                # --- [FULL SCAN] Every FULL_SCAN_MULTIPLIER ticks ---
                if self.tick_counter >= FULL_SCAN_MULTIPLIER:
                    self.tick_counter = 0
                    Logger.info(f"   📅 [Full Scan] 执行全量日期范围扫描...")
                    
                    date_range = self.get_date_range()
                    for date_str in date_range:
                        if date_str == today_str:
                            continue  # Already processed
                        self.process_single_date(date_str)

                # --- [LIVE COUNTDOWN] ---
                for i in range(TICK_INTERVAL, 0, -1):
                    msg = f"\r[Wait] 下次检测倒计时: {i}s   "
                    sys.stdout.write(msg)
                    sys.stdout.flush()
                    time.sleep(1)
                
                sys.stdout.write("\r" + " " * 40 + "\r")
                sys.stdout.flush()

        except KeyboardInterrupt:
            raise
        finally:
            self.sm.save()
