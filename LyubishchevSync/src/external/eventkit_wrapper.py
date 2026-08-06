import objc
import threading
import datetime
import time
from dataclasses import dataclass
from typing import Dict, Optional
from EventKit import EKEventStore, EKEntityTypeEvent
from Foundation import NSDate, NSDistributedNotificationCenter, NSObject, NSNotificationCenter
from PyObjCTools import AppHelper

# 定义通知名称常量
EKEventStoreChangedNotification = "EKEventStoreChangedNotification"
DistributedCalendarChangedNotification = "com.apple.calendar.database.changed"


@dataclass(frozen=True)
class CalendarFetchResult:
    ok: bool
    complete: bool
    events_by_date: Dict
    error: Optional[str] = None

class CalendarObserver(NSObject):
    """
    Observer class to handle calendar change notifications.
    Running in a background NSRunLoop via AppHelper.runConsoleEventLoop.
    """
    def initWithCallback_(self, callback):
        self = objc.super(CalendarObserver, self).init()
        if self:
            self.callback = callback
            self._registered = False
        return self

    def startObserving(self):
        if self._registered:
            return
            
        center = NSNotificationCenter.defaultCenter()
        dist_center = NSDistributedNotificationCenter.defaultCenter()
        
        # 1. 监听进程内通知 (EventKit)
        center.addObserver_selector_name_object_(
            self,
            "onCalendarChanged:",
            EKEventStoreChangedNotification,
            None
        )
        
        # 2. 监听系统级分布式通知 (底层的数据库变更)
        dist_center.addObserver_selector_name_object_(
            self,
            "onCalendarChanged:",
            DistributedCalendarChangedNotification,
            None
        )
        
        self._registered = True
        print("✅ [CalendarObserver] 开始监听日历变更通知...")

    def stopObserving(self):
        if not self._registered:
            return
            
        center = NSNotificationCenter.defaultCenter()
        dist_center = NSDistributedNotificationCenter.defaultCenter()
        
        center.removeObserver_(self)
        dist_center.removeObserver_(self)
        self._registered = False
        print("🛑 [CalendarObserver] 停止监听。")

    def onCalendarChanged_(self, notification):
        """
        Callback for both local and distributed notifications.
        """
        try:
            # print(f"⚡ [EventKit] 收到通知: {notification.name()}")
            if hasattr(self, 'callback') and self.callback:
                # 回调必须异常安全，防止由于 Python 错误导致 ObjC 崩溃
                self.callback()
        except Exception as e:
            print(f"⚠️ [CalendarObserver] 回调执行失败: {e}")

    def stopRunLoop(self):
        """
        Stop the current thread's run loop.
        Must be called ON the thread running the loop, or used via strict threading controls.
        For simplicity in this daemon setup, we rely on AppHelper.stopEventLoop()
        """
        AppHelper.stopEventLoop()

class EventKitClient:
    def __init__(self):
        self.store = EKEventStore.alloc().init()
        self.access_granted = False
        self._observer = None

    def check_access(self):
        """
        请求日历访问权限。
        注意：在 macOS 14+ 中，系统对权限要求极严。
        """
        group = threading.Event()
        
        def callback(granted, error):
            self.access_granted = granted
            if error:
                print(f"❌ 权限请求错误: {error}")
            group.set()

        # [DEBUG] Check current status first
        status = EKEventStore.authorizationStatusForEntityType_(EKEntityTypeEvent)
        print(f"ℹ️ 当前权限状态代码: {status} (0=NotDetermined, 1=Restricted, 2=Denied, 3+=Authorized)")
        
        if status == 2: # Denied
             print("⚠️ 权限已被明确拒绝。系统不会再次弹窗。")
             print("👉 请运行: tccutil reset Calendar")
             return False

        # 检查是否存在新版 API (macOS 14+)
        if hasattr(self.store, 'requestFullAccessToEventsWithCompletion_'):
            self.store.requestFullAccessToEventsWithCompletion_(callback)
        else:
            # 兼容旧版 macOS
            self.store.requestAccessToEntityType_completion_(EKEntityTypeEvent, callback)
        
        # 等待回调，超时时间设为 30s，防止进程永久挂起
        finished = group.wait(timeout=30)
        if not finished:
            print("⚠️ 权限请求超时：用户未响应或系统拦截。")
            
        return self.access_granted

    def start_watching(self, callback):
        """
        启动日历变更监听。
        
        [v2.0 ARCHITECTURE FIX]
        关键发现：EKEventStoreChangedNotification 只会被投递到创建 EKEventStore 的线程。
        由于 EKEventStore 在主线程创建，通知也只能在主线程接收。
        
        新策略：
        1. 在主线程注册 Observer（通过 performSelectorOnMainThread）
        2. 回调设置一个线程安全的 dirty flag
        3. 业务代码通过轮询检查 flag（已在 manager.py 实现）
        
        注意：这不再需要后台 RunLoop，因为主程序的事件循环会处理通知。
        """
        if not self.access_granted:
            if not self.check_access():
                print("🚫 无法启动监听：没有日历访问权限。")
                return

        if self._observer:
            print("⚠️ 监听器已在运行。")
            return

        # [v2.0] 直接在当前线程（即主程序运行的线程）注册 Observer
        # 因为 check_access() 和 EKEventStore 都是在这里创建的
        self._observer = CalendarObserver.alloc().initWithCallback_(callback)
        self._observer.startObserving()
        
        # [v3.0 Architecture] 彻底移除后台由于强制 Nudge 的 Thread
        # 依赖于 manager.py 中的 CFRunLoop 死等和中断机制


    def stop_watching(self):
        """
        停止监听并关闭后台线程。
        """
        if self._observer:
            # 由于 runConsoleEventLoop 阻塞了后台线程，我们需要在那个线程中触发 stop
            # 使用 performSelector:onThread:withObject:waitUntilDone:
            # 注意：daemon 线程通常随主进程退出，但为了优雅关闭，我们可以尝试停止它
            
            # 在 Python/PyObjC 中，跨线程调用不如原生 ObjC 方便。
            # 简单策略：直接调用 stopObserving (虽然不是线程完全安全，但通常仅仅是解绑通知)
            # 真正停止 runLoop 需要在特定线程执行。
            
            # 方案：利用 performSelectorOnMainThread 或者直接让 daemon 随风而去。
            # 为了严谨，我们尝试调用 stopObserving
            try:
                self._observer.stopObserving()
            except Exception as e:
                print(f"⚠️ 停止监听时发生警告: {e}")
                
            self._observer = None
            # 注意：AppHelper.runConsoleEventLoop() 很难从外部线程优雅终止，
            # 除非我们发送一个专门的 selector 到该线程。
            # 作为一个 daemon 线程，不再持有引用即可。

    def fetch_events(self, target_dt):
        if not self.access_granted:
            # [Fix] 再次检查权限，防止初始化时失败但后来用户授权的情况
            if not self.check_access():
                print("🚫 访问被拒绝：请在 '系统设置 > 隐私与安全性 > 日历' 中授权终端/Python。")
                return {}

        # 确保 target_dt 为 date 对象
        target_date = target_dt.date() if isinstance(target_dt, datetime.datetime) else target_dt
        
        # 构建当天 00:00:00 到 23:59:59 的时间范围
        start_dt = datetime.datetime.combine(target_date, datetime.time.min)
        end_dt = datetime.datetime.combine(target_date, datetime.time.max)
        
        # 转换为 NSDate
        ns_start = NSDate.dateWithTimeIntervalSince1970_(start_dt.timestamp())
        ns_end = NSDate.dateWithTimeIntervalSince1970_(end_dt.timestamp())

        # 创建查询谓词
        predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(
            ns_start, ns_end, None 
        )

        # 执行查询
        events = self.store.eventsMatchingPredicate_(predicate)
        
        result = {}
        if not events:
            return result
            
        from Foundation import NSCalendar, NSCalendarUnitHour, NSCalendarUnitMinute
        
        # 获取用户当前日历历法
        calendar = NSCalendar.currentCalendar()
        
        for event in events:
            try:
                title = event.title() or "无标题"
                # 处理完成状态标识（根据现有逻辑保持一致）
                is_completed = any(title.startswith(prefix) for prefix in ["✅", "✓"])
                clean_name = title.lstrip("✅✓").strip()
                
                # [NEW] 1. 提取日历名称
                cal_title = event.calendar().title() if event.calendar() else "Unknown"

                # [NEW] 2. 计算开始时间 (HH:MM)
                # 使用 NSCalendar 提取组件以确保时区正确
                components = calendar.components_fromDate_(NSCalendarUnitHour | NSCalendarUnitMinute, event.startDate())
                start_time_str = f"{components.hour():02d}:{components.minute():02d}"

                # [NEW] 3. 计算持续时长 (分钟)
                duration_seconds = event.endDate().timeIntervalSinceDate_(event.startDate())
                duration_minutes = int(duration_seconds / 60)
                
                # [v2.0.1] 生成唯一 Key: {clean_name}_{start_time}_{id_tail}
                # id_tail 取 eventIdentifier 的后 6 位，确保即使有同名同时间的事件也不会覆盖
                event_id = event.eventIdentifier() or ""
                id_tail = event_id[-6:] if len(event_id) >= 6 else event_id
                key = f"{clean_name}_{start_time_str}_{id_tail}"
                
                # [v2.0.1] 同时生成语义 Key (用于与 Obsidian 模糊匹配)
                semantic_key = f"{clean_name}_{start_time_str}"
                
                # [v2.0.1] 构造完整字典
                result[key] = {
                    'name': clean_name,
                    'id': event_id,
                    'is_completed': is_completed,
                    'raw_name': title,
                    'current_calendar': cal_title,
                    'start_time': start_time_str,
                    'duration': duration_minutes,
                    'semantic_key': semantic_key  # 供 sync_engine 进行模糊匹配
                }
            except Exception as e:
                print(f"⚠️ 处理事件失败: {e}")
                continue
            
        return result

    def fetch_range_events_result(self, start_date, end_date, batch_days=1460, calendar_names=None):
        """
        [v3.0 Chronos Mode] 获取日期范围内的所有事件
        
        由于 EventKit 对超长时间范围有限制（约4年），此方法自动将大范围拆分为多个批次。
        
        Args:
            start_date: 起始日期 (date 或 datetime)
            end_date: 结束日期 (date 或 datetime)
            batch_days: 每批次的天数（默认1460天≈4年）
        
        Returns:
            dict: {date_str: {key: event_data, ...}, ...}
                  按日期分组的事件字典
        """
        if not self.access_granted:
            if not self.check_access():
                print("🚫 访问被拒绝：请在 '系统设置 > 隐私与安全性 > 日历' 中授权终端/Python。")
                return CalendarFetchResult(False, False, {}, "calendar_access_denied")

        # 标准化日期
        if isinstance(start_date, datetime.datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime.datetime):
            end_date = end_date.date()
        
        from Foundation import NSCalendar, NSCalendarUnitHour, NSCalendarUnitMinute, NSCalendarUnitYear, NSCalendarUnitMonth, NSCalendarUnitDay
        calendar = NSCalendar.currentCalendar()
        
        # 计算总天数
        total_days = (end_date - start_date).days + 1
        
        # 按日期分组的结果
        result_by_date = {}  # {date_str: {key: event_data}}
        allowed_calendars = set(calendar_names) if calendar_names is not None else None
        parse_errors = []
        
        # 分批获取
        current_start = start_date
        batch_count = 0
        
        while current_start <= end_date:
            batch_count += 1
            current_end = min(current_start + datetime.timedelta(days=batch_days - 1), end_date)
            
            # 构建时间范围
            start_dt = datetime.datetime.combine(current_start, datetime.time.min)
            end_dt = datetime.datetime.combine(current_end, datetime.time.max)
            
            ns_start = NSDate.dateWithTimeIntervalSince1970_(start_dt.timestamp())
            ns_end = NSDate.dateWithTimeIntervalSince1970_(end_dt.timestamp())
            
            try:
                predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(
                    ns_start, ns_end, None
                )
                events = self.store.eventsMatchingPredicate_(predicate)
            except Exception as e:
                return CalendarFetchResult(False, False, {}, f"eventkit_query_failed: {e}")
            
            if events:
                for event in events:
                    try:
                        title = event.title() or "无标题"
                        is_completed = any(title.startswith(prefix) for prefix in ["✅", "✓"])
                        clean_name = title.lstrip("✅✓").strip()
                        
                        cal_title = event.calendar().title() if event.calendar() else "Unknown"
                        if allowed_calendars is not None and cal_title not in allowed_calendars:
                            continue
                        
                        # 提取开始日期和时间
                        event_start = event.startDate()
                        components = calendar.components_fromDate_(
                            NSCalendarUnitYear | NSCalendarUnitMonth | NSCalendarUnitDay | NSCalendarUnitHour | NSCalendarUnitMinute,
                            event_start
                        )
                        
                        event_date_str = f"{components.year():04d}-{components.month():02d}-{components.day():02d}"
                        start_time_str = f"{components.hour():02d}:{components.minute():02d}"
                        
                        # 计算持续时长
                        duration_seconds = event.endDate().timeIntervalSinceDate_(event_start)
                        duration_minutes = int(duration_seconds / 60)
                        
                        # 生成唯一 Key
                        event_id = event.eventIdentifier() or ""
                        if not event_id:
                            raise ValueError("managed Calendar event has no stable eventIdentifier")
                        id_tail = event_id[-6:] if len(event_id) >= 6 else event_id
                        key = f"{clean_name}_{start_time_str}_{id_tail}"
                        semantic_key = f"{clean_name}_{start_time_str}"
                        
                        # 初始化日期分组
                        if event_date_str not in result_by_date:
                            result_by_date[event_date_str] = {}
                        
                        result_by_date[event_date_str][key] = {
                            'name': clean_name,
                            'id': event_id,
                            'is_completed': is_completed,
                            'raw_name': title,
                            'current_calendar': cal_title,
                            'start_time': start_time_str,
                            'duration': duration_minutes,
                            'semantic_key': semantic_key
                        }
                    except Exception as e:
                        print(f"⚠️ 处理事件失败: {e}")
                        parse_errors.append(str(e))
                        continue
            
            # 移动到下一批次
            current_start = current_end + datetime.timedelta(days=1)
        
        print(f"📅 [EventKit] 范围查询完成: {start_date} ~ {end_date} ({total_days}天, {batch_count}批次, {len(result_by_date)}天有事件)")
        if parse_errors:
            return CalendarFetchResult(
                True,
                False,
                result_by_date,
                f"{len(parse_errors)} event(s) could not be parsed",
            )
        return CalendarFetchResult(True, True, result_by_date)

    def fetch_range_events(self, start_date, end_date, batch_days=1460):
        """Compatibility wrapper for callers that still expect a dictionary."""
        result = self.fetch_range_events_result(start_date, end_date, batch_days)
        if not result.ok or not result.complete:
            return {}
        return result.events_by_date
if __name__ == "__main__":
    # 简单的测试桩
    from Foundation import NSBundle
    
    print("🚀 测试 EventKitClient...")
    
    # Diagnostic: Check for Usage Description
    keys = ["NSCalendarsUsageDescription", "NSCalendarsFullAccessUsageDescription"]
    info = NSBundle.mainBundle().infoDictionary()
    missing_keys = [k for k in keys if not info.get(k)]
    
    if missing_keys:
        print(f"⚠️ 警告: 当前运行环境 (Python) 缺失 Info.plist 键: {missing_keys}")
        print("    这可能导致系统拒绝弹窗授权。")
        print("    建议尝试: 在系统自带的 '终端 (Terminal.app)' 中运行此脚本。")

    client = EventKitClient()
    
    if client.check_access():
        print("✅ 授权成功，准备测试监听...")
        
        def on_change():
            print("🔔 [Main] 收到日历变更回调！可以执行同步逻辑了。")
            
        client.start_watching(on_change)
        
        print("⏳ 正在监听中，请去日历 App 修改一个日程 (按 Ctrl+C 退出)...")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 测试结束")
            client.stop_watching()
    else:
        print("❌ 授权失败")
