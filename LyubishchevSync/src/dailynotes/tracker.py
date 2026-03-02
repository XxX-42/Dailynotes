import threading
import time

class WindowFocusTracker(threading.Thread):
    """
    [v3.4] 后台线程：高频记录窗口焦点历史
    使用 AppKit (PyObjC) 实现低功耗查询，避免 polling osascript
    """
    def __init__(self, history_len=20, interval=0.5):
        super().__init__()
        self.history = []  # List of (timestamp, app_name)
        self.history_len = history_len
        self.interval = interval
        self.daemon = True
        self.running = True
        self.lock = threading.Lock()
        self._ns_workspace = None
        
        # 尝试加载 AppKit
        try:
            from AppKit import NSWorkspace
            self._ns_workspace = NSWorkspace.sharedWorkspace()
        except ImportError:
            pass

    def run(self):
        while self.running:
            app_name = "Unknown"
            try:
                if self._ns_workspace:
                    # 极速方法 (微秒级)
                    front_app = self._ns_workspace.frontmostApplication()
                    if front_app:
                        app_name = front_app.localizedName()
                else:
                    # 回退方法 (较慢)
                    import subprocess
                    cmd = ['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true']
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=1)
                    app_name = res.stdout.strip()
            except Exception:
                pass
            
            with self.lock:
                now = time.time()
                self.history.append((now, app_name))
                if len(self.history) > self.history_len:
                    self.history.pop(0)
            
            time.sleep(self.interval)

    def was_app_active(self, target_app_name, seconds=5):
        """检查过去 N 秒内，目标应用是否出现过在前台"""
        now = time.time()
        start_time = now - seconds
        target_lower = target_app_name.lower()
        
        with self.lock:
            # 倒序遍历（从最近的开始）
            for ts, name in reversed(self.history):
                if ts < start_time:
                    break
                if name and target_lower in name.lower():
                    return True
        return False
    
    def stop(self):
        self.running = False
