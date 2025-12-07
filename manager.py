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
        # [已修改] 应此调试阶段的要求，仅处理今天的日记
        # 或优先处理。
        # 用户请求："只检测今天的日记"
        
        all_dates = {today_str}
        
        # 原始逻辑扫描所有内容，但用户希望专注于今天以减少干扰。
        # 但是，如果其他日期的源任务发生变化，我们必须确保对其进行监控。
        # 但对于嘈杂的 *格式化警报*，限制为今天很有用。
        
        # 让我们检查是否应该严格限制。
        # "你的控制台输出正在刷屏。只检查今天的日记。"
        # 好的，我将过滤下面的循环。

        # source_data_by_date 包含找到的有效任务的键。
        # 使用完整数据但过滤执行。
        
        source_data_by_date = self.sync_core.scan_all_source_tasks()
        
        # 将 all_dates 覆盖为仅今天
        all_dates = {today_str}
        # [严格] 跳过扫描其他每日文件
        # for f in daily_files: ... (已移除)
        
        # 确保我们只处理 today_str
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
        
        # [优雅关闭] 捕获 SIGTERM 以确保 'finally' 块运行
        def _term_handler(signum, frame):
            raise SystemExit("Received SIGTERM")
            
        signal.signal(signal.SIGTERM, _term_handler)
        
        try:
            while True:
                # [修复] 全局清理周期（同步前）
                FormatCore.fix_broken_tab_bullets_global()

                self.process_all_dates()
                
                # [修复] 全局清理周期（同步后）
                FormatCore.fix_broken_tab_bullets_global()
                
                time.sleep(Config.TICK_INTERVAL)
        except KeyboardInterrupt:
            # 异常处理交给 main.py
            raise 
        finally:
            self.sm.save()
