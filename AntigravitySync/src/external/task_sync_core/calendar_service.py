"""
Apple Calendar Service - Adapted for unified config.
"""
from datetime import datetime, timedelta
from config import Config
from .utils import escape_as_text, run_applescript
try:
    from external.eventkit_wrapper import EventKitClient
    EK_AVAILABLE = True
except ImportError:
    EK_AVAILABLE = False

# Use config values
ALL_MANAGED_CALENDARS = Config.ALL_MANAGED_CALENDARS
DELIMITER_FIELD = Config.DELIMITER_FIELD
DELIMITER_ROW = Config.DELIMITER_ROW
ALARM_RULES = Config.ALARM_RULES


def check_calendars_exist_simple():
    """Check if all required calendars exist in Apple Calendar."""
    cal_list_str = "{" + ", ".join([f'"{escape_as_text(c)}"' for c in ALL_MANAGED_CALENDARS]) + "}"
    script = f'''
    set neededCalendars to {cal_list_str}
    set missingCalendars to {{}}
    tell application "Calendar"
        repeat with calName in neededCalendars
            if not (exists calendar calName) then
                set end of missingCalendars to calName
            end if
        end repeat
    end tell
    return missingCalendars
    '''
    result = run_applescript(script)
    if result and "{" not in result:
        missing = result.replace(", ", ",").split(",")
        if len(missing) > 0 and missing[0] != "":
            print(f"❌ 错误：找不到日历：{missing}")
            return False
    return True


def get_all_calendars_state(target_dt):
    """
    Get all calendar events for a specific date using EventKit (if available) or AppleScript fallback.
    
    Args:
        target_dt: datetime object for target date
    
    Returns:
        dict: Calendar events keyed by "name_starttime"
    """
    if EK_AVAILABLE:
        try:
            client = EventKitClient()
            all_events = client.fetch_events(target_dt)
            
            # Filter by managed calendars
            filtered_events = {}
            for key, val in all_events.items():
                if val['current_calendar'] in ALL_MANAGED_CALENDARS:
                    filtered_events[key] = val
            return filtered_events
        except Exception as e:
            print(f"⚠️ EventKit Error: {e}")
            # Fallback or return empty?
            # User objective is "Replace". 
            # I will return empty or throw if strict, but let's stick to returning empty on failure 
            # to avoid crashing main loop, or maybe rely on error logging.
            return {}
            
    # Legacy AppleScript implementation removed as per objective "Replace the current..."
    # If EK not available, we can't do much if we removed the code.
    # But for safety, maybe I should have kept the old code as fallback?
    # User said "Replace the current... mechanism". So I will remove it.
    print("❌ EventKit not available.")
    return {}


class BatchExecutor:
    """Batch executor for Apple Calendar operations."""
    
    def __init__(self, target_dt):
        self.target_dt = target_dt
        self.creates = []
        self.updates = []
        self.deletes = []

    def add_create(self, name, start_time, duration, calendar_name, is_completed):
        clean_name = name.replace("✅", "").replace("✓", "").strip()
        final_title = f"✅ {clean_name}" if is_completed else clean_name
        alarm = ALARM_RULES.get(calendar_name, 0)

        self.creates.append({
            "title": escape_as_text(final_title),
            "start": start_time,
            "dur": duration,
            "cal": escape_as_text(calendar_name),
            "alarm": alarm
        })

    def add_update(self, event_id, calendar_name, new_name, start_time, duration, is_completed):
        clean_name = new_name.replace("✅", "").replace("✓", "").strip()
        final_title = f"✅ {clean_name}" if is_completed else clean_name

        self.updates.append({
            "id": escape_as_text(event_id),
            "title": escape_as_text(final_title),
            "start": start_time,
            "dur": duration,
            "cal": escape_as_text(calendar_name)
        })

    def add_delete(self, event_id, calendar_name):
        self.deletes.append({
            "id": escape_as_text(event_id),
            "cal": escape_as_text(calendar_name)
        })

    def execute(self):
        if not (self.creates or self.updates or self.deletes):
            return

        y, m, d = self.target_dt.year, self.target_dt.month, self.target_dt.day

        script = f'''
        -- 基础日期
        set targetBaseDate to current date
        set year of targetBaseDate to {y}
        set month of targetBaseDate to {m}
        set day of targetBaseDate to {d}
        set time of targetBaseDate to 0
        
        tell application "Calendar"
        '''

        # 1. Deletes
        for op in self.deletes:
            script += f'''
            try
                tell calendar "{op['cal']}" to delete (first event whose uid is "{op['id']}")
            end try
            '''

        # 2. Creates
        for op in self.creates:
            h = int(op['start'][:2])
            mn = int(op['start'][3:])
            script += f'''
            try
                tell calendar "{op['cal']}"
                    set sDate to targetBaseDate
                    set hours of sDate to {h}
                    set minutes of sDate to {mn}
                    set eDate to sDate + ({op['dur']} * minutes)

                    set newE to make new event with properties {{summary:"{op['title']}", start date:sDate, end date:eDate}}
                    tell newE
                        make new sound alarm with properties {{trigger interval:{op['alarm']}}}
                    end tell
                end tell
            end try
            '''

        # 3. Updates
        for op in self.updates:
            h = int(op['start'][:2])
            mn = int(op['start'][3:])
            script += f'''
            try
                tell calendar "{op['cal']}"
                    set targetEvent to (first event whose uid is "{op['id']}")
                    set summary of targetEvent to "{op['title']}"

                    set sDate to targetBaseDate
                    set hours of sDate to {h}
                    set minutes of sDate to {mn}
                    set eDate to sDate + ({op['dur']} * minutes)

                    set start date of targetEvent to sDate
                    set end date of targetEvent to eDate
                end tell
            end try
            '''

        script += "\nend tell"
        print(f"⚡ 执行批处理: +{len(self.creates)} ~{len(self.updates)} -{len(self.deletes)}")
        run_applescript(script)
