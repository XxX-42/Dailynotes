"""
Fusion Manager - Antigravity Architecture v1.5
Event-Driven Sync Engine with Exponential Dynamic Scheduling.

Key Features:
- [v1.4] Event-Driven: Uses watchdog to monitor file changes
- [v1.4] Self-Write Detection: Ignores events triggered by script's own writes
- [v1.5] Exponential Scheduling: I(d) = 240 * exp(0.0068 * d) + 60
- Content-Hash Self-Awareness: Uses content identity instead of mtime
"""
import os
import sys
import re
import math
import time
import datetime
import signal
import threading
from config import Config
from .utils import Logger, FileUtils
from .format_core import FormatCore
from .state_manager import StateManager
from .sync import SyncCore
from external.apple_sync_adapter import AppleSyncAdapter

# watchdog 导入（带降级处理）
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Logger.error_once("watchdog_import", "⚠️ watchdog 库未安装，将使用轮询模式")


class ObsidianEventHandler(FileSystemEventHandler):
    """
    [v1.4] 文件变更事件处理器
    监听 Obsidian Vault 中的 .md 文件变动，触发同步逻辑。
    """
    
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self._last_event_time = {}  # 防抖追踪: {filepath: timestamp}
    
    def on_modified(self, event):
        """处理文件修改事件"""
        if event.is_directory:
            return
        
        filepath = event.src_path
        
        # 仅处理 .md 文件
        if not filepath.endswith('.md'):
            return
        
        # 排除目录检查
        if FileUtils.is_excluded(filepath):
            return
        
        # [关键] 防抖检查：避免短时间内重复触发
        now = time.time()
        last_time = self._last_event_time.get(filepath, 0)
        if now - last_time < Config.EVENT_DEBOUNCE_SECONDS:
            return
        self._last_event_time[filepath] = now
        
        # [关键] 自写入检测：读取内容哈希并检查是否为系统写入
        try:
            content = FileUtils.read_content(filepath)
            if content is None:
                return
            
            content_hash = FileUtils.calculate_hash(content)
            
            # 如果这是脚本自己的写入，立即丢弃事件
            if FileUtils.is_system_write(content_hash):
                Logger.debug(f"[Event] 忽略自写入事件: {os.path.basename(filepath)}")
                return
            
            # 用户编辑事件，触发同步
            Logger.info(f"📝 [Event] 检测到变更: {os.path.basename(filepath)}")
            self.manager.on_file_changed(filepath)
            
        except Exception as e:
            Logger.error_once(f"event_err_{filepath}", f"事件处理异常: {e}")


class FusionManager:
    """
    Unified sync manager implementing Antigravity Architecture.
    
    Core Logic:
    - 主权在内 (Sovereignty Inside): Dailynotes runs first
    - 脏标志阻断 (Dirty Flag): If internal modified, skip external
    - [v1.4] 事件驱动 (Event-Driven): watchdog 监听文件变更
    - [v1.5] 指数动态调度 (Exponential Scheduling): 非线性日期冷却
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
        
        # [v1.4] Observer 实例
        self._observer = None
        self._running = False
        
        # [v1.5] 动态调度状态：记录每个日期的上次同步时间戳
        self._last_full_sync_registry = {}  # {date_str: timestamp}

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
        """
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{today_str}.md")

        if os.path.exists(daily_path):
            content = FileUtils.read_content(daily_path)
            if content:
                content_hash = FileUtils.calculate_hash(content)
                if FileUtils.check_system_write(content_hash):
                    return False

            mtime = FileUtils.get_mtime(daily_path)
            if time.time() - mtime < 60:
                return True

        return False

    def check_today_changed(self) -> bool:
        """
        Check if today's diary content has changed since last check.
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
            self.today_last_hash = current_hash
            return False
        
        if current_hash != self.today_last_hash:
            self.today_last_hash = current_hash
            return True
        
        return False

    def _maybe_create_tomorrow_note(self):
        """
        [NEW] Auto-create tomorrow's diary at 23:30.
        """
        now = datetime.datetime.now()
        today_str = now.strftime('%Y-%m-%d')
        
        if self._tomorrow_note_created_date == today_str:
            return
        
        if now.hour != 23 or now.minute < 30:
            return
        
        tomorrow = now.date() + datetime.timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        tomorrow_path = os.path.join(Config.DAILY_NOTE_DIR, f"{tomorrow_str}.md")
        
        if os.path.exists(tomorrow_path):
            Logger.info(f"📅 [预创建] 明天的日记已存在，跳过: {tomorrow_str}.md")
            self._tomorrow_note_created_date = today_str
            return
        
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
        """
        today = datetime.date.today()
        dates = []
        for delta in range(Config.DAY_START, Config.DAY_END + 1):
            target_date = today + datetime.timedelta(days=delta)
            date_str = target_date.strftime('%Y-%m-%d')
            if date_str >= Config.SYNC_START_DATE:
                dates.append(date_str)
        return dates

    def process_single_date(self, date_str):
        """
        Process a single date: internal sync + formatting + Apple sync.
        Returns detailed result dict.
        """
        results = {
            "internal_mod": False,
            "apple_to_obsidian": False,
            "obsidian_to_apple": False,
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
                    results["skipped"] = True
                    return results

        # --- [PRIORITY 1] Obsidian Internal Processing ---
        if self.check_debounce(daily_path) or not os.path.exists(daily_path):
            try:
                source_data_by_date = self.sync_core.scan_all_source_tasks()
                tasks_for_date = source_data_by_date.get(date_str, {})
                self.sync_core.process_date(date_str, tasks_for_date)

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
            except Exception as e:
                Logger.error_once(f"apple_exec_fail_{date_str}", f"外部同步异常: {e}")

        return results

    def on_file_changed(self, filepath):
        """
        [v1.4] 事件驱动入口：文件变更时调用
        从文件路径提取日期并触发同步
        """
        filename = os.path.basename(filepath)
        
        # 尝试从文件名提取日期 (格式: YYYY-MM-DD.md)
        date_match = re.match(r'^(\d{4}-\d{2}-\d{2})\.md$', filename)
        
        if date_match:
            # 这是一个日记文件
            date_str = date_match.group(1)
            Logger.info(f"   🔄 [Sync] 触发日期同步: {date_str}")
            self.process_single_date(date_str)
        else:
            # 这是一个项目文件，触发今日同步
            today_str = datetime.date.today().strftime('%Y-%m-%d')
            Logger.info(f"   🔄 [Sync] 项目文件变更，触发今日同步")
            self.process_single_date(today_str)

    def _calculate_dynamic_interval(self, date_str) -> float:
        """
        [v1.5] 计算指定日期的动态同步间隔
        公式: I(d) = EXP_BASE * exp(EXP_COEFF * d) + EXP_OFFSET
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD)
        Returns:
            同步间隔（秒）
        """
        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            today = datetime.date.today()
            d = abs((target_date - today).days)  # 距离今天的天数
            
            # 指数拟合公式
            interval = Config.EXP_BASE * math.exp(Config.EXP_COEFF * d) + Config.EXP_OFFSET
            
            # 限制在最大值以内
            return min(interval, Config.DYNAMIC_SYNC_MAX_INTERVAL)
        except Exception:
            return Config.EXP_BASE + Config.EXP_OFFSET  # 默认 300 秒

    def _do_smart_cleanup(self):
        """
        [v1.5] 智能巡检：根据日期距离动态调度同步
        近距离日期高频扫描，远距离日期低频扫描
        """
        # 修复全局格式问题（每次巡检都执行，轻量级操作）
        FormatCore.fix_broken_tab_bullets_global()
        
        # 检查是否需要预创建明天的日记
        self._maybe_create_tomorrow_note()
        
        # 遍历日期范围，根据冷却时间决定是否同步
        now = time.time()
        date_range = self.get_date_range()
        
        # [v1.5.1] 清理过期记录，防止内存缓慢泄漏
        active_dates = set(date_range)
        for recorded_date in list(self._last_full_sync_registry.keys()):
            if recorded_date not in active_dates:
                del self._last_full_sync_registry[recorded_date]
        
        for date_str in date_range:
            last_sync = self._last_full_sync_registry.get(date_str, 0)
            interval = self._calculate_dynamic_interval(date_str)
            
            if now - last_sync >= interval:
                # 冷却时间已到，执行同步
                self.process_single_date(date_str)
                self._last_full_sync_registry[date_str] = now

    def run(self):
        """
        [v1.5] 事件驱动主循环
        混合动力模式：watchdog 事件 + 指数动态调度
        """
        def _term_handler(signum, frame):
            self._running = False
            raise SystemExit("Received SIGTERM")

        signal.signal(signal.SIGTERM, _term_handler)
        self._running = True

        Logger.info(f"🚀 事件驱动引擎启动: watchdog + 指数动态调度")
        Logger.info(f"   调度公式: I(d) = {Config.EXP_BASE} * exp({Config.EXP_COEFF} * d) + {Config.EXP_OFFSET}")
        Logger.info(f"   冷却上限: {Config.DYNAMIC_SYNC_MAX_INTERVAL}s | 事件防抖: {Config.EVENT_DEBOUNCE_SECONDS}s")
        Logger.info(f"   日期范围: DAY_START={Config.DAY_START} ~ DAY_END={Config.DAY_END}")

        # 初始化 watchdog Observer
        if WATCHDOG_AVAILABLE:
            try:
                self._observer = Observer()
                event_handler = ObsidianEventHandler(self)
                
                # 监听 Vault 根目录
                self._observer.schedule(event_handler, Config.VAULT_ROOT, recursive=True)
                self._observer.start()
                Logger.info(f"👁️ [Watchdog] 开始监听: {Config.VAULT_ROOT}")
            except Exception as e:
                Logger.error_once("observer_init", f"Watchdog 初始化失败: {e}")
                self._observer = None
        else:
            Logger.info("⚠️ [Watchdog] 不可用，使用纯轮询模式")

        # 启动时执行一次智能巡检
        self._do_smart_cleanup()

        # 主循环
        try:
            while self._running:
                # 让出 CPU 资源
                time.sleep(1)
                
                # 每秒执行智能巡检（轻量级时间戳比对）
                self._do_smart_cleanup()
                
        except KeyboardInterrupt:
            Logger.info("\n⏹️ 收到中断信号...")
        finally:
            # 优雅停止 Observer
            if self._observer:
                Logger.info("🛑 [Watchdog] 停止监听...")
                self._observer.stop()
                self._observer.join(timeout=3)
            
            self.sm.save()
            Logger.info("✅ 状态已保存，引擎已停止")

