import os
import signal
import sys

# 确保导入工作
sys.path.append(os.getcwd())
from config import Config
from utils import ProcessLock

def kill_cleanly():
    print(f"Attempting to find and kill daemon using lock file at: {Config.LOCK_FILE}")
    pid = ProcessLock.read_pid()
    if pid:
        print(f"Found PID: {pid}")
        try:
            os.kill(pid, signal.SIGKILL)
            print("Process killed successfully.")
        except ProcessLookupError:
            print("Process not found (already dead?).")
        except Exception as e:
            print(f"Error killing process: {e}")
        
        # 清理锁文件以确保万无一失
        if os.path.exists(Config.LOCK_FILE):
             os.remove(Config.LOCK_FILE)
             print("Lock file removed.")
    else:
        print("No PID found in lock file or lock file missing.")

if __name__ == "__main__":
    kill_cleanly()
