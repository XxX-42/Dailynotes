import csv
import itertools
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "LyubishchevSync" / "src"))

import external.syncfit_health as sync  # noqa: E402


def row(metric, start, end, value, **overrides):
    values = {
        "uuid": "sample-1",
        "metric": metric,
        "start": start,
        "end": end,
        "value": str(value),
        "unit": "count" if metric == "step_count" else "",
        "min": "",
        "max": "",
        "avg": "",
        "source": "Phone",
        "source_bundle_id": "com.example.health",
        "aggregation": "",
        "metadata": "",
        "details": "",
    }
    values.update(overrides)
    return values


def write_csv(path, rows, headers=None):
    fieldnames = list(headers or sync.CSV_HEADERS)
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in rows:
            writer.writerow(item)


def eventually(predicate, timeout=4.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


class NormalizeTests(unittest.TestCase):
    def test_metric_mappings_preserve_fractional_heart_rate_and_stage_names(self):
        heart = sync.normalize(
            row(
                "heart_rate",
                "2026-10-03T08:00:00.250+08:00",
                "2026-10-03T08:00:01.250+08:00",
                "72.375",
            )
        )
        self.assertEqual(sync.output_payload(heart), {
            "time": "2026-10-03T08:00:00.250+08:00",
            "bpm": 72.375,
        })
        steps = sync.normalize(
            row(
                "step_count",
                "2026-10-03T08:00:00+08:00",
                "2026-10-03T09:00:00+08:00",
                "128",
            )
        )
        self.assertEqual(sync.output_payload(steps), {
            "start": "2026-10-03T08:00:00+08:00",
            "end": "2026-10-03T09:00:00+08:00",
            "count": 128,
        })
        for code, stage in sync.SLEEP_STAGES.items():
            sleep = sync.normalize(
                row(
                    "sleep_analysis",
                    "2026-10-03T00:00:00+08:00",
                    "2026-10-03T00:30:00+08:00",
                    str(code),
                )
            )
            self.assertEqual(sync.output_payload(sleep)["stage"], stage)

    def test_supported_bad_values_abort_with_file_line_header_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.csv"
            write_csv(path, [
                row("heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "70"),
                row("step_count", "2026-10-03T08:00:00+08:00", "2026-10-03T09:00:00+08:00", "1.5"),
            ])
            raw = sync.read_csv(path)
            with self.assertRaises(sync.CSVValidationError) as caught:
                sync.normalize(raw[1], path=path, line_number=raw[1].line_number)
            message = str(caught.exception)
            self.assertIn("bad.csv:3", message)
            self.assertIn("'value'", message)
            self.assertIn("source_bundle_id", message)

    def test_timezone_end_order_finite_and_sleep_code_are_required(self):
        cases = [
            (row("heart_rate", "2026-10-03T08:00:00", "2026-10-03T08:00:01+08:00", "70"), "start"),
            (row("heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T07:59:59+08:00", "70"), "end"),
            (row("heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "NaN"), "value"),
            (row("sleep_analysis", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "6"), "value"),
        ]
        for sample, column in cases:
            with self.subTest(column=column, sample=sample):
                with self.assertRaises(sync.CSVValidationError) as caught:
                    sync.normalize(sample, path=Path("sample.csv"), line_number=9)
                self.assertIn("sample.csv:9", str(caught.exception))
                self.assertIn(repr(column), str(caught.exception))

    def test_header_name_read_supports_reordered_bom_headers_and_ignores_unknown_metric(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "export.csv"
            reversed_headers = list(reversed(sync.CSV_HEADERS))
            write_csv(
                path,
                [
                    row("heart_rate", "2026-10-03T08:00:00Z", "2026-10-03T08:00:01Z", "71.5"),
                    row("oxygen_saturation", "", "", "not-a-number"),
                ],
                headers=reversed_headers,
            )
            rows = sync.read_csv(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(sync.normalize(rows[0])["value"], 71.5)

    def test_malformed_unknown_metric_row_is_ignored_before_row_shape_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "unknown-short.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(sync.CSV_HEADERS)
                writer.writerow(["uuid", "unhandled_metric"])
                writer.writerow(list(row(
                    "heart_rate", "2026-10-03T08:00:00Z", "2026-10-03T08:00:01Z", "71.5"
                ).values()))
            parsed = sync.read_csv(path)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(sync.normalize(parsed[0])["value"], 71.5)

    def test_malformed_csv_reports_path_line_and_header_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "quoted.csv"
            with path.open("w", encoding="utf-8-sig") as handle:
                handle.write(",".join(sync.CSV_HEADERS) + "\n")
                handle.write('uuid,heart_rate,2026-10-03T08:00:00Z,2026-10-03T08:00:01Z,"70\n')
            with self.assertRaises(sync.CSVValidationError) as caught:
                sync.read_csv(path)
            message = str(caught.exception)
            self.assertIn("quoted.csv:2", message)
            self.assertIn("audited headers", message)

    def test_timestamp_retains_local_timezone_and_z_is_valid(self):
        parsed, normalized = sync.parse_timestamp("2026-10-03T08:00:00Z")
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)
        self.assertEqual(normalized, "2026-10-03T08:00:00Z")


class DedupAndOutputTests(unittest.TestCase):
    def test_uuid_case_is_canonical_and_source_display_alone_does_not_conflict(self):
        one = sync.normalize(row(
            "heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "70.25",
            uuid="ABC-DEF", source="Phone",
        ))
        two = sync.normalize(row(
            "heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "70.25",
            uuid="abc-def", source="Watch",
        ))
        result = sync.deduplicate([two, one])
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["candidates"][0]["uuid"], "abc-def")

    def test_conflicting_uuid_variants_remain_internal_but_are_excluded(self):
        first = sync.normalize(row(
            "heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "70", uuid="same"
        ))
        second = sync.normalize(row(
            "heart_rate", "2026-10-04T08:00:00+08:00", "2026-10-04T08:00:01+08:00", "71", uuid="SAME"
        ))
        result = sync.deduplicate([second, first])
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(result["valid"], [])
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertEqual(set(sync.split_by_day(result["candidates"])), {"2026-10-03", "2026-10-04"})

    def test_uuid_conflict_includes_end_and_unit_even_when_public_payload_matches(self):
        first = sync.normalize(row(
            "heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "70",
            uuid="same", unit="count/min",
        ))
        different_end = sync.normalize(row(
            "heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:02+08:00", "70",
            uuid="SAME", unit="count/min",
        ))
        different_unit = sync.normalize(row(
            "heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "70",
            uuid="same", unit="bpm",
        ))
        result = sync.deduplicate([first, different_end, different_unit])
        self.assertEqual(len(result["candidates"]), 3)
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertEqual(result["valid"], [])

    def test_fallback_identity_includes_source_and_distinct_uuids_are_preserved(self):
        base = row("step_count", "2026-10-03T08:00:00+08:00", "2026-10-03T09:00:00+08:00", "10", uuid="")
        first = sync.normalize(base)
        duplicate = sync.normalize(dict(base))
        different_source = sync.normalize(dict(base, source="Watch"))
        duplicate_with_uuid_a = sync.normalize(dict(base, uuid="a"))
        duplicate_with_uuid_b = sync.normalize(dict(base, uuid="b"))
        result = sync.deduplicate([
            first,
            duplicate,
            different_source,
            duplicate_with_uuid_a,
            duplicate_with_uuid_b,
        ])
        self.assertEqual(len(result["candidates"]), 4)

    def test_local_start_date_and_aware_instant_sort_produce_exact_schema(self):
        later_instant = sync.normalize(row(
            "heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "80", uuid="later"
        ))
        earlier_instant = sync.normalize(row(
            "heart_rate", "2026-10-03T07:00:00+08:00", "2026-10-03T07:00:01+08:00", "70", uuid="earlier"
        ))
        another_local_date = sync.normalize(row(
            "step_count", "2026-10-02T23:30:00-04:00", "2026-10-03T00:00:00-04:00", "5", uuid="steps"
        ))
        days = sync.split_by_day([later_instant, earlier_instant, another_local_date])
        self.assertIn("2026-10-02", days)
        self.assertIn("2026-10-03", days)
        output = json.loads(sync.build_daily_json("2026-10-03", [later_instant, earlier_instant]))
        self.assertEqual(list(output), ["heartRate", "steps", "sleep"])
        self.assertEqual(output["heartRate"], [
            {"time": "2026-10-03T07:00:00+08:00", "bpm": 70.0},
            {"time": "2026-10-03T08:00:00+08:00", "bpm": 80.0},
        ])
        self.assertEqual(output["steps"], [])
        self.assertEqual(output["sleep"], [])
        self.assertEqual(set(output["heartRate"][0]), {"time", "bpm"})

    def test_empty_day_has_exact_three_arrays(self):
        self.assertEqual(
            json.loads(sync.build_daily_json("2026-10-03", [])),
            {"heartRate": [], "steps": [], "sleep": []},
        )


class StateAndAtomicWriteTests(unittest.TestCase):
    def test_restart_round_trip_and_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = Path(temp) / "state.json"
            samples = [sync.normalize(row(
                "heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "70.5"
            ))]
            state = sync._state_from_samples(samples)
            sync.atomic_write(state_path, sync._state_bytes(state))
            loaded = sync.load_state(state_path)
            self.assertEqual(sync._flatten_state(loaded), sync._flatten_state(state))
            state_path.write_text('{"version": 1, "samples": {"wrong": {}}}', encoding="utf-8")
            with self.assertRaises(sync.StateCorruptionError):
                sync.load_state(state_path)

    def test_state_rejects_key_mismatch_and_nonfinite_numbers(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = Path(temp) / "state.json"
            sample = sync.normalize(row(
                "heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "70.5"
            ))
            valid = sync._state_from_samples([sample])
            identity = next(iter(valid["samples"]))
            variant = next(iter(valid["samples"][identity]))
            wrong_key = {"version": 1, "samples": {"wrong": {variant: sample}}}
            state_path.write_text(json.dumps(wrong_key), encoding="utf-8")
            with self.assertRaises(sync.StateCorruptionError):
                sync.load_state(state_path)

            encoded = json.dumps(valid)
            encoded = encoded.replace('"value": 70.5', '"value": NaN')
            state_path.write_text(encoded, encoding="utf-8")
            with self.assertRaises(sync.StateCorruptionError):
                sync.load_state(state_path)

    def test_atomic_write_skips_identical_bytes_and_preserves_old_file_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "health.json"
            self.assertTrue(sync.atomic_write(target, b"first"))
            with mock.patch.object(sync.os, "replace") as replace:
                self.assertFalse(sync.atomic_write(target, b"first"))
                replace.assert_not_called()
            with mock.patch.object(sync.os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    sync.atomic_write(target, b"second")
            self.assertEqual(target.read_bytes(), b"first")
            self.assertEqual(list(Path(temp).glob("*.tmp")), [])

    def test_state_commit_precedes_output_and_startup_recovers_conflict_days(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "conflicts.csv"
            output_dir = root / "daily"
            state_path = root / "state.json"
            write_csv(input_path, [
                row("heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "70", uuid="bad"),
                row("heart_rate", "2026-10-04T08:00:00+08:00", "2026-10-04T08:00:01+08:00", "71", uuid="BAD"),
            ])
            real_atomic_write = sync.atomic_write

            def fail_daily(path, content):
                if Path(path).parent == output_dir:
                    raise OSError("simulated output failure")
                return real_atomic_write(path, content)

            with mock.patch.object(sync, "atomic_write", side_effect=fail_daily):
                with self.assertRaises(OSError):
                    sync.process_csv_file(input_path, output_dir, state_path)
            self.assertTrue(state_path.exists())
            persisted = sync._flatten_state(sync.load_state(state_path))
            self.assertEqual(len(persisted), 2)
            sync._refresh_outputs(output_dir, persisted)
            for day in ("26-10-03", "26-10-04"):
                content = json.loads((output_dir / ("health_{}.json".format(day))).read_text(encoding="utf-8"))
                self.assertEqual(content, {"heartRate": [], "steps": [], "sleep": []})


class WatcherTests(unittest.TestCase):
    def test_real_watchdog_queues_startup_csv_and_moved_in_csv(self):
        import watchdog  # noqa: F401

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            watched = root / "watched"
            elsewhere = root / "elsewhere"
            watched.mkdir()
            elsewhere.mkdir()
            existing = watched / "startup.csv"
            existing.write_text("ready", encoding="utf-8")
            seen = []
            event = threading.Event()

            def enqueue(path):
                seen.append(Path(path).name)
                event.set()

            observer = sync.watcher(watched, enqueue)
            try:
                self.assertTrue(event.wait(1.0))
                self.assertIn("startup.csv", seen)
                event.clear()
                moved = elsewhere / "moved.csv"
                moved.write_text("ready", encoding="utf-8")
                os.replace(moved, watched / "moved.csv")
                self.assertTrue(event.wait(2.0))
                deadline = time.monotonic() + 2.0
                while "moved.csv" not in seen and time.monotonic() < deadline:
                    event.wait(0.05)
                self.assertIn("moved.csv", seen)
            finally:
                observer.stop()
                observer.join()

    def test_real_watchdog_slow_write_during_processing_causes_worker_rerun(self):
        import watchdog  # noqa: F401

        with tempfile.TemporaryDirectory() as temp:
            watched = Path(temp) / "watched"
            watched.mkdir()
            entered = threading.Event()
            release_first = threading.Event()
            changed_event = threading.Event()
            calls = []
            observed_contents = []
            worker = None

            def processor(path):
                calls.append(path.name)
                if len(calls) == 1:
                    entered.set()
                    release_first.wait(2.0)
                observed_contents.append(path.read_text(encoding="utf-8"))

            worker = sync.CSVWorker(
                processor,
                stable_seconds=0.03,
                sample_interval=0.01,
                stable_timeout=1.0,
                retry_delay=0.02,
            )
            worker.start()

            def enqueue(path):
                worker.enqueue(path)
                if Path(path).name == "slow.csv":
                    changed_event.set()

            observer = sync.watcher(watched, enqueue)
            try:
                target = watched / "slow.csv"
                target.write_text("first", encoding="utf-8")
                self.assertTrue(entered.wait(2.0))
                changed_event.clear()
                with target.open("a", encoding="utf-8") as handle:
                    handle.write("-second")
                    handle.flush()
                    os.fsync(handle.fileno())
                self.assertTrue(changed_event.wait(2.0))
                release_first.set()
                deadline = time.monotonic() + 3.0
                while len(calls) < 2 and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertGreaterEqual(len(calls), 2)
                self.assertIn("first-second", observed_contents[-1])
            finally:
                release_first.set()
                observer.stop()
                observer.join()
                worker.stop(timeout=2.0)

    def test_real_observer_worker_processes_created_moved_overlapping_csvs(self):
        import watchdog  # noqa: F401

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            staging = root / "staging"
            output_dir = root / "daily"
            state_file = root / "state.json"
            input_dir.mkdir()
            staging.mkdir()
            completed = {}
            completed_lock = threading.Lock()

            def process(path):
                sync.process_csv_file(path, output_dir, state_file)
                with completed_lock:
                    completed[path.name] = completed.get(path.name, 0) + 1

            worker = sync.CSVWorker(
                process,
                stable_seconds=0.04,
                sample_interval=0.01,
                stable_timeout=1.0,
                retry_delay=0.03,
            )
            worker.start()
            observer = sync.watcher(input_dir, worker.enqueue)

            def processed(name, minimum=1):
                return eventually(lambda: completed.get(name, 0) >= minimum)

            try:
                first_rows = [
                    row("heart_rate", "2026-10-03T09:00:00+08:00", "2026-10-03T09:00:01+08:00", "90", uuid="hr-3"),
                    row("step_count", "2026-10-02T23:30:00-04:00", "2026-10-03T00:00:00-04:00", "12", uuid="step-1"),
                    row("heart_rate", "2026-10-03T07:00:00+08:00", "2026-10-03T07:00:01+08:00", "70", uuid="hr-1"),
                ]
                first_path = input_dir / "first.csv"
                write_csv(first_path, first_rows)
                self.assertTrue(processed("first.csv"))
                day_three = output_dir / "health_26-10-03.json"
                day_two = output_dir / "health_26-10-02.json"
                self.assertTrue(day_three.exists())
                self.assertTrue(day_two.exists())

                second_rows = [
                    row("heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "80", uuid="hr-2"),
                    row("heart_rate", "2026-10-03T07:00:00+08:00", "2026-10-03T07:00:01+08:00", "70", uuid="HR-1", source="Watch"),
                    row("unhandled_metric", "", "", "not-a-number", uuid="ignored"),
                ]
                second_path = input_dir / "second.csv"
                write_csv(second_path, second_rows)
                self.assertTrue(processed("second.csv"))
                output = json.loads(day_three.read_text(encoding="utf-8"))
                self.assertEqual(output["heartRate"], [
                    {"time": "2026-10-03T07:00:00+08:00", "bpm": 70.0},
                    {"time": "2026-10-03T08:00:00+08:00", "bpm": 80.0},
                    {"time": "2026-10-03T09:00:00+08:00", "bpm": 90.0},
                ])
                self.assertEqual(json.loads(day_two.read_text(encoding="utf-8"))["steps"], [
                    {
                        "start": "2026-10-02T23:30:00-04:00",
                        "end": "2026-10-03T00:00:00-04:00",
                        "count": 12,
                    }
                ])

                before_bytes = day_three.read_bytes()
                before_mtime = day_three.stat().st_mtime_ns
                worker.enqueue(first_path)
                worker.enqueue(first_path)
                self.assertTrue(processed("first.csv", 2))
                self.assertEqual(day_three.read_bytes(), before_bytes)
                self.assertEqual(day_three.stat().st_mtime_ns, before_mtime)

                moved_path = staging / "moved.csv"
                write_csv(moved_path, [
                    row("sleep_analysis", "2026-10-02T22:00:00+08:00", "2026-10-03T06:00:00+08:00", "4", uuid="sleep-1"),
                    row("unhandled_metric", "", "", "NaN", uuid="ignored-2"),
                ])
                os.replace(moved_path, input_dir / "moved.csv")
                self.assertTrue(processed("moved.csv"))
                self.assertEqual(json.loads(day_two.read_text(encoding="utf-8"))["sleep"], [
                    {
                        "start": "2026-10-02T22:00:00+08:00",
                        "end": "2026-10-03T06:00:00+08:00",
                        "stage": "deep",
                    }
                ])
            finally:
                observer.stop()
                observer.join()
                worker.stop(timeout=None)


class CLIIntegrationTests(unittest.TestCase):
    def test_long_running_cli_is_disabled_but_once_diagnostic_remains_available(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            output_dir = root / "daily"
            state_file = root / "internal" / "state.json"
            input_dir.mkdir()
            write_csv(input_dir / "export.csv", [row(
                "heart_rate",
                "2026-10-03T08:00:00+08:00",
                "2026-10-03T08:00:01+08:00",
                "72",
            )])
            arguments = [
                "--input-dir", str(input_dir),
                "--output-dir", str(output_dir),
                "--state-file", str(state_file),
                "--stable-seconds", "0",
                "--sample-interval", "0.01",
                "--stable-timeout", "0.5",
            ]

            with mock.patch.object(sync, "watcher") as watch:
                self.assertEqual(sync.main(arguments), 2)
                watch.assert_not_called()
            self.assertFalse(state_file.exists())

            self.assertEqual(sync.main(arguments + ["--once"]), 0)
            self.assertTrue((output_dir / "health_26-10-03.json").is_file())

    def test_three_csv_permutations_produce_identical_state_and_daily_bytes(self):
        csv_rows = [
            [
                row("heart_rate", "2026-10-03T07:00:00+08:00", "2026-10-03T07:00:01+08:00", "70", uuid="shared", source="Phone"),
                row("step_count", "2026-10-03T06:00:00+08:00", "2026-10-03T07:00:00+08:00", "10", uuid=""),
            ],
            [
                row("heart_rate", "2026-10-03T07:00:00+08:00", "2026-10-03T07:00:01+08:00", "70", uuid="SHARED", source="Watch"),
                row("heart_rate", "2026-10-03T09:00:00+08:00", "2026-10-03T09:00:01+08:00", "90", uuid="late"),
                row("step_count", "2026-10-03T06:00:00+08:00", "2026-10-03T07:00:00+08:00", "10", uuid=""),
            ],
            [
                row("heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "80", uuid="middle"),
                row("sleep_analysis", "2026-10-02T22:00:00+08:00", "2026-10-03T06:00:00+08:00", "3", uuid="sleep"),
            ],
        ]
        final_snapshots = []
        for permutation in itertools.permutations(range(3)):
            with self.subTest(permutation=permutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                input_dir = root / "input"
                output_dir = root / "daily"
                state_file = root / "state.json"
                input_dir.mkdir()
                paths = []
                for index, values in enumerate(csv_rows):
                    path = input_dir / "{}.csv".format(index)
                    write_csv(path, values)
                    paths.append(path)
                for index in permutation:
                    sync.process_csv_file(paths[index], output_dir, state_file)
                final_snapshots.append((
                    state_file.read_bytes(),
                    {path.name: path.read_bytes() for path in sorted(output_dir.iterdir())},
                ))
        self.assertTrue(all(snapshot == final_snapshots[0] for snapshot in final_snapshots[1:]))
        daily = json.loads(final_snapshots[0][1]["health_26-10-03.json"])
        self.assertEqual([item["bpm"] for item in daily["heartRate"]], [70.0, 80.0, 90.0])

    def test_invalid_csv_is_all_or_nothing_and_stat_change_aborts_before_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            output_dir = root / "daily"
            state_file = root / "state.json"
            input_dir.mkdir()
            baseline = input_dir / "baseline.csv"
            write_csv(baseline, [row(
                "heart_rate", "2026-10-03T08:00:00+08:00", "2026-10-03T08:00:01+08:00", "70", uuid="base"
            )])
            sync.process_csv_file(baseline, output_dir, state_file)
            before_state = state_file.read_bytes()
            before_files = {
                path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                for path in output_dir.iterdir()
            }

            invalid = input_dir / "invalid.csv"
            write_csv(invalid, [
                row("heart_rate", "2026-10-04T08:00:00+08:00", "2026-10-04T08:00:01+08:00", "80", uuid="would-add"),
                row("step_count", "2026-10-04T08:00:00+08:00", "2026-10-04T09:00:00+08:00", "1.25", uuid="bad"),
            ])
            with self.assertRaises(sync.CSVValidationError):
                sync.process_csv_file(invalid, output_dir, state_file)
            self.assertEqual(state_file.read_bytes(), before_state)
            self.assertEqual(
                {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in output_dir.iterdir()},
                before_files,
            )

            changing = input_dir / "changing.csv"
            write_csv(changing, [row(
                "heart_rate", "2026-10-05T08:00:00+08:00", "2026-10-05T08:00:01+08:00", "85", uuid="changed"
            )])
            real_normalize = sync.normalize

            def mutate_after_normalize(*args, **kwargs):
                sample = real_normalize(*args, **kwargs)
                with changing.open("a", encoding="utf-8") as handle:
                    handle.write("\n")
                return sample

            with mock.patch.object(sync, "normalize", side_effect=mutate_after_normalize):
                with self.assertRaises(sync.DeferredInputError):
                    sync.process_csv_file(changing, output_dir, state_file)
            self.assertEqual(state_file.read_bytes(), before_state)
            self.assertNotIn("health_26-10-05.json", {path.name for path in output_dir.iterdir()})

    def test_worker_retries_transient_write_error_and_remains_alive(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "retry.csv"
            path.write_text("ready", encoding="utf-8")
            calls = []
            succeeded = threading.Event()

            def processor(candidate):
                calls.append(candidate)
                if len(calls) == 1:
                    raise OSError("temporary output failure")
                succeeded.set()

            worker = sync.CSVWorker(
                processor,
                stable_seconds=0.02,
                sample_interval=0.01,
                stable_timeout=0.5,
                retry_delay=0.02,
            )
            worker.start()
            try:
                worker.enqueue(path)
                self.assertTrue(succeeded.wait(2.0))
                self.assertEqual(len(calls), 2)
            finally:
                worker.stop(timeout=None)

    def test_worker_defers_a_timed_out_write_until_file_becomes_stable(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "slow.csv"
            path.write_text("start", encoding="utf-8")
            succeeded = threading.Event()
            worker = sync.CSVWorker(
                lambda candidate: succeeded.set(),
                stable_seconds=0.04,
                sample_interval=0.01,
                stable_timeout=0.07,
                retry_delay=0.02,
            )
            worker.start()
            try:
                worker.enqueue(path)
                def keep_writing():
                    for index in range(8):
                        with path.open("a", encoding="utf-8") as handle:
                            handle.write("-chunk-{}".format(index))
                            handle.flush()
                        time.sleep(0.02)

                writer = threading.Thread(target=keep_writing)
                writer.start()
                self.assertTrue(succeeded.wait(2.0))
                writer.join()
            finally:
                worker.stop(timeout=None)


if __name__ == "__main__":
    unittest.main()
