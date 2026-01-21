"""
Fusion Manager - Antigravity Architecture v3.0 (Chronos Mode)
Pure Event-Driven Sync Engine - No Polling Required.

Key Features:
- [v3.0] Chronos Mode: Full event-driven, no polling
- [v3.0] Startup Full Sync: Scans past 1 year to future 10 years
- [v3.0] Event-Triggered Window Sync: Only syncs affected window on calendar change
- [v2.0] CFRunLoop Integration: Instant notification delivery
"""
import os
import sys
import re
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

# [v1.9] Native Calendar Monitor Import
try:
    from external.eventkit_wrapper import EventKitClient
    EK_AVAILABLE = True
except ImportError:
    EK_AVAILABLE = False
    EventKitClient = None

# watchdog 导入（带降级处理）
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    class FileSystemEventHandler:
        pass
    Logger.error_once("watchdog_import", "⚠️ watchdog 库未安装")


class ObsidianEventHandler(FileSystemEventHandler):
    """
    [v1.6] 文件变更事件处理器 - 支持原子写入
    """
    
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self._last_event_time = {}

    def _process_event(self, filepath, event_type):
        if not filepath.endswith('.md'):
            return
        
        if FileUtils.is_excluded(filepath):
            return

        Logger.info(f"🔎 [Watchdog] 捕获底层事件 ({event_type}): {os.path.basename(filepath)}")
        
        now = time.time()
        last_time = self._last_event_time.get(filepath, 0)
        if now - last_time < Config.EVENT_DEBOUNCE_SECONDS:
            Logger.debug(f"[Event] 防抖跳过: {os.path.basename(filepath)}")
            return
        self._last_event_time[filepath] = now
        
        try:
            content = FileUtils.read_content(filepath)
            if content is None:
                return
            
            content_hash = FileUtils.calculate_hash(content)
            
            if FileUtils.is_system_write(content_hash):
                Logger.debug(f"[Event] 忽略自写入事件: {os.path.basename(filepath)}")
                return
            
            Logger.info(f"📝 [Event] 检测到用户变更: {os.path.basename(filepath)}")
            self.manager.on_file_changed(filepath)
            
        except Exception as e:
            Logger.error_once(f"event_err_{filepath}", f"事件处理异常: {e}")

    def on_modified(self, event):
        if event.is_directory:
            return
        self._process_event(event.src_path, "MODIFIED")

    def on_moved(self, event):
        if event.is_directory:
            return
        self._process_event(event.dest_path, "MOVED")


class FusionManager:
    """
    [v3.0] Chronos Mode - Pure Event-Driven Sync Manager
    
    Architecture:
    - Startup: Full range sync (past 1 year to future 10 years)
    - Runtime: Pure event-driven, no polling
    - Calendar events trigger window sync (±15 days)
    - Midnight crossing triggers next day's note creation
    """
    
    def __init__(self):
        self.sm = StateManager()
        self.sync_core = SyncCore(self.sm)
        self.apple_sync = AppleSyncAdapter()
        
        # Observer instances
        self._observer = None
        self._ek_client = None
        if EK_AVAILABLE:
            try:
                self._ek_client = EventKitClient()
            except Exception as e:
                Logger.error_once("ek_init_fail", f"EventKitClient init failed: {e}")
                self._ek_client = None
        
        self._running = False
        self._registry_warmup_done = False
        
        # [v3.0] Chronos Mode
        self._calendar_dirty_flag = False
        self._last_midnight_check = datetime.date.today()
        self._startup_sync_done = False

    def process_single_date(self, date_str, is_event_trigger=False):
        """
        Process a single date: internal sync + formatting + Apple sync.
        [v3.0] Only creates note if calendar has events for that date.
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
                if not is_event_trigger and idle_duration < Config.TYPING_COOLDOWN_SECONDS:
                    results["skipped"] = True
                    return results

        # --- [PRIORITY 1] Obsidian Internal Processing ---
        try:
            tasks_for_date = self.sync_core.get_tasks_for_date(date_str)
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
        elif os.path.exists(daily_path):
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
        [v3.0] 事件驱动入口：文件变更时调用
        """
        filename = os.path.basename(filepath)
        
        if not self._registry_warmup_done:
            Logger.info("🔄 [Manager] Warming up TaskRegistry...")
            self.sync_core.initialize_registry()
            self._registry_warmup_done = True
        
        date_match = re.match(r'^(\d{4}-\d{2}-\d{2})\.md$', filename)
        
        if date_match:
            date_str = date_match.group(1)
            Logger.info(f"   🔄 [Sync] 触发日期同步: {date_str}")
            self.process_single_date(date_str, is_event_trigger=True)
        else:
            affected_dates = self.sync_core.process_file_event(filepath)
            
            if affected_dates:
                Logger.info(f"   🔄 [Sync] 项目文件变更，影响 {len(affected_dates)} 个日期")
                for date_str in affected_dates:
                    self.process_single_date(date_str, is_event_trigger=True)
            else:
                today_str = datetime.date.today().strftime('%Y-%m-%d')
                Logger.info(f"   🔄 [Sync] 项目文件变更（无任务），触发今日同步")
                self.process_single_date(today_str, is_event_trigger=True)

    def _on_calendar_push_event(self):
        """
        [v3.0] Callback for EventKit notification.
        Thread-safe: Just sets a flag.
        """
        self._calendar_dirty_flag = True

    def sync_recent_window(self):
        """
        [v3.1] 日历变更触发的窗口同步
        
        范围: 过去 CHRONOS_FULL_RANGE_PAST_DAYS 天 ~ 未来 CHRONOS_FULL_RANGE_FUTURE_YEARS 年
        性能优化: 仅同步日历中有事件的日期，避免遍历所有空白日期
        """
        if not self._ek_client:
            Logger.info("⚠️ [Chronos] EventKit 不可用，跳过窗口同步")
            return
        
        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=Config.CHRONOS_FULL_RANGE_PAST_DAYS)
        end_date = today + datetime.timedelta(days=Config.CHRONOS_FULL_RANGE_FUTURE_YEARS * 365)
        
        # 确保不早于 SYNC_START_DATE
        sync_start = datetime.datetime.strptime(Config.SYNC_START_DATE, '%Y-%m-%d').date()
        if start_date < sync_start:
            start_date = sync_start
        
        Logger.info(f"🔄 [Chronos] 窗口同步: {start_date} ~ {end_date}")
        
        # [性能优化] 使用 EventKit 批量获取有事件的日期，避免逐天遍历
        events_by_date = self._ek_client.fetch_range_events(
            start_date, 
            end_date, 
            Config.CHRONOS_EVENTKIT_BATCH_DAYS
        )
        
        if not events_by_date:
            Logger.info("📭 [Chronos] 窗口范围内无日历事件")
            return
        
        Logger.info(f"📅 [Chronos] 发现 {len(events_by_date)} 天有日历事件")
        
        # 只同步有事件的日期
        synced_count = 0
        for date_str in sorted(events_by_date.keys()):
            if date_str >= Config.SYNC_START_DATE:
                result = self.process_single_date(date_str, is_event_trigger=True)
                if result["apple_to_obsidian"] or result["obsidian_to_apple"]:
                    synced_count += 1
        
        Logger.info(f"✅ [Chronos] 窗口同步完成: {synced_count} 天有变动")

    def sync_full_range(self):
        """
        [v3.0] 全量同步：过去1年到未来10年
        仅同步日历中实际有事件的日期，避免创建大量空白笔记
        """
        if not self._ek_client:
            Logger.info("⚠️ [Chronos] EventKit 不可用，跳过全量同步")
            return
        
        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=Config.CHRONOS_FULL_RANGE_PAST_DAYS)
        end_date = today + datetime.timedelta(days=Config.CHRONOS_FULL_RANGE_FUTURE_YEARS * 365)
        
        # 确保不早于 SYNC_START_DATE
        sync_start = datetime.datetime.strptime(Config.SYNC_START_DATE, '%Y-%m-%d').date()
        if start_date < sync_start:
            start_date = sync_start
        
        Logger.info(f"🚀 [Chronos] 全量同步启动: {start_date} ~ {end_date}")
        
        # 获取日历中有事件的日期
        events_by_date = self._ek_client.fetch_range_events(
            start_date, 
            end_date, 
            Config.CHRONOS_EVENTKIT_BATCH_DAYS
        )
        
        if not events_by_date:
            Logger.info("📭 [Chronos] 日历范围内无事件")
            return
        
        Logger.info(f"📅 [Chronos] 发现 {len(events_by_date)} 天有日历事件")
        
        # 只同步有事件的日期
        synced_count = 0
        for date_str in sorted(events_by_date.keys()):
            if date_str >= Config.SYNC_START_DATE:
                result = self.process_single_date(date_str, is_event_trigger=True)
                if result["apple_to_obsidian"] or result["obsidian_to_apple"]:
                    synced_count += 1
        
        Logger.info(f"✅ [Chronos] 全量同步完成: {synced_count} 天有变动")

    def _check_midnight_crossing(self):
        """
        [v3.0] 检查是否跨越午夜，创建新的今日笔记
        """
        today = datetime.date.today()
        if today != self._last_midnight_check:
            Logger.info(f"🌙 [Chronos] 检测到跨越午夜: {self._last_midnight_check} -> {today}")
            self._last_midnight_check = today
            
            # 同步今天的日历
            today_str = today.strftime('%Y-%m-%d')
            self.process_single_date(today_str, is_event_trigger=True)

    def run(self):
        """
        [v3.0] Chronos Mode 主循环 - 纯事件驱动
        """
        def _term_handler(signum, frame):
            self._running = False
            raise SystemExit("Received SIGTERM")

        signal.signal(signal.SIGTERM, _term_handler)
        self._running = True

        Logger.info(f"🚀 Chronos Mode 启动 - 全事件驱动架构")
        Logger.info(f"   同步窗口: ±{Config.CHRONOS_SYNC_WINDOW_DAYS // 2} 天")
        Logger.info(f"   全量范围: 过去 {Config.CHRONOS_FULL_RANGE_PAST_DAYS} 天 ~ 未来 {Config.CHRONOS_FULL_RANGE_FUTURE_YEARS} 年")
        Logger.info(f"   循环间隔: {Config.CHRONOS_LOOP_INTERVAL} 秒")

        # 初始化 Watchdog
        if WATCHDOG_AVAILABLE:
            try:
                self._observer = Observer()
                event_handler = ObsidianEventHandler(self)
                self._observer.schedule(event_handler, Config.VAULT_ROOT, recursive=True)
                self._observer.start()
                Logger.info(f"👁️ [Watchdog] 开始监听: {Config.VAULT_ROOT}")
            except Exception as e:
                Logger.error_once("observer_init", f"Watchdog 初始化失败: {e}")
                self._observer = None

            # EventKit 监听
            if self._ek_client:
                try:
                    Logger.info("📅 [Watchdog] 启动 EventKit 监听...")
                    self._ek_client.start_watching(self._on_calendar_push_event)
                except Exception as e:
                    Logger.error_once("cal_ek_fail", f"无法启动日历监听: {e}")

        # [v3.0] 启动时全量同步
        if not self._startup_sync_done:
            Logger.info("🌅 [Chronos] 执行启动全量同步...")
            self.sync_core.initialize_registry()
            self._registry_warmup_done = True
            self.sync_full_range()
            self._startup_sync_done = True

        # 主循环
        try:
            from CoreFoundation import CFRunLoopRunInMode, kCFRunLoopDefaultMode
            
            while self._running:
                # [v3.0] 纯事件驱动：仅处理标志位
                if self._calendar_dirty_flag:
                    Logger.info(f"⚡ [Chronos] 检测到日历变更")
                    self.sync_recent_window()
                    self._calendar_dirty_flag = False
                
                # 检查午夜跨越
                self._check_midnight_crossing()
                
                # 保持 RunLoop 唤醒
                CFRunLoopRunInMode(kCFRunLoopDefaultMode, Config.CHRONOS_LOOP_INTERVAL, False)
                
        except KeyboardInterrupt:
            Logger.info("\n⏹️ 收到中断信号...")
        finally:
            if self._observer:
                Logger.info("🛑 [Watchdog] 停止监听 Vault...")
                self._observer.stop()
                self._observer.join(timeout=3)
            
            if self._ek_client:
                Logger.info("🛑 [Watchdog] 停止监听 Calendar...")
                self._ek_client.stop_watching()
            
            self.sm.save()
            Logger.info("✅ 状态已保存，Chronos 引擎已停止")
