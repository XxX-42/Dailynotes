"""Cooperative pause: finish an active operation, queue new operations until resume."""

import threading
from contextlib import contextmanager
from functools import wraps


class SyncPauseController:
    def __init__(self):
        self._condition = threading.Condition()
        self._paused = False
        self._local = threading.local()

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

    @contextmanager
    def operation(self):
        depth = getattr(self._local, 'depth', 0)
        if not depth:
            with self._condition:
                self._condition.wait_for(lambda: not self._paused)
                self._local.depth = 1
        else:
            self._local.depth = depth + 1
        try:
            yield
        finally:
            self._local.depth -= 1

    def guard(self, callback):
        @wraps(callback)
        def guarded(*args, **kwargs):
            with self.operation():
                return callback(*args, **kwargs)
        return guarded


sync_pause = SyncPauseController()
