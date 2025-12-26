import os
import datetime
import time
import tempfile
import inspect
import hashlib
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
    def _get_caller_info():
        # Stack: 0=here, 1=caller(info/debug), 2=actual caller
        try:
            stack = inspect.stack()
            # Find the first frame outside of utils.py/Logger
            for frame in stack[1:]:
                fn = os.path.basename(frame.filename)
                if fn != 'utils.py':
                    func = frame.function
                    if func == '<module>': func = 'Main'
                    return f"[{fn}:{func}]"
            return "[Unknown:Unknown]"
        except Exception:
            return "[Unknown:Unknown]"

    @staticmethod
    def error_once(key, message):
        if key not in Logger._shown_errors:
            caller = Logger._get_caller_info()
            print(f"\033[91m[ERROR] {caller} {message}\033[0m")
            Logger._shown_errors.add(key)

    @staticmethod
    def info(message, date_tag=None):
        # [特性] 聚焦日志：仅显示今天的日志（当前文件）
        t = datetime.datetime.now().strftime('%H:%M:%S')
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        
        if date_tag and date_tag != today_str:
            return # 跳过历史日志以减少干扰
            
        prefix = f"[{date_tag}] " if date_tag else ""
        caller = Logger._get_caller_info()
        print(f"\033[92m[{t} INFO] {caller} {prefix}{message}\033[0m")

    @staticmethod
    def debug(message):
        if Config.DEBUG_MODE:
            caller = Logger._get_caller_info()
            print(f"\033[90m[DEBUG] {caller} {message}\033[0m")

    @staticmethod
    def debug_block(title, lines):
        if Config.DEBUG_MODE:
            caller = Logger._get_caller_info()
            print(f"\033[96m--- [DEBUG] {caller} {title} ---\033[0m")
            for line in lines:
                print(f"  | {line.rstrip()}")
            print(f"\033[96m-----------------------\033[0m")


class FileUtils:
    # [REFACTORED] Content-hash based self-awareness
    # Replaces fragile mtime comparison with deterministic content identity
    _system_write_hashes = set()
    _MAX_HASH_CACHE = 50  # Prevent memory leak

    @staticmethod
    def calculate_hash(content: str) -> str:
        """Fast MD5 hash for content identity."""
        if content is None:
            content = ""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    @classmethod
    def is_system_write(cls, content_hash: str) -> bool:
        """
        Check if hash matches a system write.
        If match found, removes it from set (one-time use).
        """
        if content_hash in cls._system_write_hashes:
            cls._system_write_hashes.discard(content_hash)
            return True
        return False

    @classmethod
    def check_system_write(cls, content_hash: str) -> bool:
        """
        Check if hash matches a system write WITHOUT removing it.
        Used for activity detection where we don't want to consume the hash.
        """
        return content_hash in cls._system_write_hashes

    @staticmethod
    def read_file(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.readlines()
        except Exception:
            return None

    @staticmethod
    def read_content(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception:
            return None

    @staticmethod
    def write_file(filepath, lines_or_content):
        # [原子性] 使用 tempfile + os.replace 以确保原子写入
        dir_name = os.path.dirname(filepath) or '.'
        temp_name = None
        
        # Normalize content to string for hashing
        if lines_or_content is None:
            final_content = ""
        elif isinstance(lines_or_content, list):
            final_content = "".join([str(l) for l in lines_or_content if l is not None])
        else:
            final_content = str(lines_or_content)
        
        # [CRITICAL] Calculate hash BEFORE write and register
        content_hash = FileUtils.calculate_hash(final_content)
        
        # Manage cache size to prevent memory leak
        if len(FileUtils._system_write_hashes) >= FileUtils._MAX_HASH_CACHE:
            FileUtils._system_write_hashes.clear()
        FileUtils._system_write_hashes.add(content_hash)
        
        try:
            # 在同一目录中创建临时文件（原子重命名所需）
            with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, encoding='utf-8') as tf:
                temp_name = tf.name
                tf.write(final_content)
                
                # 刷新并 fsync 以确保数据物理写入
                tf.flush()
                os.fsync(tf.fileno())
            
            # 原子交换
            os.replace(temp_name, filepath)
            return True
            
        except Exception as e:
            Logger.error_once(f"write_{filepath}", f"写入失败 {filepath}: {e}")
            # Remove hash on failure (write didn't happen)
            FileUtils._system_write_hashes.discard(content_hash)
            # 如果临时文件存在，则清理
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
