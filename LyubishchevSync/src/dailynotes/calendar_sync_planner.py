from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional, Set

from .calendar_event_index import EventIndexDiff


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valid_date(date_str: str, start_date: str, end_date: str) -> bool:
    if not isinstance(date_str, str) or not _DATE_RE.match(date_str):
        return False
    try:
        datetime.date.fromisoformat(date_str)
    except ValueError:
        return False
    return start_date <= date_str <= end_date


@dataclass(frozen=True)
class CalendarSyncPlan:
    candidate_dates: tuple[str, ...]
    reasons: Mapping[str, frozenset[str]]
    calendar_dates: frozenset[str]


def build_startup_plan(
    calendar_dates: Iterable[str],
    obsidian_tasks_by_date: Mapping[str, Mapping],
    snapshot_dates: Iterable[str],
    start_date: str,
    end_date: str,
) -> CalendarSyncPlan:
    reasons: Dict[str, Set[str]] = {}

    def add(date_str: str, reason: str) -> None:
        if _valid_date(date_str, start_date, end_date):
            reasons.setdefault(date_str, set()).add(reason)

    calendar_set = set(calendar_dates)
    for date_str in calendar_set:
        add(date_str, "calendar_current")
    for date_str, tasks in obsidian_tasks_by_date.items():
        if tasks:
            add(date_str, "obsidian_task")
    for date_str in snapshot_dates:
        add(date_str, "historical_snapshot")

    return CalendarSyncPlan(
        candidate_dates=tuple(sorted(reasons)),
        reasons={date: frozenset(values) for date, values in reasons.items()},
        calendar_dates=frozenset(
            date for date in calendar_set if _valid_date(date, start_date, end_date)
        ),
    )


def build_incremental_plan(
    index_diff: EventIndexDiff,
    calendar_dates: Iterable[str],
    start_date: str,
    end_date: str,
) -> CalendarSyncPlan:
    reasons: Dict[str, Set[str]] = {}

    def add(date_str: str, reason: str) -> None:
        if _valid_date(date_str, start_date, end_date):
            reasons.setdefault(date_str, set()).add(reason)

    for date_str in index_diff.affected_dates:
        add(date_str, "calendar_changed")

    calendar_set = set(calendar_dates)
    return CalendarSyncPlan(
        candidate_dates=tuple(sorted(reasons)),
        reasons={date: frozenset(values) for date, values in reasons.items()},
        calendar_dates=frozenset(
            date for date in calendar_set if _valid_date(date, start_date, end_date)
        ),
    )
