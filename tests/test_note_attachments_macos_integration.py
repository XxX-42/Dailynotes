import base64
import os
import sys
import tempfile
import time
import unittest
import uuid
from datetime import date


ROOT = os.path.dirname(os.path.dirname(__file__))
NOTE_CORE = os.path.join(ROOT, "LyubishchevSync", "src", "external", "note_sync_core")
if NOTE_CORE not in sys.path:
    sys.path.insert(0, NOTE_CORE)

from read_today_note import AppleNotesReader  # noqa: E402
from note_attachments import AttachmentExporter  # noqa: E402


@unittest.skipUnless(
    os.environ.get("RUN_APPLE_NOTES_INTEGRATION") == "1",
    "set RUN_APPLE_NOTES_INTEGRATION=1 to modify a disposable Apple Note",
)
class AppleNotesAttachmentIntegrationTests(unittest.TestCase):
    def test_html_text_round_trip_is_detected_as_unsafe(self):
        reader = AppleNotesReader()
        title = f"TaskSync attachment integration {uuid.uuid4()}"
        note_id = None
        with tempfile.TemporaryDirectory() as directory:
            image_path = os.path.join(directory, "pixel.png")
            # 1x1 transparent PNG.
            with open(image_path, "wb") as handle:
                handle.write(base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
                ))
            try:
                self.assertEqual(reader.create_note(title, "09:30 integration"), "CREATED")
                snapshot = reader.get_note_snapshot(note_name=title)
                self.assertIsNotNone(snapshot)
                note_id = snapshot.note_id
                self.assertTrue(reader.add_attachment(note_id, image_path))
                time.sleep(1)
                before = reader.get_note_snapshot(note_id=note_id)
                self.assertEqual(len(before.attachments), 1)
                exporter = AttachmentExporter(directory, "assets", reader.save_attachment)
                self.assertTrue(exporter.export_all(before, date.today()))
                self.assertTrue(os.path.isfile(os.path.join(directory, before.attachments[0].obsidian_path)))
                before.document.append_suffix(0, " ✅")
                ok, after, error = reader.update_note_html(
                    note_id,
                    before.document.render(),
                    before.modification_date,
                )
                self.assertFalse(ok)
                self.assertEqual(error, "ATTACHMENT_COUNT_MISMATCH")
            finally:
                if note_id:
                    reader.delete_note_by_id(note_id)


if __name__ == "__main__":
    unittest.main()
