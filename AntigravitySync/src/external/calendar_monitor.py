import threading
import objc
from Foundation import NSObject, NSDistributedNotificationCenter
from PyObjCTools import AppHelper

class DistributedObserver(NSObject):
    """
    [Zero-Latency] System-wide Calendar Database Observer.
    Listens for 'com.apple.calendar.database.changed' distributed notification.
    """
    
    def initWithCallback_(self, callback):
        self = objc.super(DistributedObserver, self).init()
        if self is None:
            return None
        self.callback = callback
        return self
    
    def startListening(self):
        # Register for the hidden system broadcast
        NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self,
            "onCalendarChanged:",
            "com.apple.calendar.database.changed",
            None
        )
        print("📡 [Distributed] 成功挂载系统级日历变更广播 (零延迟模式)")
        
    def stopListening(self):
        NSDistributedNotificationCenter.defaultCenter().removeObserver_(self)
        
    def onCalendarChanged_(self, notification):
        """
        Callback triggered by the kernel/distributed center.
        """
        # Triggers immediately on database write
        if self.callback:
            self.callback()

def start_calendar_watchdog(on_change_callback):
    """
    Starts the Distributed Notification Observer in a background thread.
    """
    def _run_loop(callback):
        pool = objc.autorelease_pool()
        with pool:
            observer = DistributedObserver.alloc().initWithCallback_(callback)
            observer.startListening()
            
            try:
                # Install interrupt=False to allow main thread signals
                AppHelper.runConsoleEventLoop(installInterrupt=False)
            except Exception as e:
                print(f"⚠️ [Distributed] RunLoop Error: {e}")
            finally:
                if observer:
                    observer.stopListening()

    t = threading.Thread(target=_run_loop, args=(on_change_callback,), daemon=True, name="DistributedCalMonitor")
    t.start()
    return t
