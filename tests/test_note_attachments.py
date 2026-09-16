import json
import os
import sys
import tempfile
import unittest
from datetime import date


ROOT = os.path.dirname(os.path.dirname(__file__))
NOTE_CORE = os.path.join(ROOT, "LyubishchevSync", "src", "external", "note_sync_core")
if NOTE_CORE not in sys.path:
    sys.path.insert(0, NOTE_CORE)

from note_attachments import (  # noqa: E402
    AttachmentExporter,
    AttachmentSnapshot,
    AttachmentStateStore,
    NoteSnapshot,
    render_attachment_links,
)
from note_transaction import NoteAttachmentTransaction  # noqa: E402


class NoteHTMLMappingTests(unittest.TestCase):
    def _snapshot(self, body, attachments):
        return NoteSnapshot("note-1", "2026/9/16", "", body, "mod-1", attachments)

    def test_images_bind_to_previous_nonempty_line_across_blanks(self):
        body = (
            '<html><body><div>09:30 早餐</div><div><br></div>'
            '<div><img src="cid:photo-a"></div><div>10:00 跑步</div>'
            '<div><object data="cid:photo-b"></object><img src="cid:photo-c"></div>'
            '</body></html>'
        )
        attachments = [
            AttachmentSnapshot("a", "photo-a", "a.jpg"),
            AttachmentSnapshot("b", "photo-b", "b.jpg"),
            AttachmentSnapshot("c", "photo-c", "c.jpg"),
        ]
        snapshot = self._snapshot(body, attachments)

        self.assertEqual([line.text for line in snapshot.document.lines], ["09:30 早餐", "10:00 跑步"])
        self.assertEqual([item.attachment_id for item in snapshot.document.lines[0].attachments], ["a"])
        self.assertEqual([item.attachment_id for item in snapshot.document.lines[1].attachments], ["b", "c"])

    def test_embedded_data_image_falls_back_to_attachment_order(self):
        body = '<div>09:30 早餐</div><div><img src="data:image/png;base64,AAAA"></div>'
        attachment = AttachmentSnapshot("a", "server-cid-not-in-html", "a.png")
        snapshot = self._snapshot(body, [attachment, attachment])
        self.assertEqual([item.attachment_id for item in snapshot.document.lines[0].attachments], ["a"])

    def test_image_before_first_text_is_orphan(self):
        body = '<div><img src="cid:orphan"></div><div>正文</div>'
        snapshot = self._snapshot(body, [AttachmentSnapshot("a", "orphan", "a.jpg")])
        self.assertEqual(snapshot.document.orphan_cids, ["orphan"])
        self.assertEqual(snapshot.document.lines[0].attachments, [])

    def test_suffix_and_reconcile_preserve_attachment_markup(self):
        body = '<div>09:30 早餐</div><div><img src="cid:photo-a"></div>'
        snapshot = self._snapshot(body, [AttachmentSnapshot("a", "photo-a", "a.jpg")])
        snapshot.document.append_suffix(0, " ✅")
        rendered = snapshot.document.render()
        self.assertIn("09:30 早餐 ✅", rendered)
        self.assertIn('src="cid:photo-a"', rendered)

        snapshot = self._snapshot(body, [AttachmentSnapshot("a", "photo-a", "a.jpg")])
        snapshot.document.reconcile_text_lines([])
        rendered = snapshot.document.render()
        self.assertIn("[已解除同步]", rendered)
        self.assertIn('src="cid:photo-a"', rendered)

    def test_render_links_keep_order_and_size_suffix(self):
        attachments = [
            AttachmentSnapshot("a", "ca", "a.jpg", "【ATTACHMENT】/AppleNotes/a.jpg", "1"),
            AttachmentSnapshot("b", "cb", "b.jpg", "【ATTACHMENT】/AppleNotes/b.jpg", "2"),
        ]
        self.assertEqual(
            render_attachment_links(attachments),
            "![[【ATTACHMENT】/AppleNotes/a.jpg|L|200]] ![[【ATTACHMENT】/AppleNotes/b.jpg|L|200]]",
        )


class AttachmentExporterTests(unittest.TestCase):
    def test_export_is_atomic_hashed_and_idempotent(self):
        with tempfile.TemporaryDirectory() as vault:
            calls = []

            def save(note_id, attachment_id, path):
                calls.append((note_id, attachment_id))
                with open(path, "wb") as handle:
                    handle.write(b"image-bytes")
                return True

            snapshot = NoteSnapshot(
                "note-1",
                "today",
                "",
                '<div>line</div><img src="cid:a">',
                "m",
                [AttachmentSnapshot("attachment-1", "a", "photo.jpg")],
            )
            exporter = AttachmentExporter(vault, "【ATTACHMENT】", save)
            self.assertTrue(exporter.export_all(snapshot, date(2026, 9, 16)))
            exported = snapshot.attachments[0]
            self.assertTrue(os.path.isfile(os.path.join(vault, exported.obsidian_path)))
            self.assertEqual(len(exported.sha256), 64)

            self.assertTrue(exporter.export_all(snapshot, date(2026, 9, 16)))
            self.assertEqual(calls, [("note-1", "attachment-1")])

    def test_zero_byte_export_fails(self):
        with tempfile.TemporaryDirectory() as vault:
            def save(_note_id, _attachment_id, path):
                open(path, "wb").close()
                return True

            snapshot = NoteSnapshot(
                "n", "today", "", '<div>x</div><img src="cid:a">', "m",
                [AttachmentSnapshot("a", "a", "a.jpg")],
            )
            self.assertFalse(AttachmentExporter(vault, "assets", save).export_all(snapshot, date.today()))


class TransactionTests(unittest.TestCase):
    class Config:
        pass

    class Reader:
        def __init__(self, snapshot, result=None):
            self.snapshot = snapshot
            self.result = result
            self.added = []

        def save_attachment(self, _note_id, _attachment_id, path):
            with open(path, "wb") as handle:
                handle.write(b"image")
            return True

        def update_note_html(self, _note_id, _html, expected_modification_date=None):
            if self.result is not None:
                return self.result
            return True, self.snapshot, None

        def add_attachment(self, note_id, path):
            self.added.append((note_id, path))
            return True

    def _config(self, root):
        config = self.Config()
        config.VAULT_ROOT = root
        config.REL_ATTACHMENT_DIR = "attachments"
        config.APPLE_NOTES_ATTACHMENT_STATE_FILE = os.path.join(root, "state.json")
        config.APPLE_NOTES_RECOVERY_DIR = os.path.join(root, "recovery")
        return config

    def test_concurrent_update_is_cancelled_without_blocking_note(self):
        with tempfile.TemporaryDirectory() as root:
            snapshot = NoteSnapshot("n", "today", "text", "<div>text</div>", "m", [])
            reader = self.Reader(snapshot, (False, snapshot, "CONCURRENT_MODIFICATION"))
            transaction = NoteAttachmentTransaction(reader, self._config(root), lambda _message: None)
            ok, _ = transaction.write_html(snapshot, "<div>changed</div>")
            self.assertFalse(ok)
            self.assertNotIn("n", transaction.blocked_note_ids)

    def test_attachment_note_body_write_is_refused_after_backup(self):
        with tempfile.TemporaryDirectory() as root:
            attachment = AttachmentSnapshot("a", "cid-a", "a.jpg")
            before = NoteSnapshot("n", "today", "text", '<div>text</div><img src="cid:cid-a">', "m", [attachment])
            reader = self.Reader(before)
            transaction = NoteAttachmentTransaction(reader, self._config(root), lambda _message: None)
            self.assertTrue(transaction.prepare(before, date(2026, 9, 16)))
            ok, _ = transaction.write_html(before, "<div>changed</div>")
            self.assertFalse(ok)
            self.assertEqual(reader.added, [])
            recovery_files = []
            for current_root, _dirs, files in os.walk(os.path.join(root, "recovery")):
                recovery_files.extend(os.path.join(current_root, item) for item in files)
            self.assertTrue(any(path.endswith(".html") for path in recovery_files))


if __name__ == "__main__":
    unittest.main()
