"""
Fusion Manager - Antigravity Architecture
Unified single-threaded pipeline with priority-based execution.

Priority Order:
1. Internal (Dailynotes): Obsidian formatting, task sync - HIGH PRIORITY
2. External (Apple Sync): Apple Calendar sync - LOW PRIORITY, only when stable

Key Features:
- Dirty Flag Blocking: If internal modified file, skip external sync for this tick
- Frequency Layering: Internal 3s tick, External 10s minimum interval (Per-Date)
- [REFACTORED] Content-Hash Self-Awareness: Uses content identity instead of mtime
"""
import os
import time
import datetime
import signal
import math
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
    - 频率分层 (Frequency Layering): Internal fast, External slow
    """
    
    def __init__(self):
        self.sm = StateManager()
        self.sync_core = SyncCore(self.sm)
        
        # [NEW] Initialize Apple Sync adapter (lazy, platform-safe)
        self.apple_sync = AppleSyncAdapter()
        
        # State tracking
        self.last_active_time = time.time()
        
        # [FIX] Apple Sync frequency limiting - PER DATE
        # Changed from scalar to dict to prevent thread starvation
        self.apple_sync_timers = {} 
        self.APPLE_SYNC_INTERVAL = 10  # Minimum 10 seconds between external syncs PER FILE

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

    def process_all_dates(self):
        """
        Main processing loop for all dates.
        Implements priority pipeline: Internal first, External second.
        """
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        all_dates = {today_str}

        # 1. Scan Obsidian internal tasks (SyncCore)
        # This might return historical dates if tasks were moved/modified
        source_data_by_date = self.sync_core.scan_all_source_tasks()
        all_dates.update(source_data_by_date.keys())

        # 2. Process all dates
        for date_str in list(all_dates):
            # --- [TIME GATE] Skip dates before start date ---
            if date_str < Config.SYNC_START_DATE:
                continue

            daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{date_str}.md")

            # --- [PRIORITY 1] Debounce and existence check ---
            # [REFACTORED] Use content-hash instead of mtime comparison
            if os.path.exists(daily_path):
                content = FileUtils.read_content(daily_path)
                is_system_edit = False
                if content:
                    content_hash = FileUtils.calculate_hash(content)
                    is_system_edit = FileUtils.check_system_write(content_hash)
                
                if not is_system_edit:
                    idle_duration = time.time() - FileUtils.get_mtime(daily_path)
                    wait_time = Config.TYPING_COOLDOWN_SECONDS - idle_duration
                    if wait_time > 0:
                        # User is typing (and it wasn't us), skip ALL operations
                        continue

            internal_modified = False

            # --- [PRIORITY 2] Obsidian Internal Processing (Dailynotes Logic) ---
            # Only execute when file appears "stable"
            if self.check_debounce(daily_path) or (not os.path.exists(daily_path) and date_str in source_data_by_date):
                try:
                    # A. Task Flow (Projects <-> Daily)
                    tasks_for_date = source_data_by_date.get(date_str, {})
                    self.sync_core.process_date(date_str, tasks_for_date)

                    # B. Formatting (FormatCore)
                    # FormatCore.execute returns True if file was modified
                    if os.path.exists(daily_path):
                        if FormatCore.execute(daily_path):
                            internal_modified = True
                            Logger.info(f"   ✨ [Internal] 格式化完成: {date_str}")

                except Exception as e:
                    Logger.error_once(f"sync_fail_{date_str}", f"内部同步异常 [{date_str}]: {e}")

            # --- [PRIORITY 3] Apple Calendar Sync (External Logic) ---
            # Logic:
            # 1. Immediate Push: If internal_modified is True, we MUST sync now. 
            #    We just changed the file, so we know it's in a valid state. 
            # 2. Lazy Pull: If no internal change, we respect the cooldown timer.
            
            should_sync_apple = False
            last_run = self.apple_sync_timers.get(date_str, 0)
            
            if internal_modified:
                # Scenario 1: Push Model (System just edited)
                should_sync_apple = True
                Logger.info(f"   ⚡ [Trigger] 内部修改触发立即同步: {date_str}")
            elif os.path.exists(daily_path) and self.check_debounce(daily_path):
                # Scenario 2: Pull Model (Check for Apple side changes)
                if time.time() - last_run > self.APPLE_SYNC_INTERVAL:
                    should_sync_apple = True

            if should_sync_apple:
                try:
                    # Execute sync
                    self.apple_sync.sync_day(date_str)
                    
                    # Update timer ONLY for this date
                    self.apple_sync_timers[date_str] = time.time()
                    
                    # [NEW] Log next sync time
                    next_sync_ts = self.apple_sync_timers[date_str] + self.APPLE_SYNC_INTERVAL
                    next_sync_time = datetime.datetime.fromtimestamp(next_sync_ts).strftime('%H:%M:%S')
                    Logger.info(f"   🍏 [Apple] {date_str} 同步完成，下次同步: {next_sync_time}")
                except Exception as e:
                    Logger.error_once(f"apple_exec_fail_{date_str}", f"外部同步异常: {e}")
            else:
                # [NEW] Show countdown for today's date when not syncing
                if date_str == today_str and os.path.exists(daily_path):
                    last_run = self.apple_sync_timers.get(date_str, 0)
                    if last_run > 0:
                        remaining = max(0, self.APPLE_SYNC_INTERVAL - (time.time() - last_run))
                        if remaining > 0:
                            next_sync_ts = last_run + self.APPLE_SYNC_INTERVAL
                            next_sync_time = datetime.datetime.fromtimestamp(next_sync_ts).strftime('%H:%M:%S')
                            Logger.debug(f"   ⏳ [Apple] {date_str} 下次同步: {next_sync_time} (剩余 {remaining:.1f}s)")

    def run(self):
        """Main event loop with adaptive frequency."""
        def _term_handler(signum, frame):
            raise SystemExit("Received SIGTERM")

        signal.signal(signal.SIGTERM, _term_handler)

        # --- [Adaptive Engine] Gear parameters ---
        MIN_INTERVAL = 3.0  # Battle mode: 3 seconds (0~1 minute)
        MAX_INTERVAL = 15.0  # Cruise mode: 15 seconds (30+ minutes)
        RAMP_UP_TIME = 1800  # Ramp time: 30 minutes (1800 seconds)

        # Logarithmic growth model: I(t) = A + B * ln(t + 1)
        A = MIN_INTERVAL
        B = (MAX_INTERVAL - MIN_INTERVAL) / math.log(RAMP_UP_TIME + 1)

        Logger.info(f"🚀 融合引擎启动: Obsidian (Priority High) + Apple Calendar (Priority Low)")
        Logger.info(f"   自适应变速引擎: 活跃 {MIN_INTERVAL}s <-> 静默 {MAX_INTERVAL}s")

        try:
            while True:
                # 1. Core tasks
                FormatCore.fix_broken_tab_bullets_global()
                self.process_all_dates()

                # 2. [Perception] Is user still there?
                if self.is_user_active():
                    # Editing detected! Reset timer, instantly return to battle mode
                    self.last_active_time = time.time()

                # 3. [Calculate] How long to sleep next
                idle_seconds = time.time() - self.last_active_time

                if idle_seconds < 60:
                    # 0~1 minute: Maximum alertness
                    dynamic_interval = MIN_INTERVAL
                else:
                    # 1+ minute: Start logarithmic backoff
                    dynamic_interval = A + B * math.log(idle_seconds + 1)

                # Cap limit (prevent sleeping forever)
                if dynamic_interval > MAX_INTERVAL:
                    dynamic_interval = MAX_INTERVAL

                time.sleep(dynamic_interval)

        except KeyboardInterrupt:
            raise
        finally:
            self.sm.save()
