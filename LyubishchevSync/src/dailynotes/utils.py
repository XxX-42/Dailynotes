import os
import sys
import datetime
import time
import tempfile
import inspect
import hashlib
import json
from typing import List, Union
from config import Config

# 尝试导入 fcntl (仅限 Unix/macOS)
try:
    import fcntl
except ImportError:
    fcntl = None


class Logger:
    _shown_errors = set()
    _countdown_active = False  # 跟踪倒计时行是否正在显示

    @classmethod
    def _clear_countdown_line(cls):
        """清除倒计时行，为正常日志输出腾出空间"""
        if cls._countdown_active:
            # 回车 + 清行 + 换行
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()
            cls._countdown_active = False

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

    @classmethod
    def error_once(cls, key, message):
        if key not in cls._shown_errors:
            cls._clear_countdown_line()
            caller = cls._get_caller_info()
            print(f"\033[91m[ERROR] {caller} {message}\033[0m")
            cls._shown_errors.add(key)

    @classmethod
    def info(cls, message, date_tag=None):
        # [特性] 聚焦日志：仅显示今天的日志（当前文件）
        t = datetime.datetime.now().strftime('%H:%M:%S')
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        
        if date_tag and date_tag != today_str:
            return # 跳过历史日志以减少干扰
        
        cls._clear_countdown_line()
        prefix = f"[{date_tag}] " if date_tag else ""
        caller = cls._get_caller_info()
        print(f"\033[92m[{t} INFO] {caller} {prefix}{message}\033[0m")

    @classmethod
    def debug(cls, message):
        if Config.DEBUG_MODE:
            cls._clear_countdown_line()
            caller = cls._get_caller_info()
            print(f"\033[90m[DEBUG] {caller} {message}\033[0m")

    @classmethod
    def debug_block(cls, title, lines):
        if Config.DEBUG_MODE:
            cls._clear_countdown_line()
            caller = cls._get_caller_info()
            print(f"\033[96m--- [DEBUG] {caller} {title} ---\033[0m")
            for line in lines:
                print(f"  | {line.rstrip()}")
            print(f"\033[96m-----------------------\033[0m")


class FileUtils:
    # [REFACTORED] Content-hash based self-awareness
    # Replaces fragile mtime comparison with deterministic content identity
    # Replaces fragile mtime comparison with deterministic content identity
    _system_write_hashes = {}  # {hash: timestamp} to preserve order and deduplicate
    _MAX_HASH_CACHE = 50  # Prevent memory leak

    @staticmethod
    def calculate_hash(content: str) -> str:
        """Fast MD5 hash for content identity."""
        if content is None:
            content = ""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    @staticmethod
    def _get_audit_log_path() -> str:
        return getattr(
            Config,
            "MODIFICATION_AUDIT_LOG",
            os.path.join(Config.DAILY_NOTE_DIR, ".modification_audit.json"),
        )

    @staticmethod
    def _get_write_caller():
        try:
            stack = inspect.stack()
            for frame in stack[2:]:
                fn = os.path.basename(frame.filename)
                if fn != 'utils.py':
                    func = frame.function if frame.function != '<module>' else 'Main'
                    return {
                        "file": frame.filename,
                        "function": func,
                        "line": frame.lineno,
                        "label": f"{fn}:{func}:{frame.lineno}",
                    }
        except Exception:
            pass
        return {
            "file": "unknown",
            "function": "unknown",
            "line": 0,
            "label": "unknown",
        }

    @classmethod
    def _append_modification_audit(cls, filepath: str, strategy: str, content: str):
        log_path = cls._get_audit_log_path()
        if os.path.abspath(filepath) == os.path.abspath(log_path):
            return

        entry = {
            "timestamp": datetime.datetime.now().isoformat(timespec='seconds'),
            "target_file": filepath,
            "strategy": strategy,
            "content_hash": cls.calculate_hash(content),
            "snapshot": content,
            "caller": cls._get_write_caller(),
        }

        try:
            entries = []
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        entries = loaded

            entries.append(entry)
            limit = max(1, int(getattr(Config, "MODIFICATION_AUDIT_LIMIT", 30)))
            entries = entries[-limit:]

            dir_name = os.path.dirname(log_path) or '.'
            temp_name = None
            try:
                with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, encoding='utf-8') as tf:
                    temp_name = tf.name
                    json.dump(entries, tf, ensure_ascii=False, indent=2)
                    tf.flush()
                    os.fsync(tf.fileno())
                os.replace(temp_name, log_path)
            finally:
                if temp_name and os.path.exists(temp_name):
                    try:
                        os.remove(temp_name)
                    except OSError:
                        pass
        except Exception as e:
            Logger.error_once(f"audit_log_{log_path}", f"写入修改审计日志失败: {e}")

    @classmethod
    def is_system_write(cls, content_hash: str) -> bool:
        """
        Check if hash matches a system write.
        If match found, removes it from dict (one-time use).
        """
        if content_hash in cls._system_write_hashes:
            del cls._system_write_hashes[content_hash]
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
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.readlines()
        except UnicodeDecodeError as e:
            Logger.error_once(
                f"decode_readlines_{filepath}",
                f"UTF-8 解码失败，已中止读取以避免静默乱码固化: {filepath}: {e}"
            )
            return None
        except Exception:
            return None

    @staticmethod
    def read_content(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError as e:
            Logger.error_once(
                f"decode_read_{filepath}",
                f"UTF-8 解码失败，已中止读取以避免静默乱码固化: {filepath}: {e}"
            )
            return None
        except Exception:
            return None

    @staticmethod
    def write_file(filepath, lines_or_content, strategy: str = "atomic"):
        # strategy:
        # - atomic: tempfile + os.replace，适合后台批处理
        # - inplace: 就地覆盖同一 inode，尽量减少编辑器焦点/光标抖动
        dir_name = os.path.dirname(filepath) or '.'
        temp_name = None
        
        # Normalize content to string for hashing
        if lines_or_content is None:
            final_content = ""
        elif isinstance(lines_or_content, list):
            final_content = "".join([str(l) for l in lines_or_content if l is not None])
        else:
            final_content = str(lines_or_content)
        final_bytes = final_content.encode('utf-8')
        
        # [CRITICAL] Calculate hash BEFORE write and register
        content_hash = FileUtils.calculate_hash(final_content)
        
        # Manage cache size to prevent memory leak
        if len(FileUtils._system_write_hashes) >= FileUtils._MAX_HASH_CACHE:
            # 移除最早插入的一半元素
            oldest_keys = list(FileUtils._system_write_hashes.keys())[:FileUtils._MAX_HASH_CACHE // 2]
            for k in oldest_keys:
                del FileUtils._system_write_hashes[k]
        FileUtils._system_write_hashes[content_hash] = time.time()
        
        try:
            if strategy == "inplace" and os.path.exists(filepath):
                with open(filepath, 'r+b') as f:
                    f.seek(0)
                    f.write(final_bytes)
                    f.truncate()
                    f.flush()
                    os.fsync(f.fileno())
                FileUtils._append_modification_audit(filepath, strategy, final_content)
                return True

            # 在同一目录中创建临时文件（原子重命名所需）
            with tempfile.NamedTemporaryFile('wb', dir=dir_name, delete=False) as tf:
                temp_name = tf.name
                tf.write(final_bytes)
                
                # 刷新并 fsync 以确保数据物理写入
                tf.flush()
                os.fsync(tf.fileno())
            
            # 原子交换
            os.replace(temp_name, filepath)
            FileUtils._append_modification_audit(filepath, strategy, final_content)
            return True

        except Exception as e:
            Logger.error_once(f"write_{strategy}_{filepath}", f"写入失败 {filepath}: {e}")
            # Remove hash on failure (write didn't happen)
            if content_hash in FileUtils._system_write_hashes:
                del FileUtils._system_write_hashes[content_hash]
            # 如果临时文件存在，则清理
            if temp_name and os.path.exists(temp_name):
                try:
                    os.remove(temp_name)
                except OSError:
                    pass
            return False

    @staticmethod
    def create_file_if_absent(filepath, lines_or_content):
        """
        Create a file exactly once without overwriting an existing one.

        Returns one of:
        - "CREATED"
        - "ALREADY_EXISTS"
        - "FAILED"
        """
        if lines_or_content is None:
            final_content = ""
        elif isinstance(lines_or_content, list):
            final_content = "".join([str(l) for l in lines_or_content if l is not None])
        else:
            final_content = str(lines_or_content)
        final_bytes = final_content.encode('utf-8')
        content_hash = FileUtils.calculate_hash(final_content)

        try:
            fd = os.open(filepath, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            return "ALREADY_EXISTS"
        except Exception as e:
            Logger.error_once(f"create_absent_open_{filepath}", f"创建失败 {filepath}: {e}")
            return "FAILED"

        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(final_bytes)
                f.flush()
                os.fsync(f.fileno())

            if len(FileUtils._system_write_hashes) >= FileUtils._MAX_HASH_CACHE:
                oldest_keys = list(FileUtils._system_write_hashes.keys())[:FileUtils._MAX_HASH_CACHE // 2]
                for k in oldest_keys:
                    del FileUtils._system_write_hashes[k]
            FileUtils._system_write_hashes[content_hash] = time.time()

            FileUtils._append_modification_audit(filepath, "create_if_absent", final_content)
            return "CREATED"
        except Exception as e:
            Logger.error_once(f"create_absent_write_{filepath}", f"创建失败 {filepath}: {e}")
            try:
                os.remove(filepath)
            except OSError:
                pass
            if content_hash in FileUtils._system_write_hashes:
                del FileUtils._system_write_hashes[content_hash]
            return "FAILED"

    @staticmethod
    def get_mtime(filepath):
        try:
            return os.path.getmtime(filepath)
        except OSError:
            return 0

    @staticmethod
    def is_excluded(path):
        path = os.path.normpath(path)
        
        # [白名单] DAILY_NOTE_DIR 及其文件不应被排除
        daily_dir = os.path.normpath(Config.DAILY_NOTE_DIR)
        if path == daily_dir or path.startswith(daily_dir + os.sep):
            return False
        
        # [黑名单] 排除目录检查
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
