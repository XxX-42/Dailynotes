import os
import time
import datetime
import signal
from config import Config
from utils import Logger, FileUtils, ProcessLock
from format_core import FormatCore
from state_manager import StateManager
from sync_core import SyncCore

class FusionManager:
    def __init__(self):
        self.sm = StateManager()
        self.sync_core = SyncCore(self.sm)

    def check_debounce(self, filepath):
        if not os.path.exists(filepath): return False
        mtime = FileUtils.get_mtime(filepath)
        idle = time.time() - mtime
        return idle >= Config.TYPING_COOLDOWN_SECONDS

    def process_all_dates(self):
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        # [MODIFIED] Only process TODAY's note as requested for this debugging phase
        # Or priority processing.
        # User request: "只检测今天的日记" (Only check today's diary)
        
        all_dates = {today_str}
        
        # Original logic scanned all, but user wants to focus on today to reduce noise.
        # However, we must ensure Source tasks for other dates are monitored if they change.
        # But for *formatting alerts* which are noisy, restricting to Today is useful.
        
        # Let's check if we should restrict strictly.
        # "Your console output is spamming. Only check today's diary."
        # OK, I will filter the loop below.

        # source_data_by_date contains keys for valid tasks found.
        # Use full data but filter execution.
        
        source_data_by_date = self.sync_core.scan_all_source_tasks()
        
        # Override all_dates to ONLY be Today
        all_dates = {today_str}
        # [STRICT] Skip scanning other daily files
        # for f in daily_files: ... (Removed)
        
        # Ensure we only process today_str
        all_dates = {today_str}

        for date_str in all_dates:
            daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{date_str}.md")

            if os.path.exists(daily_path):
                idle_duration = time.time() - FileUtils.get_mtime(daily_path)
                wait_time = Config.TYPING_COOLDOWN_SECONDS - idle_duration

                if wait_time > 0:
                    Logger.info(f"文件正忙 (闲置 {idle_duration:.2f}s)，等待 {wait_time:.2f}s...", date_str)
                    time.sleep(wait_time)

            if self.check_debounce(daily_path) or (not os.path.exists(daily_path) and date_str in source_data_by_date):
                try:
                    tasks_for_date = source_data_by_date.get(date_str, {})
                    self.sync_core.process_date(date_str, tasks_for_date)
                except Exception as e:
                    Logger.error_once(f"sync_fail_{date_str}", f"同步异常 [{date_str}]: {e}")

                if os.path.exists(daily_path):
                    if FormatCore.execute(daily_path):
                        Logger.info(f"格式化完成", date_str)

    def run(self):
        # 移除这里的 ProcessLock.acquire()，因为 main.py 已经处理过了
        # 移除原本的 print 头部信息，main.py 已经打印过了
        
        # [Graceful Shutdown] Capture SIGTERM to ensure 'finally' block runs
        def _term_handler(signum, frame):
            raise SystemExit("Received SIGTERM")
            
        signal.signal(signal.SIGTERM, _term_handler)
        
        try:
            while True:
                self.process_all_dates()
                time.sleep(Config.TICK_INTERVAL)
        except KeyboardInterrupt:
            # 异常处理交给 main.py
            raise 
        finally:
            self.sm.save()
