"""
Fusion Manager - Antigravity Architecture
Unified single-threaded pipeline with priority-based execution.

Priority Order:
1. Internal (Dailynotes): Obsidian formatting, task sync - HIGH PRIORITY
2. External (Apple Sync): Apple Calendar sync - LOW PRIORITY, only when stable

Key Features:
- Dirty Flag Blocking: If internal modified file, skip external sync for this tick
- Frequency Layering: Internal 3s tick, External 10s minimum interval
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
# [NEW] Import external sync adapter
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
        
        # [NEW] Apple Sync frequency limiting
        self.last_apple_sync_time = 0
        self.APPLE_SYNC_INTERVAL = 10  # Minimum 10 seconds between external syncs

    def check_debounce(self, filepath):
        """Check if file has been idle long enough for processing."""
        if not os.path.exists(filepath):
            return False
        mtime = FileUtils.get_mtime(filepath)
        idle = time.time() - mtime
        return idle >= Config.TYPING_COOLDOWN_SECONDS

    def is_user_active(self):
        """
        [Activity Detection] Check for "hot" files.
        If user is editing today's diary or recently modified any file, consider active.
        """
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{today_str}.md")

        if os.path.exists(daily_path):
            mtime = FileUtils.get_mtime(daily_path)
            # If file was modified in the last 60 seconds, user is in "flow" state
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
        source_data_by_date = self.sync_core.scan_all_source_tasks()
        all_dates.update(source_data_by_date.keys())

        # 2. Process all dates
        for date_str in list(all_dates):
            # --- [TIME GATE] Skip dates before start date ---
            if date_str < Config.SYNC_START_DATE:
                continue

            daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{date_str}.md")

            # --- [PRIORITY 1] Debounce and existence check ---
            if os.path.exists(daily_path):
                idle_duration = time.time() - FileUtils.get_mtime(daily_path)
                wait_time = Config.TYPING_COOLDOWN_SECONDS - idle_duration
                if wait_time > 0:
                    # User is typing, skip ALL operations including Apple Sync
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
                            Logger.info(f"   ✨ [Internal] 格式化完成，跳过本轮外部同步: {date_str}")

                except Exception as e:
                    Logger.error_once(f"sync_fail_{date_str}", f"内部同步异常 [{date_str}]: {e}")

            # --- [PRIORITY 3] Apple Calendar Sync (External Logic) ---
            # Core mechanism: If internal processing modified the file (internal_modified),
            # the file state is unstable - DO NOT perform external sync!
            # Wait for next tick until internal processing considers file perfect.
            
            should_sync_apple = (
                not internal_modified and         # File is stable
                os.path.exists(daily_path) and    # File exists
                self.check_debounce(daily_path)   # User is not typing
            )

            # Frequency control: Don't run AppleScript every loop, too heavy
            time_since_last_apple = time.time() - self.last_apple_sync_time
            if should_sync_apple and time_since_last_apple > self.APPLE_SYNC_INTERVAL:
                try:
                    self.apple_sync.sync_day(date_str)
                    self.last_apple_sync_time = time.time()
                except Exception as e:
                    Logger.error_once(f"apple_exec_fail_{date_str}", f"外部同步异常: {e}")

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
                FormatCore.fix_broken_tab_bullets_global()

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
