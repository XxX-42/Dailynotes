import os
import tempfile
import unittest
from unittest import mock

from dailynotes.daily_note_factory import ensure_daily_note


class DailyNoteFactoryTests(unittest.TestCase):
    def test_creates_once_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            daily_dir = os.path.join(directory, "2_DailyNote")
            with mock.patch("dailynotes.daily_note_factory.Config.DAILY_NOTE_DIR", daily_dir), mock.patch(
                "dailynotes.daily_note_factory.Config.TEMPLATE_FILE", os.path.join(directory, "missing.md")
            ):
                self.assertEqual(ensure_daily_note("2026-08-10", "test"), "CREATED")
                path = os.path.join(daily_dir, "2026-08-10.md")
                with open(path, "a", encoding="utf-8") as handle:
                    handle.write("user content\n")
                self.assertEqual(ensure_daily_note("2026-08-10", "test"), "ALREADY_EXISTS")
                with open(path, "r", encoding="utf-8") as handle:
                    self.assertIn("user content", handle.read())


if __name__ == "__main__":
    unittest.main()
