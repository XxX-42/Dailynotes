"""
TaskSynctoreminder utilities adapted for unified config.
"""
import subprocess
from datetime import datetime, timedelta


def escape_as_text(text):
    """Escape text for AppleScript."""
    if not text:
        return ""
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')


def run_applescript(script):
    """Execute AppleScript and return output."""
    try:
        process = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True
        )
        return process.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def calculate_duration_minutes(start_str, end_str):
    """Calculate duration in minutes between two time strings."""
    if not end_str:
        return 30
    try:
        t1 = datetime.strptime(start_str, "%H:%M")
        t2 = datetime.strptime(end_str, "%H:%M")
        if t2 < t1:
            t2 += timedelta(days=1)
        return int((t2 - t1).total_seconds() / 60)
    except ValueError:
        return 30
