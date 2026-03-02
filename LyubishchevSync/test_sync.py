import sys
import os
sys.path.append('/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta/LyubishchevSync/src')
from external.apple_sync_adapter import AppleSyncAdapter
from config import Config
import datetime

adapter = AppleSyncAdapter()
today_str = datetime.date.today().strftime('%Y-%m-%d')
print(f"Testing sync for today: {today_str}")
obs_mod, cal_mod = adapter.sync_day(today_str)
print(f"Result: obs_mod={obs_mod}, cal_mod={cal_mod}")
