import objc
import threading
import datetime
import time
from EventKit import EKEventStore, EKEntityTypeReminder
from Foundation import NSDate, NSDistributedNotificationCenter, NSObject, NSNotificationCenter
from PyObjCTools import AppHelper

# 定义通知名称常量
EKEventStoreChangedNotification = "EKEventStoreChangedNotification"

class ReminderObserver(NSObject):
    """
    Observer class to handle reminder change notifications.
    Running in the main thread (or capable thread) to receive notifications.
    """
    def initWithCallback_(self, callback):
        self = objc.super(ReminderObserver, self).init()
        if self:
            self.callback = callback
            self._registered = False
        return self

    def startObserving(self):
        if self._registered:
            return
            
        center = NSNotificationCenter.defaultCenter()
        
        # 监听进程内通知 (EventKit)
        center.addObserver_selector_name_object_(
            self,
            "onStoreChanged:",
            EKEventStoreChangedNotification,
            None
        )
        
        self._registered = True
        print("✅ [ReminderObserver] 开始监听提醒事项变更通知...")

    def stopObserving(self):
        if not self._registered:
            return
            
        center = NSNotificationCenter.defaultCenter()
        center.removeObserver_(self)
        self._registered = False
        print("🛑 [ReminderObserver] 停止监听。")

    def onStoreChanged_(self, notification):
        """
        Callback for notifications.
        """
        try:
            if hasattr(self, 'callback') and self.callback:
                self.callback()
        except Exception as e:
            print(f"⚠️ [ReminderObserver] 回调执行失败: {e}")

class ReminderKitClient:
    def __init__(self):
        self.store = EKEventStore.alloc().init()
        self.access_granted = False
        self._observer = None

    def check_access(self):
        """
        请求提醒事项访问权限。
        """
        group = threading.Event()
        
        def callback(granted, error):
            self.access_granted = granted
            if error:
                print(f"❌ Reminder 权限请求错误: {error}")
            group.set()

        # [DEBUG] Check current status first
        status = EKEventStore.authorizationStatusForEntityType_(EKEntityTypeReminder)
        print(f"ℹ️ 当前 Reminder 权限状态: {status} (0=NotDetermined, 1=Restricted, 2=Denied, 3+=Authorized)")
        
        if status == 2: # Denied
             print("⚠️ Reminder 权限已被明确拒绝。系统不会再次弹窗。")
             print("👉 请运行: tccutil reset Reminders")
             return False

        # 检查是否存在新版 API (macOS 14+)
        if hasattr(self.store, 'requestFullAccessToRemindersWithCompletion_'):
            self.store.requestFullAccessToRemindersWithCompletion_(callback)
        else:
            # 兼容旧版 macOS
            self.store.requestAccessToEntityType_completion_(EKEntityTypeReminder, callback)
        
        # 等待回调，超时时间设为 30s
        finished = group.wait(timeout=30)
        if not finished:
            print("⚠️ Reminder 权限请求超时。")
            
        return self.access_granted

    def start_watching(self, callback):
        """
        启动提醒事项变更监听。
        """
        if not self.access_granted:
            if not self.check_access():
                print("🚫 无法启动监听：没有提醒事项访问权限。")
                return

        if self._observer:
            print("⚠️ Reminder 监听器已在运行。")
            return

        # 直接在当前线程（假设是主线程）注册 Observer
        self._observer = ReminderObserver.alloc().initWithCallback_(callback)
        self._observer.startObserving()
        
        # 可以在这里复用 EventKitWrapper 中的 runloop_nudge 逻辑，
        # 或者假设主程序已经有了 RunLoop 机制 (FusionManager 使用 CFRunLoopRunInMode)

    def stop_watching(self):
        """
        停止监听。
        """
        if self._observer:
            try:
                self._observer.stopObserving()
            except Exception as e:
                print(f"⚠️ 停止 Reminder 监听时发生警告: {e}")
            self._observer = None

    def fetch_reminders(self, start_date=None, end_date=None):
        """
        获取提醒事项。
        注意：fetchRemindersMatchingPredicate 是异步的！
        为了适配同步调用风格，我们需要用 threading.Event 等待回调。
        """
        if not self.access_granted:
            if not self.check_access():
                return {}

        # 如果没有指定日期，默认获取所有未完成的
        # 这里为了简化，我们获取所有的 (incomplete) 提醒事项，或者根据日期范围获取。
        # Predicate documentation:
        # predicateForRemindersInCalendars: (New logic) -> Fetch all incomplete?
        # predicateForIncompleteRemindersWithDueDateStarting:ending:calendars:
        # predicateForCompletedRemindersWithCompletionDateStarting:ending:calendars:
        
        # 策略：获取所有未完成 + 指定日期范围内完成的
        
        result_reminders = {}
        group = threading.Event()
        
        def completion_callback(reminders):
            if reminders:
                 for r in reminders:
                    self._process_reminder(r, result_reminders)
            group.set()
            
        # 1. 获取未完成的 (Incomplete)
        predicate_incomplete = self.store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
            None, None, None
        )
        self.store.fetchRemindersMatchingPredicate_completion_(predicate_incomplete, completion_callback)
        group.wait(timeout=10)
        
        # 2. 如果指定了日期范围，获取该范围内完成的 (Completed)
        if start_date and end_date:
            group.clear()
            
            # Convert to NSDate
            ns_start = self._to_nsdate(start_date)
            ns_end = self._to_nsdate(end_date)
            
            predicate_completed = self.store.predicateForCompletedRemindersWithCompletionDateStarting_ending_calendars_(
                ns_start, ns_end, None
            )
            self.store.fetchRemindersMatchingPredicate_completion_(predicate_completed, completion_callback)
            group.wait(timeout=10)

        return result_reminders

    def _to_nsdate(self, dt):
        if isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
             dt = datetime.datetime.combine(dt, datetime.time.min)
        return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())

    def _process_reminder(self, reminder, result_dict):
        try:
            title = reminder.title() or "无标题"
            rid = reminder.calendarItemIdentifier()
            is_completed = reminder.isCompleted()
            
            # 提取 List 名称
            list_title = reminder.calendar().title() if reminder.calendar() else "Unknown"
            
            # 提取日期
            due_date = None
            if reminder.dueDateComponents():
                comps = reminder.dueDateComponents()
                # 注意：dueDateComponents 可能没有 year/month/day (如果只设置了时间?)
                # 通常 Reminders 都有日期
                if comps.year() != 2147483647: # NSDateComponentUndefined
                     due_date = f"{comps.year():04d}-{comps.month():02d}-{comps.day():02d}"
            
            # 如果没有 due date，可能不处理？或者归类为 Inbox
            if not due_date:
                due_date = "NoDate"

            if due_date not in result_dict:
                result_dict[due_date] = []

            result_dict[due_date].append({
                'id': rid,
                'title': title,
                'is_completed': is_completed,
                'list': list_title,
                'priority': reminder.priority(),
                'notes': reminder.notes()
            })
        except Exception as e:
            print(f"⚠️ 处理 Reminder 失败: {e}")

if __name__ == "__main__":
    client = ReminderKitClient()
    if client.check_access():
        print("✅ 授权成功")
        res = client.fetch_reminders()
        print(f"📦 Fetched Reminders: {len(res)} dates")
        for date, items in res.items():
            print(f"  📅 {date}: {len(items)} items")
            for item in items[:3]:
                print(f"    - [{ 'x' if item['is_completed'] else ' ' }] {item['title']} ({item['list']})")
