import os
import time
import sys
from config import Config
from utils import Logger

def create_lock():
    lock_path = os.path.join(Config.DAILY_NOTE_DIR, '.fusion_sync_lock')
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with open(lock_path, 'w') as f:
        f.write(str(os.getpid()))
    Logger.info(f"Zombie: Lock created at {lock_path} with PID {os.getpid()}")
    sys.stdout.flush()

if __name__ == "__main__":
    create_lock()
    Logger.info("Zombie: Braains... (Sleeping)")
    sys.stdout.flush()
    while True:
        time.sleep(1)
