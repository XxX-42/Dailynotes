import time
import signal
import os
import sys
import subprocess
import atexit
import threading

# Add src to sys.path to allow importing dailynotes package
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from dailynotes.manager import FusionManager
from dailynotes.health_sync import HealthSyncService
from dailynotes.sync_pause import sync_pause
from config import Config
from dailynotes.utils import ProcessLock, Logger

# [v4.0] Apple Notes Monitor（带降级处理）
try:
    from external.note_sync_core.monitor import NoteMonitor
    from external.note_sync_core.note_monitor_guard import terminate_note_monitor_processes
    NOTE_MONITOR_AVAILABLE = True
except ImportError as e:
    NOTE_MONITOR_AVAILABLE = False
    Logger.info(f"⚠️ [NoteMonitor] 模块加载失败（不影响主程序）: {e}")

# [v2.0.1] Caffeinate 进程句柄（防休眠）
_caffeinate_proc = None

def start_caffeinate():
    """
    [v2.0.1] 启动 caffeinate 防休眠进程
    使用 -i 参数阻止系统进入 idle sleep
    """
    global _caffeinate_proc
    try:
        _caffeinate_proc = subprocess.Popen(
            ['caffeinate', '-i', '-w', str(os.getpid())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        Logger.info(f"☕ [Caffeinate] 防休眠已启用 (PID: {_caffeinate_proc.pid})")
    except FileNotFoundError:
        Logger.info("⚠️ [Caffeinate] caffeinate 命令不可用（非 macOS?），跳过防休眠")
    except Exception as e:
        Logger.info(f"⚠️ [Caffeinate] 启动失败: {e}")

def stop_caffeinate():
    """
    [v2.0.1] 停止 caffeinate 进程
    """
    global _caffeinate_proc
    if _caffeinate_proc:
        try:
            _caffeinate_proc.terminate()
            _caffeinate_proc.wait(timeout=2)
            Logger.info("☕ [Caffeinate] 防休眠已停止")
        except Exception:
            pass
        _caffeinate_proc = None

# [v4.0] NoteMonitor 全局实例（方便退出时清理）
_note_monitor_proc = None
_health_sync_service = None
_service_lock = threading.RLock()
_shutdown_requested = threading.Event()
_active_manager = None


def _note_monitor_script_paths():
    base_dir = os.path.join(os.path.dirname(__file__), 'src', 'external', 'note_sync_core')
    return [
        os.path.join(base_dir, 'watch_today_note.py'),
        os.path.join(base_dir, 'run_note_monitor.py'),
    ]

def _start_note_monitor():
    """
    [v9.0] 启动 Apple Notes 备忘录监听（独立子进程）
    直接运行 watch_today_note.py，完全独立于 FusionManager
    """
    global _note_monitor_proc
    if not NOTE_MONITOR_AVAILABLE:
        Logger.info("ℹ️  [NoteMonitor] 模块不可用，跳过备忘录监听")
        return

    try:
        watch_script = _note_monitor_script_paths()[0]
        if not os.path.exists(watch_script):
            Logger.info(f"⚠️ [NoteMonitor] 脚本不存在: {watch_script}")
            return

        terminate_note_monitor_processes(
            _note_monitor_script_paths(),
            keep_pids={os.getpid()},
            logger=Logger,
        )

        _note_monitor_proc = subprocess.Popen(
            [sys.executable, watch_script],
            cwd=os.path.dirname(__file__),
            stdout=None,  # 继承主进程的 stdout，日志直接输出到控制台
            stderr=None,
        )
        Logger.info(f"🚀 [NoteMonitor] 已作为独立子进程启动 (PID: {_note_monitor_proc.pid})")
    except Exception as e:
        Logger.info(f"⚠️ [NoteMonitor] 启动失败（不影响主程序）: {e}")
        _note_monitor_proc = None

def _stop_note_monitor():
    """[v9.0] 停止 NoteMonitor 子进程"""
    global _note_monitor_proc
    if _note_monitor_proc:
        try:
            _note_monitor_proc.terminate()
            _note_monitor_proc.wait(timeout=5)
            Logger.info("🛑 [NoteMonitor] 子进程已停止")
        except Exception:
            _note_monitor_proc.kill()
        _note_monitor_proc = None


def _start_health_sync():
    """Start the Health watcher in this process after the main lock is held."""
    global _health_sync_service
    with _service_lock:
        if _health_sync_service is not None:
            return _health_sync_service
        _health_sync_service = HealthSyncService()
        service = _health_sync_service
    # Health startup failures are isolated and reported in the menu; the task,
    # Notes, and Calendar services continue to run.
    service.start()
    return service


def _stop_health_sync():
    service = _health_sync_service
    if service is not None:
        service.stop()


def get_health_status_snapshot():
    service = _health_sync_service
    if service is None:
        return {
            "status": "starting",
            "phase": "starting",
            "queued_count": 0,
            "current_file": None,
            "last_successful_time": None,
            "last_affected_date": None,
            "last_csv": None,
            "error_detail": None,
        }
    return service.snapshot()


def request_shutdown():
    """Request a graceful stop without blocking a GUI callback or signal handler."""
    global _active_manager
    _shutdown_requested.set()
    sync_pause.cancel_waiters()
    service = _health_sync_service
    if service is not None:
        service.request_stop()
    manager = _active_manager
    if manager is not None:
        manager.request_stop()
    app = getattr(FusionManager, "app_ref", None)
    if app is not None:
        app.should_run = False


def stop_services():
    """Stop child and embedded watchers, and release their locks."""
    request_shutdown()
    _stop_note_monitor()
    _stop_health_sync()


def _handle_sigterm(signum, frame):
    request_shutdown()
    raise SystemExit("Received SIGTERM")

def run_with_self_healing():
    """
    [v2.0.1] 带错误自愈的主循环
    如果 FusionManager 崩溃，自动重启
    """
    max_restarts = 5
    restart_count = 0
    restart_cooldown = 30  # 重启冷却时间（秒）
    
    global _active_manager
    try:
        if not _shutdown_requested.is_set():
            # The main process owns all watchers. Start Health after ProcessLock
            # acquisition and before FusionManager's self-healing loop.
            _start_health_sync()
            _start_note_monitor()

        while restart_count < max_restarts and not _shutdown_requested.is_set():
            try:
                app = FusionManager()
                _active_manager = app
                Logger.info(f"=== Lyubishchev Sync {Config.VERSION} (Exponential Dynamic Scheduling) ===")
                Logger.info(f"路径: {Config.ROOT_DIR}")
                Logger.info(f"模式: Watchdog (Vault & Calendar) + 指数动态调度")
                Logger.info(f"调度公式: I(d) = {Config.EXP_BASE} * exp({Config.EXP_COEFF} * d) + {Config.EXP_OFFSET}")

                if os.path.exists(Config.TEMPLATE_FILE):
                    Logger.info(f"模板: ✅ {Config.REL_TEMPLATE_FILE}")
                else:
                    Logger.info(f"⚠️ 模板文件不存在: {Config.REL_TEMPLATE_FILE} (将使用基础骨架)")

                if _note_monitor_proc and _note_monitor_proc.poll() is None:
                    Logger.info(f"📝 备忘录: ✅ Apple Notes -> Obsidian (PID: {_note_monitor_proc.pid})")
                else:
                    Logger.info(f"📝 备忘录: ⚠️ 未启用")

                if restart_count > 0:
                    Logger.info(f"🔄 [Self-Healing] 自动重启成功 (第 {restart_count} 次)")

                Logger.info("=" * 50)
                app.run(register_signals=False)
                break

            except KeyboardInterrupt:
                Logger.info("\n停止服务...")
                request_shutdown()
                break
            except SystemExit:
                Logger.info("收到退出信号...")
                request_shutdown()
                break
            except Exception as e:
                restart_count += 1
                Logger.error_once(f"main_crash_{restart_count}", f"❌ [Self-Healing] 主循环异常: {e}")

                if _shutdown_requested.is_set():
                    break
                if restart_count < max_restarts:
                    Logger.info(f"⏳ [Self-Healing] {restart_cooldown}秒后尝试重启 ({restart_count}/{max_restarts})...")
                    _shutdown_requested.wait(restart_cooldown)
                else:
                    Logger.error_once("max_restarts", f"❌ [Self-Healing] 达到最大重启次数 ({max_restarts})，退出")
    finally:
        _active_manager = None
        stop_services()

if __name__ == "__main__":
    # [v2.0.1] 注册退出时清理 caffeinate
    atexit.register(stop_caffeinate)
    
    # [v2.0.1] 启动防休眠
    start_caffeinate()
    
    # 第一次尝试获取锁
    if not ProcessLock.acquire():
        Logger.info(f"⚠️  检测到锁文件 ({Config.LOCK_FILE})")
        old_pid = ProcessLock.read_pid()

        wait_seconds = 3
        Logger.info(f"⏳ 等待原进程 ({old_pid if old_pid else 'Unknown'}) 执行完当前周期 ({wait_seconds}s)...")
        time.sleep(wait_seconds)

        if old_pid:
            Logger.info(f"🛑 发送终止信号 (SIGTERM) 给 PID: {old_pid}...")
            try:
                os.kill(old_pid, signal.SIGTERM)

                # [优雅关闭] 给它 3 秒时间保存状态并退出
                for _ in range(30):  # 30 * 0.1s = 3s
                    time.sleep(0.1)
                    try:
                        os.kill(old_pid, 0)  # 检查是否存活
                    except OSError:
                        Logger.info("   原进程已优雅退出。")
                        break
                else:
                    Logger.info(f"💀 原进程未响应，强制关闭 (SIGKILL) PID: {old_pid}...")
                    os.kill(old_pid, signal.SIGKILL)
            except ProcessLookupError:
                Logger.info("   原进程已不存在。")
            except Exception as e:
                Logger.error_once("shutdown_fail", f"   关闭失败: {e}")
        else:
            Logger.info("⚠️  无法读取旧进程PID（可能是旧版代码遗留），尝试直接清理锁文件...")

        Logger.info("🔄 正在重启服务...")
        time.sleep(1)

        # 第二次尝试获取锁
        if not ProcessLock.acquire():
            Logger.error_once("lock_fail", "❌ 无法获取锁，强制接管失败。请手动检查。")
            exit(1)
        else:
            Logger.info("✅ 成功接管锁，服务已启动。")

    try:
        signal.signal(signal.SIGTERM, _handle_sigterm)
        run_with_self_healing()
    finally:
        stop_services()
        stop_caffeinate()
        ProcessLock.release()
