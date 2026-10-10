"""Cooperative pause: finish an active operation, queue new operations until resume."""

import threading
from contextlib import contextmanager
from functools import wraps


class SyncPauseController:
    def __init__(self):
        self._condition = threading.Condition()
        self._paused = False
        self._local = threading.local()
        self._cancel_event = threading.Event()

    @property
    def paused(self):
        with self._condition:
            return self._paused

    def pause(self):
        with self._condition:
            self._paused = True

    def resume(self):
        with self._condition:
            self._paused = False
            self._condition.notify_all()

    def cancel_waiters(self):
        """Let shutdown release operations that are waiting for a resume."""
        self._cancel_event.set()
        with self._condition:
            self._condition.notify_all()

    @contextmanager
    def operation(self, cancel_event=None):
        depth = getattr(self._local, 'depth', 0)
        if not depth:
            cancellation = cancel_event or self._cancel_event
            with self._condition:
                while self._paused and not cancellation.is_set():
                    self._condition.wait(0.1)
                if cancellation.is_set():
                    acquired = False
                else:
                    self._local.depth = 1
                    acquired = True
            if not acquired:
                yield False
                return
        else:
            self._local.depth = depth + 1
        try:
            yield True
        finally:
            self._local.depth -= 1

    def guard(self, callback):
        @wraps(callback)
        def guarded(*args, **kwargs):
            with self.operation() as proceed:
                if not proceed:
                    return None
                return callback(*args, **kwargs)
        return guarded


sync_pause = SyncPauseController()
