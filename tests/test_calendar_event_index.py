import json
import os
import tempfile
import unittest

from dailynotes.calendar_event_index import (
    CalendarEventIndexStore,
    build_event_index,
    diff_event_indexes,
    diff_event_indexes_fast_window,
)


def event(event_id, name="Task", start="10:00", duration=30, calendar="重要紧急"):
    return {
        "id": event_id,
        "name": name,
        "start_time": start,
        "duration": duration,
        "current_calendar": calendar,
        "is_completed": False,
    }


class CalendarEventIndexTests(unittest.TestCase):
    def test_last_event_deletion_keeps_old_date_affected(self):
        previous = build_event_index({"2026-08-10": {"key": event("event-1")}})
        diff = diff_event_indexes(previous, {})
        self.assertEqual(diff.removed_ids, {"event-1"})
        self.assertEqual(diff.affected_dates, {"2026-08-10"})

    def test_cross_date_move_affects_both_dates(self):
        previous = build_event_index({"2026-08-10": {"key": event("event-1")}})
        current = build_event_index({"2026-08-12": {"key": event("event-1")}})
        diff = diff_event_indexes(previous, current)
        self.assertEqual(diff.modified_ids, {"event-1"})
        self.assertEqual(diff.affected_dates, {"2026-08-10", "2026-08-12"})

    def test_title_change_is_modified(self):
        previous = build_event_index({"2026-08-10": {"key": event("event-1")}})
        current = build_event_index(
            {"2026-08-10": {"key": event("event-1", name="Renamed")}}
        )
        self.assertEqual(diff_event_indexes(previous, current).modified_ids, {"event-1"})

    def test_missing_or_duplicate_event_id_is_rejected(self):
        missing = event("")
        with self.assertRaises(ValueError):
            build_event_index({"2026-08-10": {"missing": missing}})
        with self.assertRaises(ValueError):
            build_event_index(
                {
                    "2026-08-10": {"one": event("event-1")},
                    "2026-08-11": {"two": event("event-1")},
                }
            )

    def test_store_round_trip_and_corrupt_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "index.json")
            store = CalendarEventIndexStore(path)
            payload = {"event-1": {"date": "2026-08-10", "fingerprint": "abc"}}
            self.assertTrue(store.save(payload))
            self.assertEqual(store.load(), payload)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("not-json")
            self.assertIsNone(store.load())

    def test_fast_window_defers_removal_and_cross_boundary_move(self):
        previous = build_event_index(
            {
                "2026-08-10": {"removed": event("removed")},
                "2026-09-20": {"moved": event("moved")},
            }
        )
        current_window = build_event_index(
            {
                "2026-08-12": {
                    "new": event("new"),
                    "moved": event("moved"),
                }
            }
        )
        diff = diff_event_indexes_fast_window(
            previous,
            current_window,
            "2026-08-01",
            "2026-08-31",
        )
        self.assertEqual(diff.added_ids, {"new"})
        self.assertEqual(diff.removed_ids, set())
        self.assertEqual(diff.modified_ids, set())
        self.assertEqual(diff.affected_dates, {"2026-08-12"})


if __name__ == "__main__":
    unittest.main()
