"""
Fusion Manager - Lyubishchev Architecture v3.0 (Chronos Mode)
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

# [v3.8] Reminder Kit Import
try:
    from external.reminder_kit import ReminderKitClient
    REMINDER_AVAILABLE = True
except ImportError:
    REMINDER_AVAILABLE = False
    ReminderKitClient = None

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
    [v3.1] 新增变更来源检测机制
    """
    
    # 已知进程特征映射
    _PROCESS_SIGNATURES = {
        'obsidian': 'OBSIDIAN',
        'electron': 'OBSIDIAN',  # Obsidian 基于 Electron
        'vim': 'USER',
        'nvim': 'USER',
        'code': 'USER',  # VS Code
        'sublime': 'USER',
        'textedit': 'USER',
        'bbedit': 'USER',
        'atom': 'USER',
        'finder': 'MACOS',
        'mds': 'MACOS',  # Spotlight indexer
        'mdworker': 'MACOS',  # Spotlight worker
        'fseventsd': 'MACOS',
        'python': 'SYSTEM',  # 可能是本程序
    }
    
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self._last_event_time = {}
        
        # [v4.1] 新增延迟打字重置定时器映射表
        self._delayed_timers = {}
        # [v5.0] 保存最新读取的内容，用以比对是否仅为时间戳修改，实现毫秒同步
        self._last_file_content = {}

    @staticmethod
    def _get_frontmost_app_name() -> str:
        import subprocess
        try:
            cmd = ['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1.0)
            return result.stdout.strip()
        except Exception:
            return ""

    def _is_obsidian_frontmost(self) -> bool:
        return 'Obsidian' in self._get_frontmost_app_name()

    def _detect_change_source(self, filepath: str, is_system_write: bool) -> str:
        """
        [v3.1] 检测文件变更来源
        
        返回值:
        - 'SYSTEM': LyubishchevSync 自身写入
        - 'OBSIDIAN_TYPING': 用户在 Obsidian 中打字/交互 (依据: workspace.json 同时更新)
        - 'OBSIDIAN_SYNC': Obsidian 后台同步 (依据: workspace.json 未更新)
        - 'USER': 用户通过其他编辑器修改
        - 'MACOS': macOS 系统进程 (Finder, Spotlight 等)
        - 'UNKNOWN': 无法确定来源
        """
        import subprocess
        
        # [优先级 1] 检查是否为 LyubishchevSync 自身写入
        if is_system_write:
            return 'SYSTEM'
            
        detected_source = 'UNKNOWN'
        
        # [优先级 1] 检查是否为 LyubishchevSync 自身写入
        if is_system_write:
            return 'SYSTEM'
            
        detected_source = 'UNKNOWN'
        
        # [优先级 2] 尝试通过 lsof/fuser 获取打开该文件的进程 (极简版)
        # 注意: lsof 在 macOS 上可能很慢，且不一定能捕获瞬时写入
        # 这里仅作为一种辅助手段，不强求成功
        try:
            # 仅当文件存在时检查
            if os.path.exists(filepath):
                 pass #暂不启用 lsof 以避免性能损耗
        except Exception:
            pass
        
        # [优先级 3] 检查文件扩展名特征
        if detected_source == 'UNKNOWN':
            filename = os.path.basename(filepath)
            if filename.startswith('.'):
                if filename == '.DS_Store':
                    return 'MACOS'
                elif filename.startswith('.obsidian'):
                    detected_source = 'OBSIDIAN'
            
            # [优先级 4] 检查父目录特征
            elif '/.obsidian/' in filepath or '\\.obsidian\\' in filepath:
                detected_source = 'OBSIDIAN'
        
        # [优先级 5] 检查是否有 Obsidian 进程在运行
        if detected_source == 'UNKNOWN':
            try:
                result = subprocess.run(
                    ['pgrep', '-x', 'Obsidian'],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                if result.returncode == 0 and filepath.endswith('.md'):
                    detected_source = 'OBSIDIAN'
            except Exception:
                pass
        
        # [v3.4] 细化 Obsidian 来源：多维验证 (TYPING vs SYNC)
        if detected_source in ('OBSIDIAN', 'OBSIDIAN_LIKELY'):
            is_typing = False
            reasons = []

            # --- A. Workspace 活跃度 (强特征) ---
            try:
                obsidian_config_dir = os.path.join(Config.VAULT_ROOT, '.obsidian')
                md_mtime = os.path.getmtime(filepath) if os.path.exists(filepath) else 0

                # 检查多个可能的 workspace 文件
                for ws_file in ['workspace.json', 'workspace', 'workspace-mobile.json']:
                    ws_path = os.path.join(obsidian_config_dir, ws_file)
                    if os.path.exists(ws_path):
                        if abs(md_mtime - os.path.getmtime(ws_path)) < 5.0:
                            is_typing = True
                            reasons.append(f"WorkspaceActive")
                            break
            except Exception:
                pass

            # --- B. 当前窗口检测 (辅助验证 + Idle熔断) ---
            if not is_typing:
                try:
                    active_app = self._get_frontmost_app_name()
                    
                    if 'Obsidian' in active_app:
                        # [v3.6] 回归朴素：只要 Obsidian 是前台窗口且文件变了，就认为是用户操作
                        # 因为 workspace.json 不会实时更新，依赖它会导致误判
                        is_typing = True
                        reasons.append(f"CurrentFocus")

                    elif active_app.lower() in ('terminal', 'iterm2', 'vscode', 'pycharm', 'cursor', 'python'):
                        # 开发者容错：切回终端看日志
                        is_typing = True
                        reasons.append(f"DevFocus")
                except Exception:
                    pass
            
            if is_typing:
                return 'OBSIDIAN_TYPING'
            else:
                return 'OBSIDIAN_SYNC'
                
        return detected_source

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
            
            # [v3.1] 检测变更来源（仅控制台输出，不影响逻辑）
            is_sys_write = FileUtils.check_system_write(content_hash)  # 使用 check 而非 is，避免消耗 hash
            change_source = self._detect_change_source(filepath, is_sys_write)
            
            # 来源颜色编码
            source_colors = {
                'SYSTEM': '\033[96m',          # 青色 - 系统自身
                'OBSIDIAN_TYPING': '\033[95m', # 亮紫色 - 用户在 Obsidian 打字
                'OBSIDIAN_SYNC': '\033[35m',   # 暗紫色 - Obsidian 后台同步
                'USER': '\033[92m',            # 绿色 - 用户其他编辑器
                'MACOS': '\033[93m',           # 黄色 - macOS 系统
                'UNKNOWN': '\033[90m',         # 灰色 - 未知
            }
            reset_color = '\033[0m'
            color = source_colors.get(change_source, '\033[90m')
            
            print(f"{color}🏷️  [ChangeSource] {os.path.basename(filepath)} <- {change_source}{reset_color}")
            
            # [P0 FIX] 使用已经求值的 check_system_write 结果，避免二次调用消耗 hash
            if is_sys_write:
                Logger.debug(f"[Event] 忽略自写入事件: {os.path.basename(filepath)}")
                self._last_file_content[filepath] = content
                return
            
            # [NEW FIX] 纯时间判定 (毫秒级无缝同步)
            is_time_only_change = False
            old_str = self._last_file_content.get(filepath, "")
            self._last_file_content[filepath] = content
            
            if old_str and len(old_str.splitlines()) == len(content.splitlines()):
                old_lines = old_str.splitlines()
                new_lines = content.splitlines()
                changed_lines = [(o, n) for o, n in zip(old_lines, new_lines) if o != n]
                if len(changed_lines) == 1:
                    o_l, n_l = changed_lines[0]
                    if re.match(r'^\s*- \[[ xX]\]', o_l) and re.match(r'^\s*- \[[ xX]\]', n_l):
                        # 自定义模糊匹配，剔除任务行左侧所有疑似时间的字符 (数字、冒号、连划线、空格)
                        o_fuzzy = re.sub(r'^\s*- \[[ xX]\][\d\s:-]+', '', o_l).strip()
                        n_fuzzy = re.sub(r'^\s*- \[[ xX]\][\d\s:-]+', '', n_l).strip()
                        
                        # 如果剔除前缀后的“任务名字主体”完全一致，并且当前行包含完整的时间
                        if o_fuzzy == n_fuzzy and o_fuzzy != "":
                            if re.search(r'\d{1,2}:\d{2}', n_l):
                                is_time_only_change = True
            
            # [v4.0] 两阶段响应：即时格式化 + 延迟归档
            # 阶段1：毫秒级即时响应 — 立即执行 FormatCore（更新进度百分比、ICE 指数）
            time.sleep(0.1)  # 最短等待，确保文件写入完成
            
            # 即时执行格式化（进度、ICE 指数更新），仅限日记文件
            # [FocusSafe] 用户正在 Obsidian 前台编辑时，不做即时回写，避免光标/焦点漂移
            filename = os.path.basename(filepath)
            is_daily = bool(re.match(r'^\d{4}-\d{2}-\d{2}\.md$', filename))
            if is_daily and change_source != 'OBSIDIAN_TYPING':
                try:
                    if FormatCore.execute(filepath, instant=True):
                        Logger.info(f"⚡ [Instant] 进度即时更新: {filename}")
                except Exception as e:
                    Logger.error_once(f"instant_fmt_{filepath}", f"即时格式化异常: {e}")
            
            # [v4.1] 阶段2：动态重置（防抖）定时器的延迟归档
            def delayed_archiving_task():
                Logger.info(f"📝 [Event] 计时结束，延迟归档触发: {os.path.basename(filepath)}")
                try:
                    if change_source == 'OBSIDIAN_TYPING' and self._is_obsidian_frontmost():
                        if is_daily:
                            try:
                                if FormatCore.execute(filepath, instant=True, preserve_focus=True):
                                    Logger.info(f"🪶 [FocusSafe] 前台编辑中，仅做无痛进度刷新: {filename}")
                            except Exception as e:
                                Logger.error_once(f"focus_safe_fmt_{filepath}", f"无痛进度刷新异常: {e}")

                        retry_delay = getattr(Config, 'FOCUS_SAFE_RETRY_SECONDS', 6.0)
                        Logger.debug(f"[FocusSafe] Obsidian 仍在前台，完整同步延后 {retry_delay}s: {filename}")
                        retry_timer = threading.Timer(retry_delay, delayed_archiving_task)
                        self._delayed_timers[filepath] = retry_timer
                        retry_timer.start()
                        return

                    self.manager.on_file_changed(filepath)
                except Exception as e:
                    self.manager._set_gui_status("error")
                    Logger.error_once(f"timer_err_{filepath}", f"定时器触发同步异常: {e}")

            # 清理之前的定时器（如果你在 15 秒内又打字了，系统重新开始倒计时 15 秒）
            if filepath in self._delayed_timers:
                self._delayed_timers[filepath].cancel()

            if is_time_only_change:
                delay = 0.1
                Logger.info("⚡ [InstantSync] 检测到任务纯时间修改，绕过系统打字延迟，即刻触发日历同步!")
            elif change_source == 'OBSIDIAN_TYPING':
                delay = getattr(Config, 'CHANGE_SOURCE_TYPING_DELAY', 15.0)
                Logger.debug(f"[Event] 检测到用户输入，已重置倒计时 {delay}s...")
            elif change_source == 'OBSIDIAN_SYNC':
                delay = getattr(Config, 'CHANGE_SOURCE_SYNC_DELAY', 25.0)
                Logger.debug(f"[Event] 检测到后台同步，已重置倒计时 {delay}s...")
            else:
                delay = getattr(Config, 'CHANGE_SOURCE_TYPING_DELAY', 15.0)

            debounce_token = self.manager._set_gui_status("debounce")
            self.manager._schedule_gui_idle(debounce_token, delay=delay + 1.0)
                
            # 设置新的倒计时线程
            new_timer = threading.Timer(delay, delayed_archiving_task)
            self._delayed_timers[filepath] = new_timer
            new_timer.start()
            
        except Exception as e:
            self.manager._set_gui_status("error")
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
        
        self._reminder_client = None
        if REMINDER_AVAILABLE:
             try:
                 self._reminder_client = ReminderKitClient()
             except Exception as e:
                 Logger.error_once("rem_init_fail", f"ReminderKitClient init failed: {e}")
                 self._reminder_client = None
        
        self._running = False
        self._registry_warmup_done = False
        
        # [v3.0] Chronos Mode
        self._calendar_dirty_flag = False
        self._reminder_dirty_flag = False
        self._last_midnight_check = datetime.date.today()
        self._startup_sync_done = False
        self._last_calendar_sync_time = 0  # [P2 FIX] Debounce timer

    def _set_gui_status(self, state: str):
        app = getattr(self.__class__, 'app_ref', None)
        if not app:
            return None
        try:
            return app.set_status(state)
        except Exception as e:
            Logger.debug(f"⚠️ GUI 状态更新失败 ({state}): {e}")
            return None

    def _schedule_gui_idle(self, token, delay: float = 1.5):
        app = getattr(self.__class__, 'app_ref', None)
        if not app or token is None:
            return
        try:
            app.schedule_idle(token, delay=delay)
        except Exception as e:
            Logger.debug(f"⚠️ GUI idle 恢复失败: {e}")

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
        status_token = self._set_gui_status("syncing")
        try:
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
        finally:
            self._schedule_gui_idle(status_token, delay=1.5)

    def _on_calendar_push_event(self):
        """
        [v3.0] Callback for EventKit notification.
        Thread-safe: Just sets a flag and stops the runloop.
        """
        self._calendar_dirty_flag = True
        try:
            from CoreFoundation import CFRunLoopStop, CFRunLoopGetCurrent
            CFRunLoopStop(CFRunLoopGetCurrent())
        except Exception as e:
            Logger.debug(f"⚠️ Failed to stop CFRunLoop in calendar callback: {e}")

    def _on_reminder_push_event(self):
        """
        [v3.8] Callback for ReminderKit notification.
        """
        self._reminder_dirty_flag = True
        try:
            from CoreFoundation import CFRunLoopStop, CFRunLoopGetCurrent
            CFRunLoopStop(CFRunLoopGetCurrent())
        except Exception as e:
            Logger.debug(f"⚠️ Failed to stop CFRunLoop in reminder callback: {e}")


    def sync_reminders(self):
        # [v3.8] Reminder Sync Logic

        # 这个方法现在是真正的业务逻辑实现
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        Logger.info(f"🔄 [Chronos] 执行提醒事项同步 ({today_str})...")
        
        # 1. 获取 Obsidian 中的任务 (Source of Truth for creation/deletion?)
        # 实际上 Obsidian 和 Reminders 是双向的。
        # 我们先只做简单的：把 Obsidian 今日任务推送到 Reminders，
        # 并把 Reminders 的完成状态同步回 Obsidian。
        
        try:
             # A. 获取 Reminders (Incomplete + Completed today)
             reminders_by_date = self._reminder_client.fetch_reminders(start_date=datetime.date.today(), end_date=datetime.date.today())
             today_reminders = reminders_by_date.get(today_str, [])
             
             # Map: Reminder ID -> Reminder Object
             rem_map = {r['id']: r for r in today_reminders}
             
             # B. 获取 Obsidian 今日任务
             obs_tasks = self.sync_core.get_tasks_for_date(today_str)
             
             # C. Obsidian -> Reminders (Push new tasks)
             # 目前 EventKitWrapper 只有读权限/能力？
             # 查阅代码发现在 reminder_kit.py 中只实现了 fetch。
             # 我们需要扩展 reminder_kit.py 支持 save_reminder / update_reminder。
             # 鉴于时间，先实现 "Reminders 完成状态 -> Obsidian" (Hooking into SyncCore)
             
             changes_count = 0
             
             for bid, task_data in obs_tasks.items():
                 # 假设 Obsidian 任务描述里包含了 Reminder ID? 
                 # 或者是根据 Title 匹配?
                 # 现有的 AppleNotes 逻辑是 *ID*Content。
                 # Reminders 也有 CalendarItemIdentifier。
                 
                 # 匹配逻辑：
                 # 1. 如果 Obsidian 任务有 RID (block id 即使是)，尝试在 Reminders 中找。
                 #    但是 Reminder ID 通常很长 (UUID)。
                 # 2. 只有通过 Title 匹配最稳妥，或者我们在 Obsidian 中存储 RID。
                 
                 # 简化版：仅同步完成状态 (基于 Title)
                 clean_content = task_data.get('pure', '').strip()
                 is_obs_completed = task_data.get('status') == 'x'
                 
                 matched_rem = None
                 for r in today_reminders:
                     if r['title'].strip() == clean_content:
                         matched_rem = r
                         break
                 
                 if matched_rem:
                     is_rem_completed = matched_rem['is_completed']
                     
                     if is_rem_completed and not is_obs_completed:
                         Logger.info(f"   ✅ [Sync] Reminder 完成 -> Obsidian: {clean_content}")
                         # 更新 Obsidian
                         # 最直接的方式：读取文件，替换状态，写回。
                         # 为了复用逻辑，我们可以扩展 SyncCore。
                         self.sync_core.complete_task_by_title(clean_content, today_str)
 
                         
             Logger.info(f"✅ [Chronos] 提醒事项同步完成 (占位)")
             
        except Exception as e:
            Logger.error_once("rem_sync_fail", f"提醒事项同步失败: {e}")

    def sync_recent_window(self):
        """
        [v3.1] 日历变更触发的窗口同步
        
        范围: 过去 CHRONOS_FULL_RANGE_PAST_DAYS 天 ~ 未来 CHRONOS_FULL_RANGE_FUTURE_YEARS 年
        性能优化: 仅同步日历中有事件的日期，避免遍历所有空白日期
        """
        status_token = self._set_gui_status("calendar")
        try:
            if not self._ek_client:
                Logger.info("⚠️ [Chronos] EventKit 不可用，跳过窗口同步")
                return
            
            today = datetime.date.today()
            
            # [v3.7] DEBUG_TODAY_ONLY 模式：只处理今天的日记
            if getattr(Config, 'DEBUG_TODAY_ONLY', 0) == 1:
                start_date = today
                end_date = today
                Logger.info(f"🔄 [Chronos] 窗口同步 (DEBUG模式): 仅今天 {today}")
            else:
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
        finally:
            self._schedule_gui_idle(status_token, delay=1.5)

    def sync_full_range(self):
        """
        [v3.0] 全量同步：过去1年到未来10年
        仅同步日历中实际有事件的日期，避免创建大量空白笔记
        """
        status_token = self._set_gui_status("calendar")
        try:
            if not self._ek_client:
                Logger.info("⚠️ [Chronos] EventKit 不可用，跳过全量同步")
                return
            
            today = datetime.date.today()
            
            # [v3.7] DEBUG_TODAY_ONLY 模式：只处理今天的日记
            if getattr(Config, 'DEBUG_TODAY_ONLY', 0) == 1:
                start_date = today
                end_date = today
                Logger.info(f"🚀 [Chronos] 全量同步启动 (DEBUG模式): 仅今天 {today}")
            else:
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
        finally:
            self._schedule_gui_idle(status_token, delay=1.5)

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

        # [v3.8] 启动 Reminder 监听
        if self._reminder_client:
             try:
                 Logger.info("🎗️ [Watchdog] 启动 ReminderKit 监听...")
                 # 注意: 这里使用与 EventKit 相同的推送回调逻辑，或者单独的逻辑
                 self._reminder_client.start_watching(self._on_reminder_push_event)
             except Exception as e:
                 Logger.error_once("rem_watch_fail", f"无法启动提醒事项监听: {e}")

        # 主循环
        try:
            from CoreFoundation import CFRunLoopRunInMode, kCFRunLoopDefaultMode
            
            while self._running:
                # [v3.0] 纯事件驱动：仅处理标志位
                if self._calendar_dirty_flag:
                    self._calendar_dirty_flag = False
                    Logger.info(f"⚡ [Chronos] 检测到日历变更")
                    self.sync_recent_window()
                
                if self._reminder_dirty_flag:
                    Logger.info(f"⚡ [Chronos] 检测到提醒事项变更")
                    self._reminder_dirty_flag = False
                    self.sync_reminders() 

                
                # 检查午夜跨越
                self._check_midnight_crossing()
                
                # 保持 RunLoop 唤醒，returnAfterSourceHandled=True
                CFRunLoopRunInMode(kCFRunLoopDefaultMode, Config.CHRONOS_LOOP_INTERVAL, True)

                
        except KeyboardInterrupt:
            Logger.info("\n⏹️ 收到中断信号...")
        finally:
            if self._observer:
                Logger.info("🛑 [Watchdog] 停止监听 Vault...")
                self._observer.stop()
                self._observer.join(timeout=3)
            
            if self._ek_client:
                Logger.info("🛑 [Watchdog] 停止监听 Calendar...")
            if self._ek_client:
                Logger.info("🛑 [Watchdog] 停止监听 Calendar...")
                self._ek_client.stop_watching()

            if self._reminder_client:
                Logger.info("🛑 [Watchdog] 停止监听 Reminders...")
                self._reminder_client.stop_watching()
            
            self.sm.save()
            Logger.info("✅ 状态已保存，Chronos 引擎已停止")
