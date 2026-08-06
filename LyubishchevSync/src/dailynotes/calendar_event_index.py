from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, Mapping, Optional


INDEX_SCHEMA_VERSION = 1


def _event_fingerprint(event: Mapping) -> str:
    payload = {
        "name": event.get("name", ""),
        "start_time": event.get("start_time", ""),
        "duration": event.get("duration", 0),
        "current_calendar": event.get("current_calendar", ""),
        "is_completed": bool(event.get("is_completed", False)),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_event_index(events_by_date: Mapping[str, Mapping[str, Mapping]]) -> Dict[str, Dict[str, str]]:
    """Build an EventKit-ID keyed index from date-grouped events."""
    result: Dict[str, Dict[str, str]] = {}
    for date_str, events in events_by_date.items():
        for event in events.values():
            event_id = str(event.get("id", "")).strip()
            if not event_id:
                raise ValueError(f"Calendar event on {date_str} has no stable EventKit ID")
            if event_id in result:
                raise ValueError(f"Duplicate EventKit ID in range query: {event_id}")
            result[event_id] = {
                "date": date_str,
                "fingerprint": _event_fingerprint(event),
                "calendar": str(event.get("current_calendar", "")),
            }
    return result


@dataclass(frozen=True)
class EventIndexDiff:
    added_ids: frozenset[str]
    removed_ids: frozenset[str]
    modified_ids: frozenset[str]
    affected_dates: frozenset[str]


def diff_event_indexes(
    previous: Mapping[str, Mapping[str, str]],
    current: Mapping[str, Mapping[str, str]],
) -> EventIndexDiff:
    old_ids = set(previous)
    new_ids = set(current)
    added = new_ids - old_ids
    removed = old_ids - new_ids
    modified = {
        event_id
        for event_id in old_ids & new_ids
        if previous[event_id].get("fingerprint") != current[event_id].get("fingerprint")
        or previous[event_id].get("date") != current[event_id].get("date")
    }

    dates = set()
    for event_id in added | modified:
        date_str = current[event_id].get("date")
        if date_str:
            dates.add(date_str)
    for event_id in removed | modified:
        date_str = previous[event_id].get("date")
        if date_str:
            dates.add(date_str)

    return EventIndexDiff(
        added_ids=frozenset(added),
        removed_ids=frozenset(removed),
        modified_ids=frozenset(modified),
        affected_dates=frozenset(dates),
    )


def diff_event_indexes_fast_window(
    previous: Mapping[str, Mapping[str, str]],
    current_window: Mapping[str, Mapping[str, str]],
    window_start: str,
    window_end: str,
) -> EventIndexDiff:
    """
    Return only changes that are safe to apply from a partial-window query.

    Removals and moves across the window boundary are intentionally deferred to
    the subsequent full-index comparison because a partial query cannot prove
    that an event was deleted rather than moved outside the window.
    """
    added = set()
    modified = set()
    dates = set()

    for event_id, current_entry in current_window.items():
        current_date = current_entry.get("date", "")
        previous_entry = previous.get(event_id)
        if previous_entry is None:
            added.add(event_id)
            if current_date:
                dates.add(current_date)
            continue

        previous_date = previous_entry.get("date", "")
        previous_in_window = window_start <= previous_date <= window_end
        changed = (
            previous_entry.get("fingerprint") != current_entry.get("fingerprint")
            or previous_date != current_date
        )
        if previous_in_window and changed:
            modified.add(event_id)
            if previous_date:
                dates.add(previous_date)
            if current_date:
                dates.add(current_date)

    return EventIndexDiff(
        added_ids=frozenset(added),
        removed_ids=frozenset(),
        modified_ids=frozenset(modified),
        affected_dates=frozenset(dates),
    )


class CalendarEventIndexStore:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> Optional[Dict[str, Dict[str, str]]]:
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("schema_version") != INDEX_SCHEMA_VERSION:
                return None
            events = payload.get("events")
            return events if isinstance(events, dict) else None
        except (OSError, ValueError, TypeError):
            return None

    def save(self, events: Mapping[str, Mapping[str, str]]) -> bool:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "schema_version": INDEX_SCHEMA_VERSION,
                        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                        "events": events,
                    },
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
                handle.flush()
                os.fsync(handle.fileno())

            if os.path.exists(self.path):
                try:
                    shutil.copy2(self.path, self.path + ".bak")
                except OSError:
                    pass
            os.replace(temp_path, self.path)
            temp_path = None
            return True
        except OSError:
            return False
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
