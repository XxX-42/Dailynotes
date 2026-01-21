import subprocess
import threading
import time
import signal
import os

class LogSentinel:
    """
    Broad-Spectrum Calendar Change Detector (Shotgun Mode).
    Monitors all non-debug CalendarAgent logs to reliably detect changes.
    """
    
    def __init__(self, callback):
        self.callback = callback
        self.process = None
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        """Spawns the log monitoring daemon thread."""
        if self.thread and self.thread.is_alive():
            return
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._monitor_logs, daemon=True, name="LogSentinelOps")
        self.thread.start()

    def stop(self):
        """Stops the subprocess and the monitoring thread."""
        self.stop_event.set()
        if self.process:
            try:
                os.kill(self.process.pid, signal.SIGTERM)
            except Exception:
                pass
            self.process = None

    def _monitor_logs(self):
        # [修改点 1] 移除具体的 Message 过滤，只看进程名
        # type != debug 用于过滤掉过于频繁的调试信息，只看默认和错误信息
        cmd = [
            "/usr/bin/log", "stream",
            "--style", "syslog",
            "--predicate", 'process == "CalendarAgent" && type != debug'
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1
            )

            print("🕵️ [LogSentinel] 哨兵已启动 (广谱监听模式)...")

            # [修改点 2] 引入冷却时间，防止日志刷屏导致触发太多
            last_trigger_time = 0
            COOLDOWN = 1.0  # 1秒内只触发一次

            while not self.stop_event.is_set():
                line = self.process.stdout.readline()
                if not line:
                    if self.process.poll() is not None:
                        break
                    continue
                
                # [调试用] 打印出来看看你的系统到底输出了什么日志
                # print(f"捕获日志: {line.strip()}") 

                # 只要有日志输出，就说明 CalendarAgent 在工作
                # 我们可以做一个简单的反向过滤，忽略掉 "Fetching" (读取) 这种操作
                if "Fetching" in line or "Reading" in line:
                    continue

                current_time = time.time()
                if current_time - last_trigger_time > COOLDOWN:
                    print(f"⚡ [LogSentinel] 捕获活动，触发同步！")
                    if self.callback:
                        self.callback()
                    last_trigger_time = current_time
                    
        except Exception as e:
            print(f"⚠️ [LogSentinel] 监听失败: {e}")
        finally:
            self.stop()

def start_log_sentinel(callback):
    """Helper to start the sentinel quickly."""
    sentinel = LogSentinel(callback)
    sentinel.start()
    return sentinel
