"""Embedded SyncFit Health watcher managed by the LyubishchevSync process."""

from __future__ import annotations

import importlib.util
import logging
import os
import re
import stat
import threading
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Optional

from .sync_pause import SyncPauseController, sync_pause
from .utils import Logger


LOGGER = logging.getLogger("dailynotes.health_sync")
_MODULE_NAME = "_lyubishchev_syncfit_health"
_EXPORT_NAME = re.compile(
    r"^SyncFit_(\d{8})_(\d{6})_(\d{8})_(\d{6})\.csv$",
    re.IGNORECASE,
)


def _fingerprint_from_stat(info):
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_size),
        int(info.st_mtime_ns),
        int(info.st_ctime_ns),
    )


def _load_health_module() -> ModuleType:
    """Load the vendored SyncFit Health implementation from this checkout."""
    import sys

    cached = sys.modules.get(_MODULE_NAME)
    if cached is not None:
        return cached

    source_root = Path(__file__).resolve().parents[1]
    project_root = Path(__file__).resolve().parents[4]
    candidates = (
        source_root / "external" / "syncfit_health.py",
        project_root / "SyncFitHealth" / "syncfit_health.py",
    )
    script_path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if script_path is None:
        raise FileNotFoundError(
            "SyncFit Health implementation not found (checked {})".format(
                ", ".join(str(candidate) for candidate in candidates)
            )
        )

    spec = importlib.util.spec_from_file_location(_MODULE_NAME, str(script_path))
    if spec is None or spec.loader is None:
        raise ImportError("cannot load SyncFit Health implementation: {}".format(script_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(_MODULE_NAME, None)
        raise
    return module


class HealthSyncService:
    """Own the Health observer, worker, and state lock for one main-process run."""

    def __init__(
        self,
        *,
        pause_controller: SyncPauseController = sync_pause,
        health_module: Optional[ModuleType] = None,
        input_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        state_file: Optional[Path] = None,
        stable_seconds: float = 5.0,
        sample_interval: float = 1.0,
        stable_timeout: float = 60.0,
        retry_delay: float = 1.0,
    ) -> None:
        self.pause_controller = pause_controller
        self._module = health_module
        self.input_dir = Path(input_dir).expanduser().resolve() if input_dir else None
        self.output_dir = Path(output_dir).expanduser().absolute() if output_dir else None
        self.state_file = Path(state_file).expanduser().absolute() if state_file else None
        self.stable_seconds = stable_seconds
        self.sample_interval = sample_interval
        self.stable_timeout = stable_timeout
        self.retry_delay = retry_delay

        self._lock = threading.RLock()
        self._retention_lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._successful_csv_fingerprints = {}
        self._retired_csv_fingerprints = {}
        self._stop_event = threading.Event()
        self._start_attempted = False
        self._started = False
        self._stopped = False
        self._status = "starting"
        self._phase = "starting"
        self._observer = None
        self._worker = None
        self._state_lock_context = None
        self._last_successful_time = None
        self._last_affected_date = None
        self._last_csv = None
        self._last_error = None

    def _resolve_paths(self) -> None:
        if self._module is None:
            self._module = _load_health_module()
        if self.input_dir is None:
            self.input_dir = Path(self._module.DEFAULT_INPUT_DIR).expanduser().resolve()
        if self.output_dir is None:
            self.output_dir = Path(self._module.DEFAULT_OUTPUT_DIR).expanduser().absolute()
        if self.state_file is None:
            self.state_file = Path(self._module.DEFAULT_STATE_FILE).expanduser().absolute()

    def _set_error(self, error: BaseException) -> None:
        detail = "{}: {}".format(type(error).__name__, error)
        with self._lock:
            self._status = "error"
            self._phase = "error"
            self._last_error = detail
        LOGGER.error("[SyncFit Health] %s", detail)

    def _on_worker_status(self, state, path, error, result) -> None:
        with self._lock:
            if state == "waiting-file":
                self._phase = "waiting-file"
                self._status = "waiting-file"
                self._last_csv = str(path) if path is not None else self._last_csv
                Logger.info("💚 [SyncFit Health] 等待 CSV 稳定: {}".format(path.name if path else ""))
            elif state == "processing":
                self._phase = "processing"
                self._status = "processing"
                self._last_csv = str(path) if path is not None else self._last_csv
                Logger.info("💚 [SyncFit Health] 处理中: {}".format(path.name if path else ""))
            elif state == "success":
                self._phase = "idle"
                self._status = "idle"
                self._last_csv = str(path) if path is not None else self._last_csv
                self._last_successful_time = datetime.now().astimezone().isoformat(timespec="seconds")
                dates = result if isinstance(result, (list, tuple, set)) else []
                self._last_affected_date = max(dates) if dates else None
                self._last_error = None
                Logger.info(
                    "💚 [SyncFit Health] 完成: {}，影响日期 {}".format(
                        path.name if path else "CSV",
                        self._last_affected_date or "无支持记录",
                    )
                )
            elif state == "error":
                self._phase = "error"
                self._status = "error"
                self._last_csv = str(path) if path is not None else self._last_csv
                self._last_error = error
                Logger.info("❌ [SyncFit Health] CSV 错误: {}: {}".format(path, error))
            elif state == "retry":
                self._phase = "waiting-file"
                self._status = "waiting-file"
                self._last_csv = str(path) if path is not None else self._last_csv
                self._last_error = error
                Logger.info("⚠️ [SyncFit Health] 等待重试: {}: {}".format(path, error))
            elif state == "idle":
                self._phase = "idle"
                if self._status not in ("error", "stopped"):
                    self._status = "idle"

    def start(self) -> bool:
        """Acquire the state lock, recover outputs, then start one watcher/worker."""
        with self._lifecycle_lock:
            if self._start_attempted:
                return self._started and not self._stopped
            self._start_attempted = True
            with self._lock:
                self._status = "starting"
                self._phase = "starting"

            succeeded = False
            try:
                self._resolve_paths()
                state_lock_context = self._module.state_lock(self.state_file)
                state_lock_context.__enter__()
                self._state_lock_context = state_lock_context

                state = self._module.load_state(self.state_file)
                with self.pause_controller.operation(cancel_event=self._stop_event) as proceed:
                    if not proceed:
                        with self._lock:
                            self._status = "stopped"
                            self._phase = "stopped"
                        return False
                    self._module._refresh_outputs(
                        self.output_dir,
                        self._module._flatten_state(state),
                    )

                if self._stop_event.is_set():
                    with self._lock:
                        self._status = "stopped"
                        self._phase = "stopped"
                    return False

                self._worker = self._module.CSVWorker(
                    self._process_csv,
                    stable_seconds=self.stable_seconds,
                    sample_interval=self.sample_interval,
                    stable_timeout=self.stable_timeout,
                    retry_delay=self.retry_delay,
                    status_callback=self._on_worker_status,
                )
                self._worker.start()
                self._observer = self._module.watcher(self.input_dir, self._enqueue_csv)
                succeeded = True
                self._started = True
                with self._lock:
                    self._status = "idle"
                    self._phase = "idle"
                LOGGER.info("[SyncFit Health] watching direct CSV files in %s", self.input_dir)
                Logger.info(
                    "💚 [SyncFit Health] 已启动 (PID: {})，监听 {}".format(os.getpid(), self.input_dir)
                )
                return True
            except Exception as error:
                self._set_error(error)
                return False
            finally:
                if not succeeded:
                    self._cleanup_resources()

    def _process_csv(self, path: Path):
        with self.pause_controller.operation(cancel_event=self._stop_event) as proceed:
            if not proceed:
                return None
            source = self._normalize_direct_csv_path(path)
            if source is None:
                raise self._module.IgnoredInputError(
                    "path is outside the Health input directory or is not a CSV: {}".format(path)
                )
            try:
                before = source.lstat()
            except OSError:
                raise
            if not stat.S_ISREG(before.st_mode):
                raise self._module.IgnoredInputError(
                    "path is no longer a direct regular CSV: {}".format(source)
                )
            before_fingerprint = _fingerprint_from_stat(before)

            # process_csv_file returns only after state and every affected daily
            # JSON file have been persisted successfully.
            result = self._module.process_csv_file(source, self.output_dir, self.state_file)
            try:
                after = source.lstat()
            except OSError as exc:
                raise self._module.DeferredInputError(
                    "{}: cannot stat CSV after synchronization: {}".format(source, exc)
                ) from exc
            if not stat.S_ISREG(after.st_mode):
                raise self._module.IgnoredInputError(
                    "path stopped being a direct regular CSV: {}".format(source)
                )
            after_fingerprint = _fingerprint_from_stat(after)
            if before_fingerprint != after_fingerprint:
                raise self._module.DeferredInputError(
                    "{}: CSV changed during synchronization".format(source)
                )

            with self._retention_lock:
                key = str(source)
                self._successful_csv_fingerprints[key] = after_fingerprint
                export_day, _order_key = self._retention_day_order(source, after_fingerprint)
                if export_day is not None:
                    self._cleanup_old_csvs_locked(export_day)
                else:
                    LOGGER.info(
                        "[SyncFit Health] CSV retention deferred because its local export day could not be determined: %s",
                        source,
                    )
            return result

    def _enqueue_csv(self, path: Path) -> None:
        """Queue only direct regular CSVs, suppressing delayed events for removals."""
        candidate = self._normalize_direct_csv_path(path)
        if candidate is None:
            return
        key = str(candidate)
        with self._retention_lock:
            try:
                info = candidate.lstat()
            except FileNotFoundError:
                if key in self._retired_csv_fingerprints:
                    return
            except OSError:
                # Preserve the worker's existing transient-missing retry behavior.
                pass
            else:
                if not stat.S_ISREG(info.st_mode):
                    return
                self._retired_csv_fingerprints.pop(key, None)
            worker = self._worker
            if worker is not None:
                worker.enqueue(candidate)

    def _normalize_direct_csv_path(self, path: Path):
        candidate = Path(path).expanduser().absolute()
        if candidate.suffix.lower() != ".csv" or self.input_dir is None:
            return None
        try:
            parent = candidate.parent.resolve()
            grandparent = candidate.parent.parent.resolve()
        except OSError:
            return None
        if candidate.parent != self.input_dir and not (
            parent == self.input_dir and grandparent == self.input_dir.parent
        ):
            return None
        # Normalize aliases such as macOS /var -> /private/var without resolving
        # the leaf, because resolving a leaf would follow a CSV symlink.
        return self.input_dir / candidate.name

    def _current_direct_csvs_locked(self):
        """Return direct regular CSV paths and fingerprints, or None on a scan race."""
        candidates = {}
        try:
            entries = sorted(self.input_dir.iterdir(), key=lambda item: item.name)
        except OSError:
            raise
        for candidate in entries:
            if candidate.suffix.lower() != ".csv":
                continue
            try:
                info = candidate.lstat()
            except FileNotFoundError:
                # A vanished path is no longer a current candidate. If it
                # reappears before deletion, the next full-day recheck detects it.
                continue
            if stat.S_ISREG(info.st_mode):
                candidates[str(candidate)] = (candidate, _fingerprint_from_stat(info))
        return candidates

    @staticmethod
    def _retention_day_order(path: Path, fingerprint):
        """Return export day and ordering key for audited or generic filenames."""
        match = _EXPORT_NAME.match(path.name)
        if match is not None:
            start_date, start_time, end_date, end_time = match.groups()
            try:
                start = datetime.strptime(start_date + start_time, "%Y%m%d%H%M%S")
                end = datetime.strptime(end_date + end_time, "%Y%m%d%H%M%S")
                if end < start:
                    raise ValueError("export end precedes start")
                timestamp_ns = int(end.timestamp()) * 1_000_000_000
                day = end.date().isoformat()
            except (OverflowError, OSError, ValueError):
                timestamp_ns = fingerprint[3]
                try:
                    day = datetime.fromtimestamp(timestamp_ns / 1_000_000_000).date().isoformat()
                except (OverflowError, OSError, ValueError):
                    return None, (timestamp_ns, path.name.casefold(), path.name)
        else:
            timestamp_ns = fingerprint[3]
            try:
                day = datetime.fromtimestamp(timestamp_ns / 1_000_000_000).date().isoformat()
            except (OverflowError, OSError, ValueError):
                return None, (timestamp_ns, path.name.casefold(), path.name)
        return day, (timestamp_ns, path.name.casefold(), path.name)

    def _queue_unimported_locked(self, candidates) -> None:
        worker = self._worker
        if worker is None:
            return
        for key, (path, fingerprint) in candidates.items():
            if self._successful_csv_fingerprints.get(key) != fingerprint:
                worker.enqueue(path)

    def _cleanup_old_csvs_locked(self, export_day: str) -> None:
        """Delete older CSVs for one export day after that day's inputs succeeded."""
        current_all = self._current_direct_csvs_locked()
        if current_all is None:
            LOGGER.info(
                "[SyncFit Health] CSV retention deferred for %s because the input directory changed during scan",
                export_day,
            )
            return
        candidates = {
            key: item
            for key, item in current_all.items()
            if self._retention_day_order(item[0], item[1])[0] == export_day
        }
        if not candidates:
            return

        if any(
            self._successful_csv_fingerprints.get(key) != fingerprint
            for key, (_path, fingerprint) in candidates.items()
        ):
            LOGGER.info(
                "[SyncFit Health] CSV retention deferred for %s until every same-day file is synchronized",
                export_day,
            )
            self._queue_unimported_locked(candidates)
            return

        ordered = sorted(
            candidates.items(),
            key=lambda item: self._retention_day_order(item[1][0], item[1][1])[1],
        )
        if len(ordered) <= 1:
            return

        expected = dict(candidates)
        newest_key = ordered[-1][0]
        removed = 0
        for key, (path, fingerprint) in ordered[:-1]:
            # Recheck the full set before each unlink so a changed/replaced or
            # newly arrived export cancels the remaining cleanup.
            current_all = self._current_direct_csvs_locked()
            current = (
                {
                    current_key: item
                    for current_key, item in current_all.items()
                    if self._retention_day_order(item[0], item[1])[0] == export_day
                }
                if current_all is not None
                else None
            )
            if current is None or current != expected:
                LOGGER.info(
                    "[SyncFit Health] CSV retention cancelled for %s because a same-day input changed",
                    export_day,
                )
                if current:
                    self._queue_unimported_locked(current)
                return
            if any(
                self._successful_csv_fingerprints.get(current_key) != current_fingerprint
                for current_key, (_current_path, current_fingerprint) in current.items()
            ):
                LOGGER.info(
                    "[SyncFit Health] CSV retention cancelled for %s because an input is not synchronized",
                    export_day,
                )
                self._queue_unimported_locked(current)
                return

            try:
                latest_info = path.lstat()
            except FileNotFoundError:
                LOGGER.info("[SyncFit Health] CSV retention cancelled for %s because %s disappeared", export_day, path)
                return
            if not stat.S_ISREG(latest_info.st_mode) or _fingerprint_from_stat(latest_info) != fingerprint:
                LOGGER.info("[SyncFit Health] CSV retention cancelled for %s because %s changed", export_day, path)
                return

            try:
                path.unlink()
            except OSError as exc:
                raise RuntimeError("could not remove older Health CSV {}: {}".format(path, exc)) from exc

            self._retired_csv_fingerprints[key] = fingerprint
            self._successful_csv_fingerprints.pop(key, None)
            if self._worker is not None:
                self._worker.discard(path)
            expected.pop(key, None)
            removed += 1

        newest_path, _newest_fingerprint = candidates[newest_key]
        Logger.info(
            "💚 [SyncFit Health] 已清理 {} 个旧 CSV，保留 {} 的最新文件 {}".format(
                removed,
                export_day,
                newest_path.name,
            )
        )

    def request_stop(self) -> None:
        """Cancel paused waits and prevent new worker items without blocking UI."""
        self._stop_event.set()
        worker = self._worker
        if worker is not None:
            worker.request_stop()

    def _cleanup_resources(self) -> None:
        observer = self._observer
        self._observer = None
        if observer is not None:
            try:
                observer.stop()
                observer.join()
            except Exception:
                LOGGER.exception("[SyncFit Health] observer shutdown failed")

        worker = self._worker
        self._worker = None
        if worker is not None:
            try:
                worker.stop(timeout=None)
            except Exception:
                LOGGER.exception("[SyncFit Health] worker shutdown failed")

        state_lock_context = self._state_lock_context
        self._state_lock_context = None
        if state_lock_context is not None:
            try:
                state_lock_context.__exit__(None, None, None)
            except Exception:
                LOGGER.exception("[SyncFit Health] state lock release failed")
            else:
                Logger.info("💚 [SyncFit Health] state lock 已释放 (PID: {})".format(os.getpid()))

    def stop(self) -> None:
        """Stop event intake, drain any active atomic write, and release the lock."""
        self.request_stop()
        with self._lifecycle_lock:
            if self._stopped:
                return
            self._cleanup_resources()
            self._started = False
            self._stopped = True
            with self._lock:
                self._status = "stopped"
                self._phase = "stopped"

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            status = self._status
            phase = self._phase
            snapshot = {
                "status": status,
                "phase": phase,
                "queued_count": 0,
                "current_file": None,
                "last_successful_time": self._last_successful_time,
                "last_affected_date": self._last_affected_date,
                "last_csv": self._last_csv,
                "error_detail": self._last_error,
            }
            worker = self._worker

        if worker is not None:
            worker_snapshot = worker.snapshot()
            snapshot["queued_count"] = worker_snapshot["queued_count"]
            snapshot["current_file"] = worker_snapshot["current_file"]
            worker_phase = worker_snapshot["phase"]
            if status not in ("starting", "error", "stopped"):
                if worker_snapshot["queued_count"]:
                    snapshot["status"] = "waiting-file"
                elif worker_phase in ("waiting-file", "processing"):
                    snapshot["status"] = worker_phase
                elif snapshot["error_detail"]:
                    snapshot["status"] = "error"
                else:
                    snapshot["status"] = "idle"

        if self.pause_controller.paused and snapshot["status"] != "stopped":
            snapshot["status"] = "paused"
        return snapshot
