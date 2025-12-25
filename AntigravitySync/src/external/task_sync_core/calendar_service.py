"""
Apple Calendar Service - Adapted for unified config.
"""
from datetime import datetime, timedelta
from config import Config
from .utils import escape_as_text, run_applescript

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
    Get all calendar events for a specific date.
    
    Args:
        target_dt: datetime object for target date
    
    Returns:
        dict: Calendar events keyed by "name_starttime"
    """
    cal_list_str = "{" + ", ".join([f'"{escape_as_text(c)}"' for c in ALL_MANAGED_CALENDARS]) + "}"

    # Construct date parameters for AppleScript
    y = target_dt.year
    m = target_dt.month
    d = target_dt.day

    script = f'''
    set event_data to ""
    set targetCalendars to {cal_list_str}

    -- [精准日期构建]
    set targetDate to current date
    set year of targetDate to {y}
    set month of targetDate to {m}
    set day of targetDate to {d}
    set time of targetDate to 0 -- 00:00:00

    set dayStart to targetDate
    set dayEnd to dayStart + (1 * days)

    tell application "Calendar"
        repeat with calName in targetCalendars
            if exists calendar calName then
                tell calendar calName
                    set all_events to (every event whose start date ≥ dayStart and start date < dayEnd)
                    repeat with e in all_events
                        try
                            set e_name to summary of e
                            set e_date to start date of e
                            set e_id to uid of e
                            set e_end to end date of e
                            set durationSeconds to (e_end - e_date)
                            set durationMins to (durationSeconds / 60) as integer

                            set h to (hours of e_date)
                            set m to (minutes of e_date)
                            set h_str to h as string
                            if h < 10 then set h_str to "0" & h_str
                            set m_str to m as string
                            if m < 10 then set m_str to "0" & m_str
                            set time_key to h_str & ":" & m_str

                            set event_data to event_data & e_name & "{DELIMITER_FIELD}" & time_key & "{DELIMITER_FIELD}" & e_id & "{DELIMITER_FIELD}" & calName & "{DELIMITER_FIELD}" & durationMins & "{DELIMITER_ROW}"
                        end try
                    end repeat
                end tell
            end if
        end repeat
    end tell
    return event_data
    '''
    output = run_applescript(script)
    calendar_events = {}
    if output is None:
        return calendar_events

    for entry in output.strip().split(DELIMITER_ROW):
        if not entry:
            continue
        try:
            parts = entry.split(DELIMITER_FIELD)
            if len(parts) < 5:
                continue
            raw_name, time_str, e_id, cal_name, duration_mins = parts

            is_completed = False
            clean_name = raw_name.strip()
            if clean_name.startswith("✅"):
                is_completed = True
                clean_name = clean_name.replace("✅", "", 1).strip()
            elif clean_name.startswith("✓"):
                is_completed = True
                clean_name = clean_name.replace("✓", "", 1).strip()

            key = f"{clean_name}_{time_str}"

            calendar_events[key] = {
                'name': clean_name,
                'id': e_id,
                'current_calendar': cal_name.strip(),
                'duration': int(duration_mins),
                'start_time': time_str,
                'is_completed': is_completed,
                'raw_name': raw_name.strip()
            }
        except:
            continue
    return calendar_events


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
