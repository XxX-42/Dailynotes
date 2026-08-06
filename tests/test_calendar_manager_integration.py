import os
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from dailynotes.calendar_event_index import CalendarEventIndexStore, build_event_index
from dailynotes.manager import FusionManager


def event(event_id):
    return {
        "id": event_id,
        "name": "Task",
        "start_time": "10:00",
        "duration": 30,
        "current_calendar": "重要紧急",
        "is_completed": False,
    }


class FakeEventKitClient:
    def __init__(self, result):
        self.result = result

    def fetch_range_events_result(self, *args, **kwargs):
        return self.result


class CalendarManagerIntegrationTests(unittest.TestCase):
    def make_manager(self, index_path, fetch_result):
        manager = FusionManager.__new__(FusionManager)
        manager._ek_client = FakeEventKitClient(fetch_result)
        manager._sync_execution_lock = threading.RLock()
        manager._calendar_index_store = CalendarEventIndexStore(index_path)
        manager._last_calendar_sync_time = 0
        manager._set_gui_status = lambda *args, **kwargs: None
        manager._schedule_gui_idle = lambda *args, **kwargs: None
        manager._calendar_range = lambda: (
            __import__("datetime").date(2026, 8, 1),
            __import__("datetime").date(2026, 8, 31),
        )
        manager.sync_core = SimpleNamespace(scan_all_source_tasks=lambda: {})
        manager.apple_sync = SimpleNamespace(
            get_snapshot_dates=lambda: set(),
            is_available=lambda: True,
        )
        manager.calls = []

        def process(date_str, **kwargs):
            manager.calls.append((date_str, kwargs.get("calendar_has_events")))
            return {
                "apple_to_obsidian": False,
                "obsidian_to_apple": False,
                "success": True,
            }

        manager.process_single_date = process
        return manager

    def test_last_event_deletion_executes_old_date(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "index.json")
            store = CalendarEventIndexStore(path)
            store.save(build_event_index({"2026-08-10": {"key": event("event-1")}}))
            manager = self.make_manager(
                path,
                SimpleNamespace(ok=True, complete=True, events_by_date={}, error=None),
            )
            self.assertTrue(manager._sync_calendar_candidates(startup=False))
            self.assertEqual(manager.calls, [("2026-08-10", False)])

    def test_incomplete_fetch_never_executes_or_replaces_index(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "index.json")
            store = CalendarEventIndexStore(path)
            previous = build_event_index({"2026-08-10": {"key": event("event-1")}})
            store.save(previous)
            manager = self.make_manager(
                path,
                SimpleNamespace(ok=True, complete=False, events_by_date={}, error="parse failed"),
            )
            self.assertFalse(manager._sync_calendar_candidates(startup=False))
            self.assertEqual(manager.calls, [])
            self.assertEqual(store.load(), previous)

    def test_calendar_notifications_are_debounced(self):
        manager = FusionManager.__new__(FusionManager)
        manager._calendar_dirty_flag = False
        manager._calendar_event_lock = threading.Lock()
        manager._calendar_debounce_timer = None
        with mock.patch(
            "dailynotes.manager.Config.CALENDAR_NOTIFICATION_DEBOUNCE_SECONDS", 0.02
        ):
            manager._on_calendar_push_event()
            manager._on_calendar_push_event()
            manager._on_calendar_push_event()
            time.sleep(0.06)
        self.assertTrue(manager._calendar_dirty_flag)
        self.assertIsNone(manager._calendar_debounce_timer)


if __name__ == "__main__":
    unittest.main()
