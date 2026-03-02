import sys
import datetime
sys.path.append('/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta/LyubishchevSync/src')
from external.task_sync_core.obsidian_service import get_obsidian_state
from config import Config
import os

today_str = datetime.date.today().strftime('%Y-%m-%d')
file_path = os.path.join(Config.DAILY_NOTE_DIR, f"{today_str}.md")
tasks, lines, mtime, idx = get_obsidian_state(file_path)
for k, v in tasks.items():
    print(f"{k}: {v}")
