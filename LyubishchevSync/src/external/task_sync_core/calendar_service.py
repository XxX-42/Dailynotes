"""
Apple Calendar Service - EventKit Native Implementation (v2.0)

重写说明：
- 完全移除 AppleScript 依赖，使用 PyObjC/EventKit 原生 API
- 复用 eventkit_wrapper.py 的 EventKitClient 单例
- 保持函数签名不变以兼容 sync_engine.py
"""
from datetime import datetime, timedelta
from config import Config

# EventKit imports
try:
    from EventKit import EKEventStore, EKEntityTypeEvent, EKEvent, EKAlarm, EKSpanThisEvent
    from Foundation import NSDate
    from external.eventkit_wrapper import EventKitClient
    EK_AVAILABLE = True
except ImportError:
    EK_AVAILABLE = False

# Use config values
ALL_MANAGED_CALENDARS = Config.ALL_MANAGED_CALENDARS
ALARM_RULES = Config.ALARM_RULES

# [v2.0 FIX] 单例 EventKitClient，避免创建过多 EKEventStore 实例
_ek_client_singleton = None

def _get_ek_client():
    """获取或创建 EventKitClient 单例"""
    global _ek_client_singleton
    if _ek_client_singleton is None and EK_AVAILABLE:
        from external.eventkit_wrapper import EventKitClient
        _ek_client_singleton = EventKitClient()
        # 确保已授权
        if not _ek_client_singleton.access_granted:
            _ek_client_singleton.check_access()
    return _ek_client_singleton


# =============================================================================
# Helper Functions for EventKit
# =============================================================================

def _datetime_to_nsdate(target_dt: datetime, time_str: str):
    """
    Convert a target date and time string (HH:MM) to NSDate.
    
    Args:
        target_dt: The target date (datetime object)
        time_str: Time in "HH:MM" format
    
    Returns:
        NSDate object representing the combined datetime
    """
    h = int(time_str[:2])
    m = int(time_str[3:5])
    
    # Combine date with time
    combined_dt = datetime(
        year=target_dt.year,
        month=target_dt.month,
        day=target_dt.day,
        hour=h,
        minute=m,
        second=0
    )
    
    return NSDate.dateWithTimeIntervalSince1970_(combined_dt.timestamp())


def _find_calendar_by_name(store, calendar_name: str):
    """
    Find an EKCalendar by its title.
    
    Args:
        store: EKEventStore instance
        calendar_name: The calendar title to find
    
    Returns:
        EKCalendar object or None if not found
    """
    calendars = store.calendarsForEntityType_(EKEntityTypeEvent)
    if not calendars:
        return None
    
    for cal in calendars:
        if cal.title() == calendar_name:
            return cal
    
    return None


def check_calendars_exist_simple():
    """Check if all required calendars exist in Apple Calendar using EventKit."""
    client = _get_ek_client()
    if not client:
        print("❌ EventKit not available.")
        return False
    
    store = client.store
    missing_calendars = []
    
    for cal_name in ALL_MANAGED_CALENDARS:
        if _find_calendar_by_name(store, cal_name) is None:
            missing_calendars.append(cal_name)
    
    if missing_calendars:
        print(f"❌ 错误：找不到日历：{missing_calendars}")
        return False
    
    return True


def get_all_calendars_state(target_dt):
    """
    Get all calendar events for a specific date using EventKit.
    
    Args:
        target_dt: datetime object for target date
    
    Returns:
        dict: Calendar events keyed by "name_starttime_idtail"
    """
    client = _get_ek_client()
    if client:
        try:
            all_events = client.fetch_events(target_dt)
            
            # Filter by managed calendars
            filtered_events = {}
            for key, val in all_events.items():
                if val['current_calendar'] in ALL_MANAGED_CALENDARS:
                    filtered_events[key] = val
            return filtered_events
        except Exception as e:
            print(f"⚠️ EventKit Error: {e}")
            return {}
            
    print("❌ EventKit not available.")
    return {}


class BatchExecutor:
    """
    Batch executor for Apple Calendar operations using EventKit.
    
    所有操作先缓存，execute() 时统一执行。
    """
    
    def __init__(self, target_dt):
        self.target_dt = target_dt
        self.creates = []
        self.updates = []
        self.deletes = []

    def add_create(self, name, start_time, duration, calendar_name, is_completed):
        """
        Queue a create operation.
        
        Args:
            name: Event title
            start_time: Start time in "HH:MM" format
            duration: Duration in minutes
            calendar_name: Target calendar name
            is_completed: Whether the task is marked complete
        """
        clean_name = name.replace("✅", "").replace("✓", "").strip()
        final_title = f"✅ {clean_name}" if is_completed else clean_name
        alarm = ALARM_RULES.get(calendar_name, 0)

        self.creates.append({
            "title": final_title,
            "start": start_time,
            "dur": duration,
            "cal": calendar_name,
            "alarm": alarm  # 负数表示提前分钟数
        })

    def add_update(self, event_id, calendar_name, new_name, start_time, duration, is_completed):
        """
        Queue an update operation.
        
        Args:
            event_id: Existing event identifier
            calendar_name: Calendar containing the event
            new_name: New event title
            start_time: New start time in "HH:MM" format
            duration: New duration in minutes
            is_completed: Whether the task is marked complete
        """
        clean_name = new_name.replace("✅", "").replace("✓", "").strip()
        final_title = f"✅ {clean_name}" if is_completed else clean_name

        self.updates.append({
            "id": event_id,
            "title": final_title,
            "start": start_time,
            "dur": duration,
            "cal": calendar_name
        })

    def add_delete(self, event_id, calendar_name):
        """
        Queue a delete operation.
        
        Args:
            event_id: Event identifier to delete
            calendar_name: Calendar containing the event
        """
        self.deletes.append({
            "id": event_id,
            "cal": calendar_name
        })

    def execute(self):
        """
        Execute all queued operations using EventKit.
        
        Operations are executed in order: deletes → creates → updates
        This ensures no ID conflicts when recreating moved events.
        """
        if not (self.creates or self.updates or self.deletes):
            return

        client = _get_ek_client()
        if not client:
            print("❌ [BatchExecutor] EventKit 不可用，无法执行操作")
            return
        
        if not client.access_granted:
            print("❌ [BatchExecutor] 没有日历访问权限")
            return

        store = client.store
        
        success_count = {"delete": 0, "create": 0, "update": 0}
        error_count = {"delete": 0, "create": 0, "update": 0}

        # =====================================================================
        # 1. DELETE Operations
        # =====================================================================
        for op in self.deletes:
            try:
                event = store.eventWithIdentifier_(op['id'])
                if event:
                    # removeEvent:span:commit:error: 
                    # span: EKSpanThisEvent (只删除这一个事件，不影响重复事件)
                    # commit: True (立即提交)
                    success, error = store.removeEvent_span_commit_error_(
                        event, EKSpanThisEvent, True, None
                    )
                    if success:
                        success_count["delete"] += 1
                    else:
                        error_count["delete"] += 1
                        if error:
                            print(f"⚠️ [Delete] 失败 ({op['id'][:8]}...): {error}")
                else:
                    # 事件不存在，算作成功（幂等）
                    success_count["delete"] += 1
            except Exception as e:
                error_count["delete"] += 1
                print(f"❌ [Delete] 异常 ({op['id'][:8] if op['id'] else 'N/A'}...): {e}")

        # =====================================================================
        # 2. CREATE Operations
        # =====================================================================
        for op in self.creates:
            try:
                # 1. Find target calendar
                cal = _find_calendar_by_name(store, op['cal'])
                if not cal:
                    print(f"⚠️ [Create] 找不到日历: {op['cal']}")
                    error_count["create"] += 1
                    continue

                # 2. Create new event
                event = EKEvent.eventWithEventStore_(store)
                event.setTitle_(op['title'])
                event.setCalendar_(cal)
                
                # 3. Set start/end dates
                start_nsdate = _datetime_to_nsdate(self.target_dt, op['start'])
                # Duration in minutes -> seconds
                end_timestamp = start_nsdate.timeIntervalSince1970() + (op['dur'] * 60)
                end_nsdate = NSDate.dateWithTimeIntervalSince1970_(end_timestamp)
                
                event.setStartDate_(start_nsdate)
                event.setEndDate_(end_nsdate)
                
                # 4. Add alarm if configured
                alarm_offset = op.get('alarm', 0)
                if alarm_offset != 0:
                    # EventKit alarm offset is in seconds (negative = before event)
                    alarm = EKAlarm.alarmWithRelativeOffset_(alarm_offset * 60)
                    event.addAlarm_(alarm)
                
                # 5. Save
                success, error = store.saveEvent_span_commit_error_(
                    event, EKSpanThisEvent, True, None
                )
                if success:
                    success_count["create"] += 1
                else:
                    error_count["create"] += 1
                    if error:
                        print(f"⚠️ [Create] 保存失败 ({op['title'][:20]}): {error}")
                        
            except Exception as e:
                error_count["create"] += 1
                print(f"❌ [Create] 异常 ({op['title'][:20] if op.get('title') else 'N/A'}): {e}")

        # =====================================================================
        # 3. UPDATE Operations
        # =====================================================================
        for op in self.updates:
            try:
                # 1. Get existing event
                event = store.eventWithIdentifier_(op['id'])
                if not event:
                    print(f"⚠️ [Update] 事件不存在: {op['id'][:8]}...")
                    error_count["update"] += 1
                    continue

                # 2. Update properties
                event.setTitle_(op['title'])
                
                # 3. Update start/end dates
                start_nsdate = _datetime_to_nsdate(self.target_dt, op['start'])
                end_timestamp = start_nsdate.timeIntervalSince1970() + (op['dur'] * 60)
                end_nsdate = NSDate.dateWithTimeIntervalSince1970_(end_timestamp)
                
                event.setStartDate_(start_nsdate)
                event.setEndDate_(end_nsdate)
                
                # 4. Note: Calendar change is handled by delete+create in sync_engine
                #    We don't change calendar here to avoid complexity
                
                # 5. Save
                success, error = store.saveEvent_span_commit_error_(
                    event, EKSpanThisEvent, True, None
                )
                if success:
                    success_count["update"] += 1
                else:
                    error_count["update"] += 1
                    if error:
                        print(f"⚠️ [Update] 保存失败 ({op['title'][:20]}): {error}")
                        
            except Exception as e:
                error_count["update"] += 1
                print(f"❌ [Update] 异常 ({op['id'][:8] if op.get('id') else 'N/A'}): {e}")

        # =====================================================================
        # Summary
        # =====================================================================
        total_success = sum(success_count.values())
        total_errors = sum(error_count.values())
        
        if total_errors > 0:
            print(f"⚡ 执行批处理: +{success_count['create']} ~{success_count['update']} -{success_count['delete']} (❌{total_errors}错误)")
        else:
            print(f"⚡ 执行批处理: +{success_count['create']} ~{success_count['update']} -{success_count['delete']}")
