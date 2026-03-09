import sys
import os
import threading
import time
import signal
import subprocess

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Check if rumps is installed
try:
    import rumps
except ImportError:
    print("Error: 'rumps' module not found. Please run: pip install rumps")
    sys.exit(1)

import main
from config import Config
from dailynotes.utils import ProcessLock, Logger

class LyubishchevApp(rumps.App):
    def __init__(self):
        super(LyubishchevApp, self).__init__("柳比歇夫", title="⏳ 柳比歇夫")
        self.menu = [
            rumps.MenuItem("Status: Initializing...", callback=None),
            None,
            rumps.MenuItem("Open Log File", callback=self.open_log),
            rumps.MenuItem("Restart Sync", callback=self.restart_sync),
            None, # Separator before Quit
        ]
        self.sync_thread = None
        self.should_run = True

    def run_sync_logic(self):
        """
        Runs the main application logic in a background thread.
        Replicates the startup sequence from main.py:
        1. Caffeinate
        2. Lock Acquisition (with aggressive kill of old process)
        3. Main Loop (run_with_self_healing)
        """
        # 1. Start Caffeinate
        # main.start_caffeinate() # Move to main thread if possible or handle carefully

        # 2. Acquire Lock
        if not ProcessLock.acquire():
            Logger.info("⚠️ [GUI] Lock held by another process. Attempting takeover...")
            old_pid = ProcessLock.read_pid()
            if old_pid and old_pid != os.getpid():
                Logger.info(f"🛑 Killing old process {old_pid}...")
                try:
                    os.kill(old_pid, signal.SIGTERM)
                    # Wait up to 3 seconds
                    for _ in range(30):
                        time.sleep(0.1)
                        os.kill(old_pid, 0)
                    else:
                        os.kill(old_pid, signal.SIGKILL)
                except OSError:
                    Logger.info("   Old process gone.")
                except Exception as e:
                    Logger.error_once("kill_fail", f"Failed to kill old process: {e}")
            
            # Retry acquire
            time.sleep(1)
            if not ProcessLock.acquire():
                Logger.error_once("lock_fail", "❌ Could not acquire lock even after cleanup.")
                dum_title = "❌ Error"
                try:
                    self.title = dum_title
                    rumps.notification("Sync Error", "Lock Failed", "Could not start sync engine.")
                except: pass
                return

        # Success acquiring lock
        Logger.info("✅ [GUI] Lock acquired. Starting engine...")
        try:
             # Update Status UI (Safely?)
            self.title = "🚀 柳比歇夫"
            self.menu["Status: Initializing..."].title = "Status: Running"
        except: pass

        try:
            # 3. Run Main Loop
            # This calls the self-healing loop from main.py
            main.run_with_self_healing()
        except Exception as e:
            Logger.error_once("gui_thread_crash", f"❌ Sync thread crashed: {e}")
            try:
                self.title = "⚠️ Valid"
            except: pass
        finally:
            # Cleanup
            ProcessLock.release()
            main.stop_caffeinate()
            try:
                self.title = "🔴 Stop"
                self.menu["Status: Initializing..."].title = "Status: Stopped"
            except: pass

    @rumps.clicked("Open Log File")
    def open_log(self, _):
        log_file = "/tmp/LyubishchevSync_startup.log"
        if os.path.exists(log_file):
            subprocess.run(["open", log_file])
        else:
            rumps.notification("Lyubishchev Sync", "Log Missing", "Log file not found at " + log_file)

    @rumps.clicked("Restart Sync")
    def restart_sync(self, _):
        # 弹窗提示正在重启
        rumps.notification("柳比歇夫", "Restarting...", "The synchronization engine is restarting.")
        
        # 组装完整的后台启动 shell 命令
        python_path = "/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta_v2/.venv/bin/python"
        script_path = "/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta_v2/LyubishchevSync/gui_main.py"
        log_path = "/tmp/LyubishchevSync_startup.log"
        
        cmd = f'export PYTHONIOENCODING=utf-8; "{python_path}" -u "{script_path}" > "{log_path}" 2>&1 &'
        
        # 使用 subprocess 启动全新分离的后台进程
        subprocess.Popen(cmd, shell=True)
        
        # 退出当前进程（完成替换接力）
        rumps.quit_application()

    def start(self):
        # Start the sync logic thread
        self.sync_thread = threading.Thread(target=self.run_sync_logic, daemon=True)
        self.sync_thread.start()
        
        # Start the Rumps App (Main Thread)
        self.run()

if __name__ == "__main__":
    # Prevent signal handlers from running in non-main threads
    # We patch the signal module in main.py or handle it here
    
    # Monkey-patching signal.signal to ignore signals in non-main threads if called from there, 
    # but the issue is FusionManager calls signal.signal.
    # We need to run FusionManager's signal setup in the main thread OR disable it.
    
    # Option: Instantiate FusionManager and run it without signal handlers?
    # Or run the heavy lifting in a thread, but keep signal handling in the main thread?
    # Rumps app.run() blocks the main thread.
    
    # Workaround: Disable signal handling in FusionManager when running under GUI
    import dailynotes.manager
    
    # Store original run method
    original_run = dailynotes.manager.FusionManager.run
    
    def patched_run(self):
        # Skip signal registration
        self._running = True
        
        Logger.info(f"🚀 Chronos Mode 启动 - 全事件驱动架构 (GUI Mode)")
        Logger.info(f"   同步窗口: ±{Config.CHRONOS_SYNC_WINDOW_DAYS // 2} 天")
        Logger.info(f"   全量范围: 过去 {Config.CHRONOS_FULL_RANGE_PAST_DAYS} 天 ~ 未来 {Config.CHRONOS_FULL_RANGE_FUTURE_YEARS} 年")
        Logger.info(f"   循环间隔: {Config.CHRONOS_LOOP_INTERVAL} 秒")

        # 初始化 Watchdog
        if dailynotes.manager.WATCHDOG_AVAILABLE:
            try:
                self._observer = dailynotes.manager.Observer()
                event_handler = dailynotes.manager.ObsidianEventHandler(self)
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
            
            while self.app_ref.should_run and self._running:
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

    # Apply Patch
    dailynotes.manager.FusionManager.run = patched_run

    app = LyubishchevApp()
    # Inject app reference to manager so it can check should_run
    dailynotes.manager.FusionManager.app_ref = app 
    
    app.start()
