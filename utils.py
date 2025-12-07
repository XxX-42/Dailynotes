import os
import datetime
import time
import tempfile
from typing import List, Union
from config import Config

# 尝试导入 fcntl (仅限 Unix/macOS)
try:
    import fcntl
except ImportError:
    fcntl = None


class Logger:
    _shown_errors = set()

    @staticmethod
    def error_once(key, message):
        if key not in Logger._shown_errors:
            print(f"\033[91m[ERROR] {message}\033[0m")
            Logger._shown_errors.add(key)

    @staticmethod
    def info(message, date_tag=None):
        # [FEATURE] Focused Logging: Only show logs for today (Current File)
        t = datetime.datetime.now().strftime('%H:%M:%S')
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        
        if date_tag and date_tag != today_str:
            return # Skip history logs to reduce noise
            
        prefix = f"[{date_tag}] " if date_tag else ""
        print(f"\033[92m[{t} INFO] {prefix}{message}\033[0m")

    @staticmethod
    def debug(message):
        if Config.DEBUG_MODE:
            print(f"\033[90m[DEBUG] {message}\033[0m")

    @staticmethod
    def debug_block(title, lines):
        if Config.DEBUG_MODE:
            print(f"\033[96m--- [DEBUG] {title} ---\033[0m")
            for line in lines:
                print(f"  | {line.rstrip()}")
            print(f"\033[96m-----------------------\033[0m")


class FileUtils:
    @staticmethod
    def read_file(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.readlines()
        except Exception:
            return None

    @staticmethod
    def read_content(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None

    @staticmethod
    def write_file(filepath, lines_or_content):
        # [ATOIMC] Uses tempfile + os.replace to ensure atomic writes
        dir_name = os.path.dirname(filepath) or '.'
        temp_name = None
        
        try:
            # Create temp file in same directory (required for atomic rename)
            # delete=False because we want to rename it, not have it deleted on close
            with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, encoding='utf-8') as tf:
                temp_name = tf.name
                
                if lines_or_content is None:
                    tf.write("")
                elif isinstance(lines_or_content, list):
                    tf.writelines([str(l) for l in lines_or_content if l is not None])
                else:
                    tf.write(str(lines_or_content))
                
                # Flush and fsync to ensure data is physically written
                tf.flush()
                os.fsync(tf.fileno())
            
            # Atomic swap
            os.replace(temp_name, filepath)
            return True
            
        except Exception as e:
            Logger.error_once(f"write_{filepath}", f"写入失败 {filepath}: {e}")
            # Cleanup temp file if it exists
            if temp_name and os.path.exists(temp_name):
                try:
                    os.remove(temp_name)
                except OSError:
                    pass
            return False

    @staticmethod
    def get_mtime(filepath):
        try:
            return os.path.getmtime(filepath)
        except OSError:
            return 0

    @staticmethod
    def is_excluded(path):
        path = os.path.normpath(path)
        for exclude in Config.EXCLUDE_DIRS:
            exclude = os.path.normpath(exclude)
            if path == exclude or path.startswith(exclude + os.sep):
                return True
        if '/.trash/' in path or path.endswith('/.trash') or '\\.trash\\' in path:
            return True
        return False


class ProcessLock:
    _lock_fd = None

    @classmethod
    def acquire(cls):
        if not fcntl: return True
        try:
            if not os.path.exists(Config.DAILY_NOTE_DIR): return False
            # 打开文件，准备读写
            cls._lock_fd = os.open(Config.LOCK_FILE, os.O_CREAT | os.O_RDWR)
            
            # 尝试获取排他锁（非阻塞）
            fcntl.flock(cls._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # [新增] 获取锁成功，清空文件并写入当前 PID
            os.ftruncate(cls._lock_fd, 0)
            os.write(cls._lock_fd, str(os.getpid()).encode())
            
            return True
        except (BlockingIOError, OSError):
            # 获取失败，关闭文件描述符
            if cls._lock_fd is not None:
                try:
                    os.close(cls._lock_fd)
                except OSError:
                    pass
                cls._lock_fd = None
            return False

    @staticmethod
    def read_pid():
        """尝试从锁文件中读取持有者的 PID"""
        try:
            if os.path.exists(Config.LOCK_FILE):
                with open(Config.LOCK_FILE, 'r') as f:
                    content = f.read().strip()
                    if content:
                        return int(content)
        except Exception:
            return None
        return None

    @classmethod
    def release(cls):
        if cls._lock_fd is not None:
            fcntl.flock(cls._lock_fd, fcntl.LOCK_UN)
            os.close(cls._lock_fd)
            cls._lock_fd = None
        try:
            if os.path.exists(Config.LOCK_FILE):
                os.remove(Config.LOCK_FILE)
        except OSError:
            pass
