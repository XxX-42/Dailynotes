#!/usr/bin/env python3
"""Convert exported Apple Health CSV files into daily SyncFit JSON files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import logging
import math
import os
import signal
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


DEFAULT_INPUT_DIR = Path(
    "/Users/jiajia/Library/Mobile Documents/com~apple~CloudDocs/Sync/Health"
)
DEFAULT_OUTPUT_DIR = Path(
    "/Users/jiajia/Documents/Documents/Obsidian/远程仓库1/00_Archive/10_health"
)
DEFAULT_STATE_FILE = (
    Path.home() / "Library/Application Support/SyncFitHealth/state.json"
)

CSV_HEADERS = (
    "uuid",
    "metric",
    "start",
    "end",
    "value",
    "unit",
    "min",
    "max",
    "avg",
    "source",
    "source_bundle_id",
    "aggregation",
    "metadata",
    "details",
)

SUPPORTED_METRICS = {"heart_rate", "step_count", "sleep_analysis"}
SLEEP_STAGES = {
    0: "in_bed",
    1: "asleep_unspecified",
    2: "awake",
    3: "core",
    4: "deep",
    5: "rem",
}

STATE_VERSION = 1
STATE_TOP_LEVEL_KEYS = {"version", "samples"}
STATE_SAMPLE_KEYS = {
    "metric",
    "uuid",
    "start",
    "end",
    "value",
    "unit",
    "source_bundle_id",
    "source",
}

LOGGER = logging.getLogger("syncfit_health")


class SyncFitHealthError(Exception):
    """Base class for errors intended to be reported without a traceback."""


class CSVValidationError(SyncFitHealthError):
    """A CSV header or supported row is invalid."""


class StateCorruptionError(SyncFitHealthError):
    """Persisted internal state is invalid and must not be discarded."""


class DeferredInputError(SyncFitHealthError):
    """A file was still changing while it was being read; retry it later."""


class IgnoredInputError(SyncFitHealthError):
    """A queued path stopped being a direct regular CSV before processing."""


class AuditedRow(dict):
    """Dictionary row retaining DictReader's physical ending line number."""

    def __init__(self, values: Mapping[str, str], line_number: int) -> None:
        super().__init__(values)
        self.line_number = line_number


class AuditedRows(list):
    """Parsed rows plus the source signature that was stable during parsing."""

    def __init__(
        self,
        rows: Iterable[Mapping[str, str]],
        signature: Tuple[int, int, int, int, int],
    ) -> None:
        super().__init__(rows)
        self.stat_signature = signature


def parse_timestamp(value: str, *, context: str = "timestamp") -> Tuple[datetime, str]:
    """Parse an ISO timestamp, requiring an offset and retaining that offset."""
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    parse_text = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(parse_text)
    except (TypeError, ValueError) as exc:
        raise ValueError("must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("must include a timezone offset")
    # Preserve source text, including Z, offset spelling, and fractional-second
    # precision. Parsed datetimes are used for validation and sorting only.
    return parsed, text


def _stat_signature(path: Path) -> Tuple[int, int, int, int, int]:
    info = path.stat()
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_size),
        int(info.st_mtime_ns),
        int(info.st_ctime_ns),
    )


def _header_audit() -> str:
    return ", ".join(CSV_HEADERS)


def _row_error(path: Path, line_number: int, column: str, detail: str) -> CSVValidationError:
    return CSVValidationError(
        "{}:{}: invalid {!r}: {}; audited headers: {}".format(
            path, line_number, column, detail, _header_audit()
        )
    )


def read_csv(path: Path) -> List[Dict[str, str]]:
    """Read supported rows by header name and reject malformed supported rows.

    The input is opened read-only. A pre/post stat comparison covers the entire
    parse, so no partially-read file can reach the state commit.
    """
    source = Path(path)
    try:
        before = _stat_signature(source)
    except OSError as exc:
        raise DeferredInputError("{}: cannot stat CSV: {}".format(source, exc)) from exc

    parse_error: Optional[BaseException] = None
    result: List[Dict[str, str]] = []
    last_completed_line = 0
    try:
        descriptor = os.open(
            str(source),
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
        with os.fdopen(descriptor, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            headers = reader.fieldnames
            if headers is None:
                raise CSVValidationError(
                    "{}:1: missing header row; audited headers: {}".format(
                        source, _header_audit()
                    )
                )
            last_completed_line = reader.line_num
            if len(headers) != len(set(headers)):
                raise CSVValidationError(
                    "{}:1: duplicate header names; audited headers: {}".format(
                        source, _header_audit()
                    )
                )
            if set(headers) != set(CSV_HEADERS):
                raise CSVValidationError(
                    "{}:1: CSV headers do not match the audited schema; found {}; expected {}".format(
                        source, ", ".join(headers), _header_audit()
                    )
                )

            for row in reader:
                line_number = reader.line_num
                last_completed_line = line_number
                raw_metric = row.get("metric")
                if raw_metric is None or not raw_metric.strip():
                    raise _row_error(source, line_number, "metric", "must not be blank")
                metric = raw_metric.strip().lower()
                if metric not in SUPPORTED_METRICS:
                    continue
                if None in row:
                    raise _row_error(
                        source, line_number, "<row>", "contains more values than headers"
                    )
                if any(row.get(header) is None for header in CSV_HEADERS):
                    raise _row_error(
                        source, line_number, "<row>", "contains fewer values than headers"
                    )
                result.append(AuditedRow({header: row[header] for header in CSV_HEADERS}, line_number))
    except (csv.Error, UnicodeError) as exc:
        active_reader = locals().get("reader")
        line_number = max(
            getattr(active_reader, "line_num", 1),
            last_completed_line + 1,
        )
        parse_error = CSVValidationError(
            "{}:{}: malformed CSV: {}; audited headers: {}".format(
                source, line_number, exc, _header_audit()
            )
        )
    except Exception as exc:
        parse_error = exc

    try:
        after = _stat_signature(source)
    except OSError as exc:
        raise DeferredInputError("{}: cannot stat CSV after reading: {}".format(source, exc)) from exc
    if before != after:
        raise DeferredInputError("{}: CSV changed while it was being read".format(source))
    if parse_error is not None:
        raise parse_error
    return AuditedRows(result, after)


def _number(value: str, path: Path, line_number: int, column: str) -> Decimal:
    text = value.strip()
    if not text:
        raise _row_error(path, line_number, column, "must not be blank")
    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise _row_error(path, line_number, column, "must be a number") from exc
    if not parsed.is_finite():
        raise _row_error(path, line_number, column, "must be finite")
    return parsed


def normalize(row: Mapping[str, str], *, path: Path = Path("<row>"), line_number: int = 0) -> Dict[str, Any]:
    """Normalize one supported CSV row to the compact internal sample schema."""
    metric = (row.get("metric") or "").strip().lower()
    if metric not in SUPPORTED_METRICS:
        raise _row_error(path, line_number, "metric", "unsupported metric {!r}".format(metric))

    try:
        start_dt, start = parse_timestamp(row.get("start", ""), context="start")
    except ValueError as exc:
        raise _row_error(path, line_number, "start", str(exc)) from exc
    try:
        end_dt, end = parse_timestamp(row.get("end", ""), context="end")
    except ValueError as exc:
        raise _row_error(path, line_number, "end", str(exc)) from exc
    if end_dt < start_dt:
        raise _row_error(path, line_number, "end", "must not be earlier than start")

    number = _number(row.get("value", ""), path, line_number, "value")
    if metric == "heart_rate":
        normalized_value: Any = float(number)
        if not math.isfinite(normalized_value):
            raise _row_error(path, line_number, "value", "must be finite as a JSON number")
    elif metric == "step_count":
        if number != number.to_integral_value():
            raise _row_error(path, line_number, "value", "step count must be an integer")
        normalized_value = int(number)
    else:
        if number != number.to_integral_value():
            raise _row_error(path, line_number, "value", "sleep stage code must be an integer")
        stage_code = int(number)
        if stage_code not in SLEEP_STAGES:
            raise _row_error(path, line_number, "value", "unknown sleep stage code {}".format(stage_code))
        normalized_value = stage_code

    raw_uuid = (row.get("uuid") or "").strip()
    return {
        "metric": metric,
        "uuid": raw_uuid.lower() if raw_uuid else None,
        "start": start,
        "end": end,
        "value": normalized_value,
        "unit": (row.get("unit") or "").strip(),
        "source_bundle_id": (row.get("source_bundle_id") or "").strip(),
        "source": (row.get("source") or "").strip(),
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def output_payload(sample: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the exact public daily JSON item for an internal sample."""
    metric = sample["metric"]
    if metric == "heart_rate":
        return {"time": sample["start"], "bpm": sample["value"]}
    if metric == "step_count":
        return {
            "start": sample["start"],
            "end": sample["end"],
            "count": sample["value"],
        }
    if metric == "sleep_analysis":
        return {
            "start": sample["start"],
            "end": sample["end"],
            "stage": SLEEP_STAGES[sample["value"]],
        }
    raise ValueError("unknown metric in normalized sample: {!r}".format(metric))


def _identity_key(sample: Mapping[str, Any]) -> str:
    if sample["uuid"]:
        identity = ["uuid", sample["metric"], sample["uuid"]]
        prefix = "uuid"
    else:
        metric = sample["metric"]
        identity = [
            "fallback",
            metric,
            sample["start"],
            sample["end"],
            sample["value"],
            sample["unit"],
            sample["source_bundle_id"],
            sample["source"],
        ]
        prefix = "fallback"
    digest = hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()
    return "{}:{}".format(prefix, digest)


def _variant_key(sample: Mapping[str, Any]) -> str:
    if not sample["uuid"]:
        return "fallback"
    # These normalized sample fields define UUID conflicts. Source display
    # names are mutable and do not make an otherwise identical sample conflict.
    normalized = [
        sample["metric"],
        sample["start"],
        sample["end"],
        sample["value"],
        sample["unit"],
    ]
    digest = hashlib.sha256(_canonical_json(normalized).encode("utf-8")).hexdigest()
    return "sample:{}".format(digest)


def _sample_sort_key(sample: Mapping[str, Any]) -> Tuple[str, str]:
    return (_canonical_json(output_payload(sample)), _canonical_json(sample))


def deduplicate(samples: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Deduplicate by UUID or deterministic fallback and identify UUID conflicts.

    A UUID group is a conflict only when its normalized output samples differ.
    Source display names and CSV paths do not create conflicts. Conflicting
    variants remain in the returned candidate list so restart recovery retains
    their dates, but they are omitted from ``valid``.
    """
    groups: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for raw in samples:
        sample = dict(raw)
        identity = _identity_key(sample)
        variant = _variant_key(sample)
        group = groups.setdefault(identity, {})
        existing = group.get(variant)
        if existing is None or _sample_sort_key(sample) < _sample_sort_key(existing):
            group[variant] = sample

    candidates: List[Dict[str, Any]] = []
    valid: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    conflict_ids: List[str] = []
    for identity in sorted(groups):
        variants = [groups[identity][key] for key in sorted(groups[identity])]
        candidates.extend(variants)
        is_conflict = bool(variants and variants[0]["uuid"] and len(variants) > 1)
        if is_conflict:
            conflicts.append({"identity": identity, "variants": variants})
            conflict_ids.append("{}:{}".format(variants[0]["metric"], variants[0]["uuid"]))
        else:
            valid.extend(variants)

    candidates.sort(key=lambda sample: (_identity_key(sample), _variant_key(sample)))
    valid.sort(key=lambda sample: (_identity_key(sample), _variant_key(sample)))
    return {
        "candidates": candidates,
        "valid": valid,
        "conflicts": conflicts,
        "conflict_ids": conflict_ids,
    }


def split_by_day(samples: Iterable[Mapping[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group samples by the local calendar date of their start timestamp."""
    days: Dict[str, List[Dict[str, Any]]] = {}
    for raw in samples:
        sample = dict(raw)
        parsed, _ = parse_timestamp(sample["start"], context="state start")
        date_key = parsed.date().isoformat()
        days.setdefault(date_key, []).append(sample)
    for day_samples in days.values():
        day_samples.sort(key=_sample_sort_key)
    return days


def _instant_sort_key(value: str) -> datetime:
    parsed, _ = parse_timestamp(value)
    return parsed.astimezone(timezone.utc)


def build_daily_json(day: str, samples: Iterable[Mapping[str, Any]]) -> bytes:
    """Build a daily file with exactly three arrays and strict item schemas."""
    arrays: Dict[str, List[Tuple[Tuple[datetime, str], Dict[str, Any]]]] = {
        "heartRate": [],
        "steps": [],
        "sleep": [],
    }
    metric_to_array = {
        "heart_rate": "heartRate",
        "step_count": "steps",
        "sleep_analysis": "sleep",
    }
    items: List[Tuple[str, Dict[str, Any]]] = []
    for sample in samples:
        payload = output_payload(sample)
        start_value = payload.get("time", payload.get("start"))
        parsed, _ = parse_timestamp(start_value)
        if parsed.date().isoformat() != day:
            continue
        items.append((metric_to_array[sample["metric"]], payload))

    for array_name, payload in items:
        start_value = payload.get("time", payload.get("start"))
        sort_key = (
            _instant_sort_key(start_value),
            _canonical_json(payload),
        )
        # Sorting is repeated per array below; retain keys temporarily.
        arrays[array_name].append((sort_key, payload))

    encoded_arrays: Dict[str, List[Dict[str, Any]]] = {}
    for name in ("heartRate", "steps", "sleep"):
        typed_items = arrays[name]
        typed_items.sort(key=lambda pair: pair[0])
        encoded_arrays[name] = [payload for _, payload in typed_items]
    text = json.dumps(
        encoded_arrays,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )
    return (text + "\n").encode("utf-8")


def atomic_write(path: Path, content: bytes) -> bool:
    """Atomically replace a file unless its bytes already match.

    Returns True when the destination was replaced and False when it already
    contained exactly the requested bytes.
    """
    destination = Path(path)
    data = content.encode("utf-8") if isinstance(content, str) else content
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        if destination.read_bytes() == data:
            return False
    except FileNotFoundError:
        pass

    descriptor, temp_name = tempfile.mkstemp(
        prefix=".{}.".format(destination.name),
        suffix=".tmp",
        dir=str(destination.parent),
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp_path), str(destination))
        try:
            directory_fd = os.open(str(destination.parent), os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        return True
    except BaseException:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise


def _reject_constant(value: str) -> Any:
    raise ValueError("invalid JSON numeric constant {}".format(value))


def _no_duplicate_object_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key {!r}".format(key))
        result[key] = value
    return result


def _validate_state_sample(sample: Any, key: str) -> Dict[str, Any]:
    if not isinstance(sample, dict) or set(sample) != STATE_SAMPLE_KEYS:
        raise StateCorruptionError("state sample {!r} has an invalid schema".format(key))
    metric = sample["metric"]
    if not isinstance(metric, str) or metric not in SUPPORTED_METRICS:
        raise StateCorruptionError("state sample {!r} has an invalid metric".format(key))
    uuid_value = sample["uuid"]
    if uuid_value is not None and (
        not isinstance(uuid_value, str)
        or not uuid_value
        or uuid_value != uuid_value.strip().lower()
    ):
        raise StateCorruptionError("state sample {!r} has an invalid UUID".format(key))
    for field in ("start", "end"):
        if not isinstance(sample[field], str):
            raise StateCorruptionError("state sample {!r} has an invalid {}".format(key, field))
        try:
            parsed, preserved = parse_timestamp(sample[field], context=field)
        except ValueError as exc:
            raise StateCorruptionError(
                "state sample {!r} has invalid {} timestamp: {}".format(key, field, exc)
            ) from exc
        if preserved != sample[field] or sample[field] != sample[field].strip():
            raise StateCorruptionError(
                "state sample {!r} has surrounding whitespace in {} timestamp".format(key, field)
            )
        if field == "start":
            start_dt = parsed
        else:
            end_dt = parsed
    if end_dt < start_dt:
        raise StateCorruptionError("state sample {!r} ends before it starts".format(key))
    for field in ("unit", "source_bundle_id", "source"):
        if not isinstance(sample[field], str):
            raise StateCorruptionError("state sample {!r} has invalid {}".format(key, field))

    value = sample["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StateCorruptionError("state sample {!r} has an invalid value".format(key))
    if isinstance(value, float) and not math.isfinite(value):
        raise StateCorruptionError("state sample {!r} has a nonfinite value".format(key))
    if metric == "heart_rate":
        # Preserve integral CSV values as numbers without coercing them to int.
        pass
    elif metric == "step_count":
        if not isinstance(value, int):
            raise StateCorruptionError("state sample {!r} has a fractional step count".format(key))
    elif metric == "sleep_analysis":
        if not isinstance(value, int) or value not in SLEEP_STAGES:
            raise StateCorruptionError("state sample {!r} has an invalid sleep stage".format(key))
    return dict(sample)


def _empty_state() -> Dict[str, Any]:
    return {"version": STATE_VERSION, "samples": {}}


def _state_from_samples(samples: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    result = deduplicate(samples)
    groups: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for sample in result["candidates"]:
        identity = _identity_key(sample)
        variant = _variant_key(sample)
        groups.setdefault(identity, {})[variant] = dict(sample)
    return {"version": STATE_VERSION, "samples": groups}


def _flatten_state(state: Mapping[str, Any]) -> List[Dict[str, Any]]:
    flattened: List[Dict[str, Any]] = []
    for identity in sorted(state["samples"]):
        variants = state["samples"][identity]
        for variant in sorted(variants):
            flattened.append(dict(variants[variant]))
    return flattened


def _state_bytes(state: Mapping[str, Any]) -> bytes:
    return (json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode(
        "utf-8"
    )


def load_state(path: Path) -> Dict[str, Any]:
    """Load and strictly validate state. Corruption always fails closed."""
    state_path = Path(path)
    try:
        raw = state_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _empty_state()
    except (OSError, UnicodeError) as exc:
        raise StateCorruptionError("cannot read state {}: {}".format(state_path, exc)) from exc
    try:
        parsed = json.loads(
            raw,
            parse_constant=_reject_constant,
            object_pairs_hook=_no_duplicate_object_keys,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        raise StateCorruptionError("state JSON is corrupt at {}: {}".format(state_path, exc)) from exc
    if not isinstance(parsed, dict) or set(parsed) != STATE_TOP_LEVEL_KEYS:
        raise StateCorruptionError("state {} has an invalid top-level schema".format(state_path))
    if type(parsed["version"]) is not int or parsed["version"] != STATE_VERSION:
        raise StateCorruptionError("state {} has an unsupported version".format(state_path))
    groups = parsed["samples"]
    if not isinstance(groups, dict):
        raise StateCorruptionError("state {} samples must be an object".format(state_path))
    checked: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for identity, variants in groups.items():
        if not isinstance(identity, str) or not identity:
            raise StateCorruptionError("state contains an invalid identity key")
        if not isinstance(variants, dict) or not variants:
            raise StateCorruptionError("state identity {!r} has invalid variants".format(identity))
        checked_variants: Dict[str, Dict[str, Any]] = {}
        for variant, raw_sample in variants.items():
            if not isinstance(variant, str) or not variant:
                raise StateCorruptionError("state identity {!r} has an invalid variant key".format(identity))
            sample = _validate_state_sample(raw_sample, identity)
            if _identity_key(sample) != identity:
                raise StateCorruptionError("state identity key does not match its sample")
            if _variant_key(sample) != variant:
                raise StateCorruptionError("state variant key does not match its sample")
            checked_variants[variant] = sample
        if not next(iter(checked_variants.values()))["uuid"] and len(checked_variants) != 1:
            raise StateCorruptionError("fallback identity {!r} has multiple variants".format(identity))
        checked[identity] = checked_variants
    return {"version": STATE_VERSION, "samples": checked}


def _daily_path(output_dir: Path, day: str) -> Path:
    date = datetime.strptime(day, "%Y-%m-%d")
    return Path(output_dir) / date.strftime("health_%y-%m-%d.json")


def _refresh_outputs(output_dir: Path, samples: Iterable[Mapping[str, Any]]) -> None:
    result = deduplicate(samples)
    for conflict in result["conflicts"]:
        sample = conflict["variants"][0]
        LOGGER.warning(
            "conflicting normalized samples for %s UUID %s; all variants are excluded",
            sample["metric"],
            sample["uuid"],
        )

    all_days = split_by_day(result["candidates"])
    valid_days = split_by_day(result["valid"])
    for day in sorted(all_days):
        content = build_daily_json(day, valid_days.get(day, []))
        atomic_write(_daily_path(output_dir, day), content)


def process_csv_file(path: Path, output_dir: Path, state_file: Path) -> List[str]:
    """Read a complete CSV, commit state, then regenerate every affected day."""
    raw_rows = read_csv(path)
    normalized: List[Dict[str, Any]] = []
    for index, row in enumerate(raw_rows, start=2):
        line_number = getattr(row, "line_number", index)
        normalized.append(normalize(row, path=Path(path), line_number=line_number))

    state = load_state(state_file)
    previous = _flatten_state(state)
    combined = deduplicate(previous + normalized)["candidates"]
    next_state = _state_from_samples(combined)

    # Keep the read guard active through normalization and state loading. If a
    # sync client resumes a write during that work, discard this parse before
    # committing the new state.
    read_signature = getattr(raw_rows, "stat_signature", None)
    try:
        current_signature = _stat_signature(Path(path))
    except OSError as exc:
        raise DeferredInputError(
            "{}: cannot stat CSV before state commit: {}".format(path, exc)
        ) from exc
    if read_signature is None or current_signature != read_signature:
        raise DeferredInputError("{}: CSV changed before state commit".format(path))

    # Commit state first. If an output write fails, restart recovery can rebuild
    # every local date from the durable candidate set, including conflicts.
    atomic_write(state_file, _state_bytes(next_state))
    _refresh_outputs(output_dir, _flatten_state(next_state))
    return sorted({sample["start"][:10] for sample in normalized})


def wait_until_stable(
    path: Path,
    stable_seconds: float = 5.0,
    sample_interval: float = 1.0,
    timeout: float = 60.0,
    stop_event: Optional[threading.Event] = None,
    stat_fn: Callable[[Path], os.stat_result] = Path.stat,
) -> bool:
    """Wait until size and modification metadata stay unchanged continuously."""
    if stable_seconds < 0 or sample_interval <= 0 or timeout < 0:
        raise ValueError("stable timing values must be nonnegative and interval positive")
    source = Path(path)
    started = time.monotonic()
    stable_since: Optional[float] = None
    previous: Optional[Tuple[int, int, int, int, int]] = None
    while True:
        if stop_event is not None and stop_event.is_set():
            return False
        now = time.monotonic()
        if now - started > timeout:
            return False
        try:
            info = stat_fn(source)
            current = (
                int(info.st_dev),
                int(info.st_ino),
                int(info.st_size),
                int(info.st_mtime_ns),
                int(info.st_ctime_ns),
            )
        except OSError:
            current = None
        if current is not None and current == previous:
            if stable_since is not None and now - stable_since >= stable_seconds:
                return True
        elif current is not None:
            previous = current
            stable_since = now
        else:
            previous = None
            stable_since = None
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            return False
        delay = min(sample_interval, remaining)
        if stop_event is None:
            time.sleep(delay)
        elif stop_event.wait(delay):
            return False


class CSVWorker:
    """Single worker with per-path coalescing and deferred retries."""

    def __init__(
        self,
        processor: Callable[[Path], None],
        *,
        stable_seconds: float = 5.0,
        sample_interval: float = 1.0,
        stable_timeout: float = 60.0,
        retry_delay: float = 1.0,
        status_callback: Optional[Callable[[str, Optional[Path], Optional[str], Any], None]] = None,
    ) -> None:
        self.processor = processor
        self.stable_seconds = stable_seconds
        self.sample_interval = sample_interval
        self.stable_timeout = stable_timeout
        self.retry_delay = retry_delay
        self.status_callback = status_callback
        self._condition = threading.Condition()
        self._heap: List[Tuple[float, int, str]] = []
        self._queued: Dict[str, float] = {}
        self._processing: set = set()
        self._rerun: set = set()
        self._sequence = 0
        self._stopping = False
        self._stop_event = threading.Event()
        self._phase = "idle"
        self._current_file: Optional[str] = None
        self._thread = threading.Thread(target=self._run, name="syncfit-health-worker", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def enqueue(self, path: Path, delay: float = 0.0) -> None:
        candidate = Path(path).expanduser().absolute()
        if candidate.suffix.lower() != ".csv":
            return
        key = str(candidate)
        with self._condition:
            if self._stopping:
                return
            if key in self._processing:
                self._rerun.add(key)
                return
            due = time.monotonic() + max(0.0, delay)
            prior_due = self._queued.get(key)
            if prior_due is not None and prior_due <= due:
                return
            self._queued[key] = due
            self._sequence += 1
            heapq.heappush(self._heap, (due, self._sequence, key))
            self._condition.notify_all()

    def discard(self, path: Path) -> None:
        """Remove stale queued work for a CSV intentionally removed by retention."""
        key = str(Path(path).expanduser().absolute())
        with self._condition:
            self._queued.pop(key, None)
            self._rerun.discard(key)
            self._condition.notify_all()

    def stop(self, timeout: Optional[float] = None) -> None:
        self.request_stop()
        if self._thread.is_alive():
            self._thread.join(timeout)

    def request_stop(self) -> None:
        with self._condition:
            self._stopping = True
            self._stop_event.set()
            self._condition.notify_all()

    def snapshot(self) -> Dict[str, Any]:
        with self._condition:
            pending = len(self._queued) + len(self._rerun)
            return {
                "phase": self._phase,
                "current_file": self._current_file,
                "queued_count": pending,
            }

    def _report(
        self,
        state: str,
        path: Optional[Path] = None,
        error: Optional[str] = None,
        result: Any = None,
    ) -> None:
        with self._condition:
            self._phase = state
            self._current_file = str(path) if path is not None and state not in ("idle", "success") else None
        if self.status_callback is not None:
            try:
                self.status_callback(state, path, error, result)
            except Exception:
                LOGGER.exception("SyncFit Health status callback failed")

    def _take_next(self) -> Optional[str]:
        with self._condition:
            while True:
                if self._stopping:
                    return None
                while self._heap:
                    due, sequence, key = self._heap[0]
                    if self._queued.get(key) != due:
                        heapq.heappop(self._heap)
                        continue
                    remaining = due - time.monotonic()
                    if remaining > 0:
                        self._condition.wait(remaining)
                        break
                    heapq.heappop(self._heap)
                    del self._queued[key]
                    self._processing.add(key)
                    return key
                else:
                    self._condition.wait()

    def _finish(self, key: str, retry: bool) -> None:
        with self._condition:
            self._processing.discard(key)
            rerun = key in self._rerun
            self._rerun.discard(key)
            if self._stopping:
                return
            if rerun:
                self.enqueue(Path(key))
            elif retry:
                self.enqueue(Path(key), delay=self.retry_delay)

    def _run(self) -> None:
        while True:
            key = self._take_next()
            if key is None:
                return
            retry = False
            path = Path(key)
            try:
                self._report("waiting-file", path)
                stable = wait_until_stable(
                    path,
                    self.stable_seconds,
                    self.sample_interval,
                    self.stable_timeout,
                    stop_event=self._stop_event,
                )
                if not stable:
                    if not self._stop_event.is_set():
                        LOGGER.warning("CSV did not become stable before timeout: %s", key)
                        self._report("retry", path, "CSV did not become stable before timeout")
                        retry = True
                else:
                    self._report("processing", path)
                    result = self.processor(path)
                    if not self._stop_event.is_set():
                        self._report("success", path, result=result)
            except IgnoredInputError as exc:
                LOGGER.info("skipping %s: %s", key, exc)
            except (DeferredInputError, OSError) as exc:
                LOGGER.warning("will retry %s after transient error: %s", key, exc)
                self._report("retry", path, str(exc))
                retry = True
            except CSVValidationError as exc:
                LOGGER.error("%s", exc)
                self._report("error", path, str(exc))
            except StateCorruptionError as exc:
                LOGGER.error("%s", exc)
                self._report("error", path, str(exc))
            except Exception as exc:
                LOGGER.exception("unexpected failure while processing %s", key)
                self._report("error", path, str(exc) or "Unexpected processing failure for {}".format(path))
            finally:
                self._finish(key, retry)
                with self._condition:
                    stopping = self._stopping
                if not stopping:
                    self._report("idle")


class _CsvEventHandler:
    """Watchdog callback adapter; callbacks only enqueue paths."""

    def __init__(self, enqueue: Callable[[Path], None]) -> None:
        from watchdog.events import FileSystemEventHandler

        class Handler(FileSystemEventHandler):
            def on_created(self, event: Any) -> None:
                if not event.is_directory:
                    enqueue(Path(event.src_path))

            def on_modified(self, event: Any) -> None:
                # Modified events catch resumed writes when a sync client pauses
                # between chunks. Coalescing prevents an event storm from
                # starting concurrent conversions.
                if not event.is_directory:
                    enqueue(Path(event.src_path))

            def on_moved(self, event: Any) -> None:
                if not event.is_directory:
                    enqueue(Path(event.dest_path))

        self.handler = Handler()


def watcher(input_dir: Path, enqueue: Callable[[Path], None]) -> Any:
    """Start a nonrecursive directory observer, then queue its startup scan."""
    from watchdog.observers import Observer

    directory = Path(input_dir)
    if not directory.is_dir():
        raise SyncFitHealthError("input directory does not exist: {}".format(directory))
    observer = Observer()
    observer.schedule(_CsvEventHandler(enqueue).handler, str(directory), recursive=False)
    observer.start()
    # The observer is registered before this scan, closing the startup race.
    for candidate in sorted(directory.iterdir()):
        if candidate.is_file() and candidate.suffix.lower() == ".csv":
            enqueue(candidate)
    return observer


@contextmanager
def state_lock(state_file: Path) -> Iterable[None]:
    """Prevent two SyncFit Health processes from writing the same state/output."""
    import fcntl

    lock_path = Path(state_file).with_name(Path(state_file).name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SyncFitHealthError("another SyncFit Health instance holds {}".format(lock_path)) from exc
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert audited Apple Health CSV exports into daily SyncFit JSON files."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument(
        "--once",
        action="store_true",
        help="convert the current direct-child CSV files once, then exit",
    )
    parser.add_argument("--stable-seconds", type=float, default=5.0)
    parser.add_argument("--sample-interval", type=float, default=1.0)
    parser.add_argument("--stable-timeout", type=float, default=60.0)
    parser.add_argument("--retry-delay", type=float, default=1.0)
    return parser.parse_args(argv)


def _once(args: argparse.Namespace) -> None:
    if not args.input_dir.is_dir():
        raise SyncFitHealthError("input directory does not exist: {}".format(args.input_dir))
    state = load_state(args.state_file)
    _refresh_outputs(args.output_dir, _flatten_state(state))
    for candidate in sorted(args.input_dir.iterdir()):
        if not candidate.is_file() or candidate.suffix.lower() != ".csv":
            continue
        if not wait_until_stable(
            candidate,
            args.stable_seconds,
            args.sample_interval,
            args.stable_timeout,
        ):
            raise DeferredInputError("{} did not become stable before timeout".format(candidate))
        process_csv_file(candidate, args.output_dir, args.state_file)


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args(argv)
    args.input_dir = args.input_dir.expanduser().absolute()
    args.output_dir = args.output_dir.expanduser().absolute()
    args.state_file = args.state_file.expanduser().absolute()
    if not args.once:
        LOGGER.error(
            "The SyncFit Health watcher is managed by LyubishchevSync. "
            "Start LyubishchevSync/main.py; use --once only for a one-time diagnostic conversion."
        )
        return 2
    try:
        with state_lock(args.state_file):
            state = load_state(args.state_file)
            _refresh_outputs(args.output_dir, _flatten_state(state))
            if args.once:
                _once(args)
                return 0

            def process(path: Path) -> None:
                process_csv_file(path, args.output_dir, args.state_file)

            worker = CSVWorker(
                process,
                stable_seconds=args.stable_seconds,
                sample_interval=args.sample_interval,
                stable_timeout=args.stable_timeout,
                retry_delay=args.retry_delay,
            )
            worker.start()
            observer = None
            stop_event = threading.Event()

            def request_stop(signum: int, frame: Any) -> None:
                stop_event.set()

            previous_sigint = signal.getsignal(signal.SIGINT)
            previous_sigterm = signal.getsignal(signal.SIGTERM)
            try:
                signal.signal(signal.SIGINT, request_stop)
                signal.signal(signal.SIGTERM, request_stop)
                observer = watcher(args.input_dir, worker.enqueue)
                LOGGER.info("watching direct CSV files in %s", args.input_dir)
                while not stop_event.wait(1.0):
                    pass
            except KeyboardInterrupt:
                LOGGER.info("stopping SyncFit Health")
            finally:
                signal.signal(signal.SIGINT, previous_sigint)
                signal.signal(signal.SIGTERM, previous_sigterm)
                if observer is not None:
                    observer.stop()
                    observer.join()
                # Keep the process lock until any active parse/write finishes.
                worker.stop(timeout=None)
        return 0
    except (SyncFitHealthError, OSError) as exc:
        LOGGER.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
