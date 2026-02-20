import time
import signal
import os
import sys
import subprocess
import atexit

# Add src to sys.path to allow importing dailynotes package
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from dailynotes.manager import FusionManager
from config import Config
from dailynotes.utils import ProcessLock, Logger

# [v4.0] Apple Notes Monitor（带降级处理）
try:
    from external.note_sync_core.monitor import NoteMonitor
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
        watch_script = os.path.join(
            os.path.dirname(__file__), 'src', 'external', 'note_sync_core', 'watch_today_note.py'
        )
        if not os.path.exists(watch_script):
            Logger.info(f"⚠️ [NoteMonitor] 脚本不存在: {watch_script}")
            return

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

def run_with_self_healing():
    """
    [v2.0.1] 带错误自愈的主循环
    如果 FusionManager 崩溃，自动重启
    """
    max_restarts = 5
    restart_count = 0
    restart_cooldown = 30  # 重启冷却时间（秒）
    
    # [v4.0] 在主循环之前启动备忘录监听
    _start_note_monitor()
    
    while restart_count < max_restarts:
        try:
            app = FusionManager()
            Logger.info(f"=== Antigravity Sync {Config.VERSION} (Exponential Dynamic Scheduling) ===")
            Logger.info(f"路径: {Config.ROOT_DIR}")
            Logger.info(f"模式: Watchdog (Vault & Calendar) + 指数动态调度")
            Logger.info(f"调度公式: I(d) = {Config.EXP_BASE} * exp({Config.EXP_COEFF} * d) + {Config.EXP_OFFSET}")
            
            # [P2 FIX] Validate template file at startup
            if os.path.exists(Config.TEMPLATE_FILE):
                Logger.info(f"模板: ✅ {Config.REL_TEMPLATE_FILE}")
            else:
                Logger.info(f"⚠️ 模板文件不存在: {Config.REL_TEMPLATE_FILE} (将使用基础骨架)")
            
            # [v9.0] 备忘录监听状态（子进程模式）
            if _note_monitor_proc and _note_monitor_proc.poll() is None:
                Logger.info(f"📝 备忘录: ✅ Apple Notes -> Obsidian (PID: {_note_monitor_proc.pid})")
            else:
                Logger.info(f"📝 备忘录: ⚠️ 未启用")
            
            if restart_count > 0:
                Logger.info(f"🔄 [Self-Healing] 自动重启成功 (第 {restart_count} 次)")
            
            Logger.info("=" * 50)
            
            app.run()
            break  # 正常退出
            
        except KeyboardInterrupt:
            Logger.info("\n停止服务...")
            break
        except SystemExit:
            Logger.info("收到退出信号...")
            break
        except Exception as e:
            restart_count += 1
            Logger.error_once(f"main_crash_{restart_count}", f"❌ [Self-Healing] 主循环异常: {e}")
            
            if restart_count < max_restarts:
                Logger.info(f"⏳ [Self-Healing] {restart_cooldown}秒后尝试重启 ({restart_count}/{max_restarts})...")
                time.sleep(restart_cooldown)
            else:
                Logger.error_once("max_restarts", f"❌ [Self-Healing] 达到最大重启次数 ({max_restarts})，退出")

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
        run_with_self_healing()
    finally:
        _stop_note_monitor()
        stop_caffeinate()
        ProcessLock.release()
