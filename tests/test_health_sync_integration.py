import csv
from datetime import datetime, timedelta
import importlib
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "LyubishchevSync"
SRC = PROJECT / "src"
for path in (str(SRC), str(PROJECT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from dailynotes.health_sync import HealthSyncService, _load_health_module  # noqa: E402
from dailynotes.sync_pause import SyncPauseController  # noqa: E402
import main as main_module  # noqa: E402


health = _load_health_module()


def eventually(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def health_row(metric, day, value, uuid):
    return {
        "uuid": uuid,
        "metric": metric,
        "start": "{}T08:00:00+08:00".format(day),
        "end": "{}T08:00:01+08:00".format(day),
        "value": str(value),
        "unit": "",
        "min": "",
        "max": "",
        "avg": "",
        "source": "Phone",
        "source_bundle_id": "com.example.health",
        "aggregation": "",
        "metadata": "",
        "details": "",
    }


def write_health_csv(path, day, value="72", uuid="sample"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=health.CSV_HEADERS)
        writer.writeheader()
        writer.writerow(health_row("heart_rate", day, value, uuid))
    return path


class HealthSyncServiceTests(unittest.TestCase):
    def make_service(self, root, pause_controller=None):
        root = Path(root)
        input_dir = root / "health-input"
        output_dir = root / "daily-output"
        state_file = root / "state" / "health.json"
        input_dir.mkdir(parents=True, exist_ok=True)
        service = HealthSyncService(
            pause_controller=pause_controller or SyncPauseController(),
            health_module=health,
            input_dir=input_dir,
            output_dir=output_dir,
            state_file=state_file,
            stable_seconds=0.02,
            sample_interval=0.01,
            stable_timeout=0.5,
            retry_delay=0.02,
        )
        return service, input_dir, output_dir, state_file

    def test_service_owns_one_worker_and_releases_state_lock_on_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            service, input_dir, output_dir, state_file = self.make_service(directory)
            self.addCleanup(service.stop)
            csv_path = write_health_csv(input_dir / "export.csv", "2026-10-03")

            self.assertTrue(service.start())
            worker = service._worker
            observer = service._observer
            self.assertTrue(service.start())
            self.assertIs(service._worker, worker)
            self.assertIs(service._observer, observer)
            self.assertTrue(eventually(lambda: service.snapshot()["last_successful_time"] is not None))
            self.assertTrue(eventually(lambda: service.snapshot()["status"] == "idle" and service.snapshot()["queued_count"] == 0))

            snapshot = service.snapshot()
            self.assertEqual(snapshot["status"], "idle")
            self.assertEqual(snapshot["last_affected_date"], "2026-10-03")
            self.assertEqual(Path(snapshot["last_csv"]).name, csv_path.name)
            self.assertTrue((output_dir / "health_26-10-03.json").is_file())

            service.stop()
            self.assertFalse(worker._thread.is_alive())
            self.assertEqual(service.snapshot()["status"], "stopped")
            with health.state_lock(state_file):
                pass

    def test_startup_imports_all_exports_and_retains_latest_per_export_day(self):
        with tempfile.TemporaryDirectory() as directory:
            service, input_dir, output_dir, state_file = self.make_service(directory)
            self.addCleanup(service.stop)
            older = write_health_csv(
                input_dir / "SyncFit_20261009_080000_20261009_090000.csv",
                "2026-10-09",
                uuid="historical",
            )
            newest_same_day = write_health_csv(
                input_dir / "SyncFit_20261009_090000_20261009_100000.csv",
                "2026-10-10",
                uuid="current",
            )
            other_day = write_health_csv(
                input_dir / "SyncFit_20261010_090000_20261010_100000.csv",
                "2026-10-10",
                uuid="other-day",
            )
            # Deliberately reverse filesystem time: audited export end time wins.
            os.utime(older, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
            os.utime(newest_same_day, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
            os.utime(other_day, ns=(1_500_000_000_000_000_000, 1_500_000_000_000_000_000))

            self.assertTrue(service.start())
            expected_names = sorted((newest_same_day.name, other_day.name))
            self.assertTrue(eventually(lambda: sorted(p.name for p in input_dir.glob("*.csv")) == expected_names))
            self.assertTrue(eventually(
                lambda: service.snapshot()["status"] == "idle"
                and service.snapshot()["queued_count"] == 0
                and Path(service.snapshot()["last_csv"] or ".").name == other_day.name
            ))

            state = health.load_state(state_file)
            samples = health._flatten_state(state)
            self.assertEqual({sample["uuid"] for sample in samples}, {"historical", "current", "other-day"})
            self.assertTrue((output_dir / "health_26-10-09.json").is_file())
            self.assertTrue((output_dir / "health_26-10-10.json").is_file())

            state_before = state_file.read_bytes()
            output_before = (output_dir / "health_26-10-10.json").read_bytes()
            service._process_csv(newest_same_day)
            self.assertEqual(state_file.read_bytes(), state_before)
            self.assertEqual((output_dir / "health_26-10-10.json").read_bytes(), output_before)
            self.assertEqual(sorted(path.name for path in input_dir.iterdir()), expected_names)
            self.assertFalse(any(path.name.endswith((".bak", ".backup")) for path in input_dir.iterdir()))

    def test_generic_exports_use_mtime_and_late_events_for_removed_csv_are_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            service, input_dir, _output_dir, _state_file = self.make_service(directory)
            self.addCleanup(service.stop)
            older = write_health_csv(input_dir / "a.csv", "2026-10-08", uuid="a")
            newest = write_health_csv(input_dir / "b.csv", "2026-10-09", uuid="b")
            other_day = write_health_csv(input_dir / "c.csv", "2026-10-09", uuid="c")
            local_midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
            old_mtime_ns = int(local_midnight.replace(hour=9).timestamp() * 1_000_000_000)
            new_mtime_ns = int(local_midnight.replace(hour=10).timestamp() * 1_000_000_000)
            other_day_mtime_ns = int(
                (local_midnight + timedelta(days=1)).replace(hour=9).timestamp() * 1_000_000_000
            )
            os.utime(older, ns=(old_mtime_ns, old_mtime_ns))
            os.utime(newest, ns=(new_mtime_ns, new_mtime_ns))
            os.utime(other_day, ns=(other_day_mtime_ns, other_day_mtime_ns))

            self.assertTrue(service.start())
            self.assertTrue(eventually(lambda: sorted(p.name for p in input_dir.glob("*.csv")) == ["b.csv", "c.csv"]))
            self.assertTrue(eventually(
                lambda: service.snapshot()["status"] == "idle" and service.snapshot()["queued_count"] == 0
            ))
            service._enqueue_csv(older)
            self.assertEqual(service.snapshot()["queued_count"], 0)
            self.assertTrue(newest.is_file())
            self.assertTrue(other_day.is_file(), "different local mtime day remains")
            samples = health._flatten_state(health.load_state(service.state_file))
            self.assertEqual({sample["uuid"] for sample in samples}, {"a", "b", "c"})
            outside = write_health_csv(Path(directory) / "outside.csv", "2026-10-10", uuid="outside")
            service._enqueue_csv(outside)
            self.assertEqual(service.snapshot()["queued_count"], 0)

    def test_failed_newest_and_output_write_failure_never_delete_pending_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            service, input_dir, _output_dir, _state_file = self.make_service(directory)
            older = write_health_csv(input_dir / "01.csv", "2026-10-07", uuid="older")
            newest = write_health_csv(input_dir / "02.csv", "2026-10-08", "not-a-number", "bad")

            service._process_csv(older)
            self.assertTrue(older.exists())
            self.assertTrue(newest.exists(), "an unimported newer file blocks retention")
            with self.assertRaises(health.CSVValidationError):
                service._process_csv(newest)
            self.assertTrue(older.exists())
            self.assertTrue(newest.exists(), "a failed newest file must not be deleted")

            # A state commit followed by a daily-output failure also must not
            # mark the CSV as imported or trigger retention.
            with mock.patch.object(health, "_refresh_outputs", side_effect=OSError("daily output write failed")):
                with self.assertRaisesRegex(OSError, "daily output write failed"):
                    service._process_csv(older)
            self.assertTrue(older.exists())
            self.assertTrue(newest.exists())

    def test_retention_unlink_failure_is_reported_and_does_not_claim_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            service, input_dir, _output_dir, _state_file = self.make_service(directory)
            self.addCleanup(service.stop)
            older = write_health_csv(input_dir / "01.csv", "2026-10-06", uuid="older")
            newest = write_health_csv(input_dir / "02.csv", "2026-10-07", uuid="newest")
            original_unlink = Path.unlink

            def fail_for_older(path, *args, **kwargs):
                if path.name == older.name and path.parent.resolve() == older.parent.resolve():
                    raise PermissionError("simulated retention denial")
                return original_unlink(path, *args, **kwargs)

            with mock.patch.object(Path, "unlink", new=fail_for_older):
                self.assertTrue(service.start())
                self.assertTrue(eventually(
                    lambda: "could not remove older Health CSV" in (service.snapshot()["error_detail"] or "")
                ))
                self.assertTrue(older.exists())
                self.assertTrue(newest.exists())
                self.assertIn("simulated retention denial", service.snapshot()["error_detail"])

    def test_changed_and_new_files_cancel_cleanup_until_all_versions_succeed(self):
        with tempfile.TemporaryDirectory() as directory:
            service, input_dir, _output_dir, _state_file = self.make_service(directory)
            first = write_health_csv(input_dir / "01.csv", "2026-10-04", uuid="first")
            second = write_health_csv(input_dir / "02.csv", "2026-10-05", uuid="second")

            service._process_csv(first)
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

            original_process = health.process_csv_file

            def process_then_replace(path, output_dir, state_file):
                result = original_process(path, output_dir, state_file)
                write_health_csv(first, "2026-10-04", "74", "first-replaced")
                return result

            with mock.patch.object(health, "process_csv_file", side_effect=process_then_replace):
                service._process_csv(second)
            self.assertTrue(first.exists(), "a replaced input version blocks cleanup")
            self.assertTrue(second.exists())

            third = write_health_csv(input_dir / "03.csv", "2026-10-06", uuid="third")
            service._process_csv(first)
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertTrue(third.exists(), "a newly arrived export blocks cleanup until imported")

            service._process_csv(third)
            self.assertEqual([path.name for path in input_dir.glob("*.csv")], ["03.csv"])
            samples = health._flatten_state(health.load_state(service.state_file))
            self.assertTrue({"first", "first-replaced", "second", "third"}.issubset(
                {sample["uuid"] for sample in samples}
            ))

    def test_pending_failed_export_day_does_not_block_another_days_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            service, input_dir, _output_dir, _state_file = self.make_service(directory)
            day_a_old = write_health_csv(
                input_dir / "SyncFit_20261008_080000_20261008_090000.csv",
                "2026-10-08",
                uuid="a-old",
            )
            day_a_failed = write_health_csv(
                input_dir / "SyncFit_20261008_090000_20261008_100000.csv",
                "2026-10-08",
                "bad",
                "a-failed",
            )
            day_b_old = write_health_csv(
                input_dir / "SyncFit_20261009_080000_20261009_090000.csv",
                "2026-10-09",
                uuid="b-old",
            )
            day_b_new = write_health_csv(
                input_dir / "SyncFit_20261009_090000_20261009_100000.csv",
                "2026-10-09",
                uuid="b-new",
            )

            service._process_csv(day_a_old)
            self.assertTrue(day_a_old.exists())
            self.assertTrue(day_a_failed.exists(), "pending same-day file blocks only day A")

            service._process_csv(day_b_old)
            self.assertTrue(day_b_old.exists())
            self.assertTrue(day_b_new.exists(), "pending same-day file blocks day B until processed")
            service._process_csv(day_b_new)
            self.assertFalse(day_b_old.exists(), "successful day B cleanup proceeds while day A is pending")
            self.assertTrue(day_b_new.exists())
            self.assertTrue(day_a_old.exists())
            self.assertTrue(day_a_failed.exists())

            with self.assertRaises(health.CSVValidationError):
                service._process_csv(day_a_failed)
            self.assertTrue(day_a_old.exists())
            self.assertTrue(day_a_failed.exists(), "failed day A export must remain")

    def test_cleanup_ignores_symlinks_and_nested_csvs_without_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            service, input_dir, _output_dir, _state_file = self.make_service(directory)
            self.addCleanup(service.stop)
            older = write_health_csv(input_dir / "01.csv", "2026-10-02", uuid="direct-old")
            newest = write_health_csv(input_dir / "02.csv", "2026-10-03", uuid="direct-new")
            nested = write_health_csv(input_dir / "nested" / "nested.csv", "2026-10-04", uuid="nested")
            linked_target = write_health_csv(Path(directory) / "linked-target.csv", "2026-10-05", uuid="linked")
            symlink = input_dir / "linked.csv"
            try:
                symlink.symlink_to(linked_target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable in this environment")

            self.assertTrue(service.start())
            self.assertTrue(eventually(lambda: sorted(p.name for p in input_dir.glob("*.csv")) == ["02.csv", "linked.csv"]))
            self.assertTrue(eventually(lambda: service.snapshot()["queued_count"] == 0))
            samples = health._flatten_state(health.load_state(service.state_file))
            self.assertEqual({sample["uuid"] for sample in samples}, {"direct-old", "direct-new"})
            self.assertFalse(older.exists())
            self.assertTrue(newest.exists())
            self.assertTrue(nested.exists())
            self.assertTrue(symlink.is_symlink())
            self.assertTrue(linked_target.exists())
            service._enqueue_csv(nested)
            service._enqueue_csv(linked_target)
            self.assertEqual(service.snapshot()["queued_count"], 0)
            self.assertFalse(any(path.name.endswith((".bak", ".backup")) for path in input_dir.rglob("*")))

    def test_startup_rebuild_waits_for_resume_and_shutdown_cancels_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            pause = SyncPauseController()
            service, input_dir, output_dir, state_file = self.make_service(directory, pause)
            self.addCleanup(service.stop)
            sample = health.normalize(health_row("heart_rate", "2026-10-03", "72", "baseline"))
            state_file.parent.mkdir(parents=True)
            state_file.write_bytes(health._state_bytes(health._state_from_samples([sample])))
            pause.pause()

            result = []
            start_thread = threading.Thread(target=lambda: result.append(service.start()), daemon=True)
            start_thread.start()
            self.assertTrue(eventually(lambda: state_file.with_name(state_file.name + ".lock").exists()))
            self.assertTrue(start_thread.is_alive())
            self.assertFalse(output_dir.exists())

            service.request_stop()
            start_thread.join(1.0)
            self.assertFalse(start_thread.is_alive(), "stop while paused must release startup")
            self.assertEqual(result, [False])
            self.assertFalse(output_dir.exists(), "paused recovery must not write daily outputs")
            service.stop()
            with health.state_lock(state_file):
                pass

    def test_paused_worker_queues_changes_and_processes_after_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            pause = SyncPauseController()
            service, input_dir, output_dir, state_file = self.make_service(directory, pause)
            self.addCleanup(service.stop)
            self.assertTrue(service.start())
            pause.pause()

            first = write_health_csv(input_dir / "01.csv", "2026-10-04", "71", "first")
            self.assertTrue(eventually(lambda: Path(service.snapshot()["current_file"] or ".").name == first.name))
            write_health_csv(input_dir / "02.csv", "2026-10-05", "73", "second")
            self.assertTrue(eventually(lambda: service.snapshot()["queued_count"] == 1))
            self.assertEqual(service.snapshot()["status"], "paused")
            self.assertFalse(state_file.exists())

            pause.resume()
            self.assertTrue(eventually(lambda: service.snapshot()["last_affected_date"] == "2026-10-05"))
            self.assertTrue((output_dir / "health_26-10-04.json").is_file())
            self.assertTrue((output_dir / "health_26-10-05.json").is_file())
            self.assertEqual(service.snapshot()["queued_count"], 0)
            service.stop()

    def test_stop_while_worker_is_paused_does_not_write_or_deadlock(self):
        with tempfile.TemporaryDirectory() as directory:
            pause = SyncPauseController()
            service, input_dir, output_dir, state_file = self.make_service(directory, pause)
            self.addCleanup(service.stop)
            self.assertTrue(service.start())
            pause.pause()
            csv_path = write_health_csv(input_dir / "pending.csv", "2026-10-06")
            self.assertTrue(eventually(lambda: Path(service.snapshot()["current_file"] or ".").name == csv_path.name))

            stopped = threading.Event()
            stopper = threading.Thread(target=lambda: (service.stop(), stopped.set()), daemon=True)
            stopper.start()
            self.assertTrue(stopped.wait(2.0), "worker stop should cancel its paused gate")
            stopper.join(0.5)
            self.assertFalse(state_file.exists())
            self.assertFalse(output_dir.exists() and any(output_dir.iterdir()))
            with health.state_lock(state_file):
                pass

    def test_corrupt_state_is_reported_and_lock_is_released(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _input_dir, output_dir, state_file = self.make_service(directory)
            state_file.parent.mkdir(parents=True)
            state_file.write_text("{broken", encoding="utf-8")

            self.assertFalse(service.start())
            snapshot = service.snapshot()
            self.assertEqual(snapshot["status"], "error")
            self.assertIn("StateCorruptionError", snapshot["error_detail"])
            self.assertFalse(output_dir.exists())
            with health.state_lock(state_file):
                pass
            service.stop()

    def test_invalid_csv_error_recovers_after_file_is_corrected(self):
        with tempfile.TemporaryDirectory() as directory:
            service, input_dir, output_dir, _state_file = self.make_service(directory)
            self.addCleanup(service.stop)
            self.assertTrue(service.start())
            invalid = write_health_csv(input_dir / "fixable.csv", "2026-10-07", "not-a-number")
            self.assertTrue(eventually(lambda: service.snapshot()["status"] == "error"))
            self.assertIn("value", service.snapshot()["error_detail"])

            write_health_csv(invalid, "2026-10-07", "74", "fixed")
            self.assertTrue(eventually(lambda: service.snapshot()["last_successful_time"] is not None))
            self.assertTrue(eventually(lambda: service.snapshot()["status"] == "idle"))
            self.assertIsNone(service.snapshot()["error_detail"])
            self.assertTrue((output_dir / "health_26-10-07.json").is_file())


class _FakeMenuItem:
    def __init__(self, title, callback=None):
        self._title = title
        self.callback = callback
        self.write_threads = []

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self.write_threads.append(threading.get_ident())
        self._title = value


class _FakeTimer:
    instances = []

    def __init__(self, callback, interval):
        self.callback = callback
        self.interval = interval
        self.running = False
        self.__class__.instances.append(self)

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def fire(self):
        self.callback(self)


class _FakeApp:
    def __init__(self, name, title=None):
        self.name = name
        self.title = title
        self.menu = []


class HealthMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_rumps = types.SimpleNamespace(
            App=_FakeApp,
            MenuItem=_FakeMenuItem,
            Timer=_FakeTimer,
            clicked=lambda _name: lambda function: function,
            notification=lambda *args, **kwargs: None,
            quit_application=lambda: None,
        )
        with mock.patch.dict(sys.modules, {"rumps": fake_rumps}):
            cls.gui = importlib.import_module("gui_main")

    def test_timer_updates_full_health_rows_on_ui_thread_without_overriding_main_status(self):
        _FakeTimer.instances.clear()
        app = self.gui.LyubishchevApp()
        original_pause_file = os.environ.get("LYUBISHCHEV_SYNC_PAUSE_FILE")
        try:
            app.set_status("idle", force=True)
            app._start_health_refresh()
            timer = app._health_timer
            self.assertIsInstance(timer, _FakeTimer)
            self.assertEqual(timer.interval, 1.0)
            self.assertTrue(timer.running)

            snapshot = {
                "status": "processing",
                "queued_count": 2,
                "current_file": "/tmp/health/large-export.csv",
                "last_successful_time": "2026-10-10T10:00:00+08:00",
                "last_affected_date": "2026-10-09",
                "last_csv": "/tmp/health/previous.csv",
                "error_detail": None,
            }
            with mock.patch.object(self.gui.main, "get_health_status_snapshot", return_value=snapshot):
                timer.fire()
            self.assertEqual(app.health_status_item.title, "健康同步：处理中")
            self.assertEqual(app.health_queue_item.title, "健康 CSV 队列：2")
            self.assertEqual(app.health_current_item.title, "当前健康 CSV：/tmp/health/large-export.csv")
            self.assertIn("影响日期 2026-10-09", app.health_last_success_item.title)
            self.assertEqual(app.health_last_csv_item.title, "健康上次 CSV：/tmp/health/previous.csv")
            self.assertEqual(app.title, "🩺柳比")
            self.assertEqual(app.status_item.title, "Status: Idle")
            self.assertTrue(all(
                thread_id == threading.get_ident()
                for item in (app.health_status_item, app.health_queue_item, app.health_current_item)
                for thread_id in item.write_threads
            ))

            app.set_status("calendar", force=True)
            calendar_title = app.title
            snapshot["status"] = "error"
            snapshot["error_detail"] = "StateCorruptionError: invalid state"
            with mock.patch.object(self.gui.main, "get_health_status_snapshot", return_value=snapshot):
                timer.fire()
            self.assertEqual(app.title, calendar_title)
            self.assertEqual(app.health_error_item.title, "健康错误：StateCorruptionError: invalid state")

            app.set_status("idle", force=True)
            with mock.patch.object(self.gui.main, "get_health_status_snapshot", return_value=snapshot):
                timer.fire()
            self.assertEqual(app.title, "⚠️柳比")

            app.set_status("error", force=True)
            error_title = app.title
            snapshot["status"] = "processing"
            with mock.patch.object(self.gui.main, "get_health_status_snapshot", return_value=snapshot):
                timer.fire()
            self.assertEqual(app.title, error_title)

            app.set_status("paused", force=True)
            paused_title = app.title
            snapshot["status"] = "processing"
            with mock.patch.object(self.gui.main, "get_health_status_snapshot", return_value=snapshot):
                timer.fire()
            self.assertEqual(app.title, paused_title)
        finally:
            app._stop_health_refresh()
            app._pause_directory.cleanup()
            if original_pause_file is None:
                os.environ.pop("LYUBISHCHEV_SYNC_PAUSE_FILE", None)
            else:
                os.environ["LYUBISHCHEV_SYNC_PAUSE_FILE"] = original_pause_file

    def test_restart_waits_for_runtime_cleanup_before_launching_replacement(self):
        app = self.gui.LyubishchevApp()
        original_pause_file = os.environ.get("LYUBISHCHEV_SYNC_PAUSE_FILE")

        class FakeThread:
            alive = True

            def is_alive(self):
                return self.alive

        fake_thread = FakeThread()
        app.sync_thread = fake_thread
        try:
            with mock.patch.object(self.gui.main, "request_shutdown") as request_shutdown, \
                    mock.patch.object(self.gui.rumps, "notification") as notification, \
                    mock.patch.object(self.gui.rumps, "quit_application") as quit_application:
                app._launch_restart = mock.Mock()
                app.restart_sync(None)
                request_shutdown.assert_called_once_with()
                notification.assert_called_once()
                app._exit_timer.fire()
                app._launch_restart.assert_not_called()
                quit_application.assert_not_called()

                fake_thread.alive = False
                app._exit_timer.fire()
                app._launch_restart.assert_called_once_with()
                quit_application.assert_called_once_with()
        finally:
            app._pause_directory.cleanup()
            if original_pause_file is None:
                os.environ.pop("LYUBISHCHEV_SYNC_PAUSE_FILE", None)
            else:
                os.environ["LYUBISHCHEV_SYNC_PAUSE_FILE"] = original_pause_file

    def test_restart_notification_runtime_error_does_not_block_shutdown_or_cleanup(self):
        app = self.gui.LyubishchevApp()
        original_pause_file = os.environ.get("LYUBISHCHEV_SYNC_PAUSE_FILE")

        class FakeThread:
            alive = True

            def is_alive(self):
                return self.alive

        fake_thread = FakeThread()
        app.sync_thread = fake_thread
        try:
            with mock.patch.object(self.gui.main, "request_shutdown") as request_shutdown, \
                    mock.patch.object(
                        self.gui.rumps,
                        "notification",
                        side_effect=RuntimeError("missing Info.plist/CFBundleIdentifier"),
                    ), \
                    mock.patch.object(self.gui.rumps, "quit_application") as quit_application:
                app._launch_restart = mock.Mock()
                app.restart_sync(None)
                request_shutdown.assert_called_once_with()
                self.assertEqual(app._exit_action, "restart")
                self.assertIsNotNone(app._exit_timer)

                app._exit_timer.fire()
                app._launch_restart.assert_not_called()
                quit_application.assert_not_called()

                fake_thread.alive = False
                app._exit_timer.fire()
                app._launch_restart.assert_called_once_with()
                quit_application.assert_called_once_with()
        finally:
            app._pause_directory.cleanup()
            if original_pause_file is None:
                os.environ.pop("LYUBISHCHEV_SYNC_PAUSE_FILE", None)
            else:
                os.environ["LYUBISHCHEV_SYNC_PAUSE_FILE"] = original_pause_file

    def test_missing_log_notification_runtime_error_is_nonfatal(self):
        app = self.gui.LyubishchevApp()
        original_pause_file = os.environ.get("LYUBISHCHEV_SYNC_PAUSE_FILE")
        try:
            with mock.patch.object(self.gui.os.path, "exists", return_value=False), \
                    mock.patch.object(
                        self.gui.rumps,
                        "notification",
                        side_effect=RuntimeError("missing Info.plist/CFBundleIdentifier"),
                    ):
                app.open_log(None)
        finally:
            app._pause_directory.cleanup()
            if original_pause_file is None:
                os.environ.pop("LYUBISHCHEV_SYNC_PAUSE_FILE", None)
            else:
                os.environ["LYUBISHCHEV_SYNC_PAUSE_FILE"] = original_pause_file


class VendoredHealthModuleTests(unittest.TestCase):
    def test_main_process_loads_self_contained_vendored_module_first(self):
        vendored_path = SRC / "external" / "syncfit_health.py"
        self.assertTrue(vendored_path.is_file())
        self.assertEqual(Path(health.__file__).resolve(), vendored_path.resolve())


class MainLifecycleTests(unittest.TestCase):
    def test_health_start_error_does_not_cancel_main_loop_and_services_stop_in_finally(self):
        main = main_module

        events = []

        class FakeHealthService:
            def start(self):
                events.append("health-start")
                return False

            def request_stop(self):
                events.append("health-request-stop")

            def stop(self):
                events.append("health-stop")

            def snapshot(self):
                return {"status": "error", "error_detail": "state is corrupt"}

        class FakeManager:
            app_ref = None

            def __init__(self):
                events.append("manager-created")

            def run(self, register_signals=True):
                events.append(("manager-run", register_signals))

            def request_stop(self):
                events.append("manager-stop")

        original_service = main._health_sync_service
        main._health_sync_service = None
        main._shutdown_requested.clear()
        main.sync_pause._cancel_event.clear()
        try:
            with mock.patch.object(main, "HealthSyncService", FakeHealthService), \
                    mock.patch.object(main, "FusionManager", FakeManager), \
                    mock.patch.object(main, "_start_note_monitor", side_effect=lambda: events.append("notes-start")), \
                    mock.patch.object(main, "_stop_note_monitor", side_effect=lambda: events.append("notes-stop")):
                main.run_with_self_healing()
            self.assertEqual(events[:4], ["health-start", "notes-start", "manager-created", ("manager-run", False)])
            self.assertIn("health-stop", events)
            self.assertIn("notes-stop", events)
        finally:
            main._health_sync_service = original_service
            main._active_manager = None
            main._shutdown_requested.clear()
            main.sync_pause._cancel_event.clear()


if __name__ == "__main__":
    unittest.main()
