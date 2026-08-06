
import sys
import os
import time
import logging
import atexit

try:
    import fcntl
except ImportError:
    fcntl = None

# ==========================================
# 路径设置: 确保能导入项目模块
# ==========================================
# 1. 当前脚本所在目录: src/external/note_sync_core/
current_dir = os.path.dirname(os.path.abspath(__file__))
# 2. 项目根目录 (LyubishchevSync 的父目录，即 Beta Folder)
# src/external/note_sync_core/ -> src/external/ -> src/ -> LyubishchevSync -> Root
beta_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))

if beta_root not in sys.path:
    sys.path.append(beta_root)

# 3. LyubishchevSync 根目录
lyubishchev_root = os.path.join(beta_root, 'LyubishchevSync')
if lyubishchev_root not in sys.path:
    sys.path.append(lyubishchev_root)

# ==========================================
# 导入模块
# ==========================================
try:
    from config import Config
    from src.dailynotes.utils import Logger
except ImportError as e:
    print(f"❌ [Error] 无法导入 Config 或 Logger: {e}")
    print(f"   sys.path: {sys.path}")
    sys.exit(1)

try:
    from monitor import NoteMonitor
except ImportError as e:
    # 尝试相对导入
    sys.path.append(current_dir)
    from monitor import NoteMonitor
from note_monitor_guard import terminate_note_monitor_processes

# ==========================================
# 简单的 Logger 适配器 (如果 Utils Logger不可用)
# ==========================================
class SimpleLogger:
    @staticmethod
    def info(msg):
        print(msg)


_note_monitor_lock_fd = None


def _note_monitor_script_paths():
    return [
        os.path.join(current_dir, 'watch_today_note.py'),
        os.path.join(current_dir, 'run_note_monitor.py'),
    ]


def _note_monitor_lock_path():
    daily_dir = getattr(Config, 'DAILY_NOTE_DIR', None)
    if daily_dir:
        return os.path.join(daily_dir, '.note_monitor.lock')
    return os.path.join(current_dir, '.note_monitor.lock')


def acquire_note_monitor_lock(logger):
    global _note_monitor_lock_fd
    if not fcntl:
        return True

    lock_path = _note_monitor_lock_path()
    try:
        _note_monitor_lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(_note_monitor_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.ftruncate(_note_monitor_lock_fd, 0)
        os.write(_note_monitor_lock_fd, str(os.getpid()).encode())
        return True
    except (BlockingIOError, OSError):
        logger.info("ℹ️ [NoteMonitor] 已有监听子进程在运行，当前实例退出")
        if _note_monitor_lock_fd is not None:
            try:
                os.close(_note_monitor_lock_fd)
            except OSError:
                pass
            _note_monitor_lock_fd = None
        return False


def release_note_monitor_lock():
    global _note_monitor_lock_fd
    if not fcntl or _note_monitor_lock_fd is None:
        return

    lock_path = _note_monitor_lock_path()
    try:
        fcntl.flock(_note_monitor_lock_fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(_note_monitor_lock_fd)
    except OSError:
        pass
    _note_monitor_lock_fd = None
    try:
        if os.path.exists(lock_path):
            os.remove(lock_path)
    except OSError:
        pass

# ==========================================
# 主入口
# ==========================================
def main():
    print("🚀 [Launcher] 正在启动 NoteMonitor (via watch_today_note.py wrapper)...")
    
    # 使用项目 Logger 或 SimpleLogger
    logger = Logger if 'Logger' in locals() else SimpleLogger
    if not acquire_note_monitor_lock(logger):
        return
    atexit.register(release_note_monitor_lock)

    terminate_note_monitor_processes(
        _note_monitor_script_paths(),
        keep_pids={os.getpid()},
        logger=logger,
    )
    
    # 初始化 Monitor
    # Config 应该包含 DAILY_NOTE_DIR, TEMPLATE_FILE, KEYWORD_MAPPING
    monitor = NoteMonitor(config=Config, logger=logger)
    
    try:
        monitor.start()
        
        # 保持主线程运行 (NoteMonitor 是 daemon 线程)
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 [Launcher] 停止中...")
        monitor.stop()
    except Exception as e:
        print(f"❌ [Launcher] 异常: {e}")
        monitor.stop()

if __name__ == "__main__":
    main()
