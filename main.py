import time
import signal
import os
import sys

# Add src to sys.path to allow importing dailynotes package
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from dailynotes.manager import FusionManager
from config import Config
from dailynotes.utils import ProcessLock, Logger

if __name__ == "__main__":
    app = FusionManager()
    
    Logger.info(f"=== Obsidian 融合守护进程 v5.4 (Auto-Healing) ===")
    Logger.info(f"路径: {Config.ROOT_DIR}")
    Logger.info(f"模式: 极简符号 + 新格式扫描 + 全日期扫描 + 5s 强制防抖")
    Logger.info(f"频率: {Config.TICK_INTERVAL}s/次")
    Logger.info("==========================================================")

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
                for _ in range(30): # 30 * 0.1s = 3s
                    time.sleep(0.1)
                    try:
                        os.kill(old_pid, 0) # 检查是否存活
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

        # 清理可能残留的锁文件（虽然 os.kill 后系统可能会释放，但为了保险）
        # 注意：这里主要依赖第二次 acquire 重新抢占
        
        Logger.info("🔄 正在重启服务...")
        time.sleep(1) # 给系统一点回收资源的时间

        # 第二次尝试获取锁
        if not ProcessLock.acquire():
            Logger.error_once("lock_fail", "❌ 无法获取锁，强制接管失败。请手动检查。")
            exit(1)
        else:
            Logger.info("✅ 成功接管锁，服务已启动。")

    try:
        app.run() # 注意：manager.py 里的 run 方法不再需要处理锁的获取，只需处理循环
    except KeyboardInterrupt:
        Logger.info("\n停止服务...")
    finally:
        ProcessLock.release()
