"""
Apple Sync State Manager - Manages sync state for Apple Calendar integration.
Renamed from state_manager.py to avoid conflict with Dailynotes StateManager.
"""
import os
import json
from datetime import datetime


class StateManager:
    """Manages bidirectional sync state between Obsidian and Apple Calendar."""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.data = self.load()

    def load(self):
        """Load state from file."""
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save(self):
        """Save state to file."""
        temp_path = self.filepath + ".tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.filepath)
        except IOError:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def get_snapshot(self, date_str):
        """Get the last known state snapshot for a date."""
        if date_str not in self.data:
            return {}, {}
        entry = self.data[date_str]
        return entry.get("obsidian", {}), entry.get("calendar", {})

    def update_snapshot(self, date_str, obs_state, cal_state):
        """Update the state snapshot for a date."""
        clean_obs = {}
        for k, v in obs_state.items():
            clean_obs[k] = {
                'name': v['name'],
                'start_time': v['start_time'],
                'end_time': v['end_time'],
                'target_calendar': v['target_calendar'],
                'tag': v.get('tag', ''),
                'status': v.get('status', ' ')
            }
        clean_cal = {}
        for k, v in cal_state.items():
            clean_cal[k] = {
                'name': v['name'],
                'id': v['id'],
                'current_calendar': v['current_calendar'],
                'duration': v['duration'],
                'start_time': v.get('start_time', ''),
                'is_completed': v.get('is_completed', False)
            }
        self.data[date_str] = {
            "obsidian": clean_obs,
            "calendar": clean_cal,
            "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.save()
