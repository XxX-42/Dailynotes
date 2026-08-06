import unittest

from dailynotes.calendar_event_index import EventIndexDiff
from dailynotes.calendar_sync_planner import build_incremental_plan, build_startup_plan


class CalendarSyncPlannerTests(unittest.TestCase):
    def test_startup_uses_three_source_union(self):
        plan = build_startup_plan(
            calendar_dates={"2026-08-08", "2026-08-09"},
            obsidian_tasks_by_date={"2026-08-09": {"a": {}}, "2026-08-20": {"b": {}}},
            snapshot_dates={"2026-08-10"},
            start_date="2026-08-01",
            end_date="2026-08-31",
        )
        self.assertEqual(
            plan.candidate_dates,
            ("2026-08-08", "2026-08-09", "2026-08-10", "2026-08-20"),
        )
        self.assertEqual(plan.reasons["2026-08-20"], {"obsidian_task"})
        self.assertEqual(plan.reasons["2026-08-10"], {"historical_snapshot"})

    def test_empty_registry_seed_dates_are_ignored(self):
        plan = build_startup_plan(
            calendar_dates=set(),
            obsidian_tasks_by_date={"2026-08-09": {}},
            snapshot_dates=set(),
            start_date="2026-08-01",
            end_date="2026-08-31",
        )
        self.assertEqual(plan.candidate_dates, ())

    def test_invalid_and_out_of_range_dates_are_ignored(self):
        plan = build_startup_plan(
            calendar_dates={"not-a-date", "2026-09-01"},
            obsidian_tasks_by_date={"2026-02-30": {"a": {}}},
            snapshot_dates={"2026-07-31"},
            start_date="2026-08-01",
            end_date="2026-08-31",
        )
        self.assertEqual(plan.candidate_dates, ())

    def test_incremental_plan_uses_old_and_new_affected_dates(self):
        diff = EventIndexDiff(
            added_ids=frozenset(),
            removed_ids=frozenset(),
            modified_ids=frozenset({"event-1"}),
            affected_dates=frozenset({"2026-08-10", "2026-08-12"}),
        )
        plan = build_incremental_plan(
            diff,
            calendar_dates={"2026-08-12"},
            start_date="2026-08-01",
            end_date="2026-08-31",
        )
        self.assertEqual(plan.candidate_dates, ("2026-08-10", "2026-08-12"))
        self.assertEqual(plan.calendar_dates, {"2026-08-12"})


if __name__ == "__main__":
    unittest.main()
