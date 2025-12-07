import os
import signal
import sys

# 确保导入工作
sys.path.append(os.getcwd())
from config import Config
from config import Config
from utils import ProcessLock, Logger

def kill_cleanly():
    Logger.info(f"Attempting to find and kill daemon using lock file at: {Config.LOCK_FILE}")
    pid = ProcessLock.read_pid()
    if pid:
        Logger.info(f"Found PID: {pid}")
        try:
            os.kill(pid, signal.SIGKILL)
            os.kill(pid, signal.SIGKILL)
            Logger.info("Process killed successfully.")
        except ProcessLookupError:
            Logger.info("Process not found (already dead?).")
        except Exception as e:
            Logger.error_once("kill_fail", f"Error killing process: {e}")
        
        # 清理锁文件以确保万无一失
        if os.path.exists(Config.LOCK_FILE):
             os.remove(Config.LOCK_FILE)
             Logger.info("Lock file removed.")
    else:
        Logger.info("No PID found in lock file or lock file missing.")

if __name__ == "__main__":
    kill_cleanly()
