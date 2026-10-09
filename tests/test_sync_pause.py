import threading
import unittest

from dailynotes.sync_pause import SyncPauseController


class SyncPauseTests(unittest.TestCase):
    def test_new_operation_waits_until_resume(self):
        controller = SyncPauseController()
        completed = threading.Event()
        controller.pause()
        thread = threading.Thread(target=controller.guard(completed.set), daemon=True)
        thread.start()
        try:
            self.assertFalse(completed.wait(0.05))
            controller.resume()
            self.assertTrue(completed.wait(1))
        finally:
            controller.resume()
            thread.join(1)

    def test_active_operation_can_finish_nested_work_after_pause(self):
        controller = SyncPauseController()
        with controller.operation():
            controller.pause()
            # Reconciliation often calls formatting and date sync recursively.
            # Pause must not deadlock that already active operation.
            with controller.operation():
                self.assertTrue(controller.paused)
        controller.resume()

    def test_exception_releases_operation_depth(self):
        controller = SyncPauseController()
        with self.assertRaises(ValueError):
            with controller.operation():
                raise ValueError('operation failed')
        self.assertEqual(controller._local.depth, 0)


if __name__ == '__main__':
    unittest.main()
