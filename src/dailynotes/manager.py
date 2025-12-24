import os
import time
import datetime
import signal
import math
from config import Config
from config import Config
from .utils import Logger, FileUtils
from .format_core import FormatCore
from .state_manager import StateManager
from .sync import SyncCore


class FusionManager:
    def __init__(self):
        self.sm = StateManager()
        self.sync_core = SyncCore(self.sm)
        # [状态] 上一次检测到活跃的时间 (用于计算惰性)
        self.last_active_time = time.time()

    def check_debounce(self, filepath):
        if not os.path.exists(filepath): return False
        mtime = FileUtils.get_mtime(filepath)
        idle = time.time() - mtime
        return idle >= Config.TYPING_COOLDOWN_SECONDS

    def is_user_active(self):
        """
        [活跃检测] 检查是否有“热”文件。
        如果用户正在编辑今天的日记，或者最近修改了任何文件，视为活跃。
        """
        # 1. 检查今天的日记 (最常用入口)
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{today_str}.md")

        if os.path.exists(daily_path):
            mtime = FileUtils.get_mtime(daily_path)
            # 如果文件在过去 60秒内被修改过，视为用户正处于"心流"状态
            if time.time() - mtime < 60:
                return True

        return False

    def process_all_dates(self):
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        all_dates = {today_str}

        # 1. 获取源任务数据 (SyncCore 内部也会过滤，这里拿到的都是合法的)
        source_data_by_date = self.sync_core.scan_all_source_tasks()

        # 2. 合并涉及的所有日期
        all_dates.update(source_data_by_date.keys())

        # 3. 遍历处理所有日期
        for date_str in list(all_dates):  # 使用 list 副本以防迭代中修改

            # --- [TIME GATE] 时间门控拦截 ---
            # 如果日期早于设定值，直接忽略，不读不写不处理
            if date_str < Config.SYNC_START_DATE:
                continue
            # ------------------------

            daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{date_str}.md")

            if os.path.exists(daily_path):
                idle_duration = time.time() - FileUtils.get_mtime(daily_path)
                wait_time = Config.TYPING_COOLDOWN_SECONDS - idle_duration
                if wait_time > 0: time.sleep(wait_time)

            if self.check_debounce(daily_path) or (not os.path.exists(daily_path) and date_str in source_data_by_date):
                try:
                    tasks_for_date = source_data_by_date.get(date_str, {})
                    self.sync_core.process_date(date_str, tasks_for_date)
                except Exception as e:
                    Logger.error_once(f"sync_fail_{date_str}", f"同步异常 [{date_str}]: {e}")

                # [RESTORED] 恢复日记格式化
                # 注意：FormatCore 现已更新为"靶向格式化"，只会触碰 # Day planner 和 # Journey
                # 其他区域（如 Log, Sport）会被安全忽略。
                if os.path.exists(daily_path):
                    FormatCore.execute(daily_path)

    def run(self):
        def _term_handler(signum, frame):
            raise SystemExit("Received SIGTERM")

        signal.signal(signal.SIGTERM, _term_handler)

        # --- [Adaptive Engine] 变速箱参数 ---
        MIN_INTERVAL = 3.0  # 战斗模式：3秒 (0~1分钟)
        MAX_INTERVAL = 15.0  # 巡航模式：15秒 (30分钟后)
        RAMP_UP_TIME = 1800  # 爬坡时间：30分钟 (1800秒)

        # 对数增长模型: I(t) = A + B * ln(t + 1)
        A = MIN_INTERVAL
        B = (MAX_INTERVAL - MIN_INTERVAL) / math.log(RAMP_UP_TIME + 1)

        Logger.info(f"🚀 启动自适应变速引擎: 活跃 {MIN_INTERVAL}s <-> 静默 {MAX_INTERVAL}s")

        try:
            while True:
                # 1. 执行核心任务
                FormatCore.fix_broken_tab_bullets_global()
                self.process_all_dates()
                FormatCore.fix_broken_tab_bullets_global()

                # 2. [感知] 用户还在吗？
                if self.is_user_active():
                    # 发现编辑动作！重置计时器，瞬间拉回战斗模式
                    self.last_active_time = time.time()

                # 3. [计算] 下一次睡多久
                idle_seconds = time.time() - self.last_active_time

                if idle_seconds < 60:
                    # 0~1分钟：保持最高警惕
                    dynamic_interval = MIN_INTERVAL
                else:
                    # 1分钟后：开始对数退避
                    dynamic_interval = A + B * math.log(idle_seconds + 1)

                # 封顶限制 (防止睡死)
                if dynamic_interval > MAX_INTERVAL:
                    dynamic_interval = MAX_INTERVAL

                time.sleep(dynamic_interval)

        except KeyboardInterrupt:
            raise
        finally:
            self.sm.save()