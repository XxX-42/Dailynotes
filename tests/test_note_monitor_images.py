import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "LyubishchevSync", "src")
PROJECT = os.path.join(ROOT, "LyubishchevSync")
NOTE_CORE = os.path.join(SRC, "external", "note_sync_core")
for path in (SRC, PROJECT, NOTE_CORE):
    if path not in sys.path:
        sys.path.insert(0, path)

from monitor import NoteMonitor  # noqa: E402


class _Reader:
    def __init__(self):
        self.updated = None

    def update_note_content(self, name, content):
        self.updated = (name, content)
        return True


class NoteMonitorImageRoutingTests(unittest.TestCase):
    def _monitor(self):
        monitor = NoteMonitor.__new__(NoteMonitor)
        monitor._log = lambda _message: None
        monitor._reader = _Reader()
        monitor._config = type("Config", (), {"KEYWORD_MAPPING": {}})
        monitor._write_snapshot_html = lambda _snapshot: True
        return monitor

    def test_takein_receives_attachment_link_after_business_content(self):
        monitor = self._monitor()
        calls = []
        monitor._append_to_daily_note = lambda line, links="": calls.append((line, links)) or True
        monitor._append_to_day_plan_section = lambda *_args: False
        monitor._append_to_account_section = lambda *_args: False
        monitor._is_day_plan_entry = lambda _line: False
        monitor._mark_obsidian_task_completed_with_time = lambda *_args: False
        monitor._process_diff(
            ["@@ -0,0 +1 @@", "+09:30 早餐"],
            ["09:30 早餐"],
            "today",
            line_attachments={0: "![[【ATTACHMENT】/AppleNotes/a.jpg|L|200]]"},
        )
        self.assertEqual(calls[0][1], "![[【ATTACHMENT】/AppleNotes/a.jpg|L|200]]")

    def test_parse_entry_places_link_at_generated_line_end(self):
        monitor = self._monitor()
        parsed = monitor._parse_entry(
            '09:30:01"Food":"egg"',
            "![[【ATTACHMENT】/AppleNotes/a.jpg|L|200]]",
        )
        self.assertTrue(parsed["raw"].rstrip().endswith("![[【ATTACHMENT】/AppleNotes/a.jpg|L|200]]"))

    def test_raw_task_image_routes_to_existing_obsidian_task(self):
        monitor = self._monitor()
        calls = []
        monitor._append_attachment_to_obsidian_task = lambda task_id, links: calls.append((task_id, links)) or True
        monitor._append_to_daily_note = lambda *_args: False
        monitor._append_to_day_plan_section = lambda *_args: False
        monitor._append_to_account_section = lambda *_args: False
        monitor._is_day_plan_entry = lambda _line: False
        monitor._process_diff(
            ["@@ -0,0 +1 @@", "+*abc123*#B 拍照"],
            ["*abc123*#B 拍照"],
            "today",
            line_attachments={0: "![[【ATTACHMENT】/AppleNotes/a.jpg|L|200]]"},
        )
        self.assertEqual(calls[0][0], "abc123")


if __name__ == "__main__":
    unittest.main()
