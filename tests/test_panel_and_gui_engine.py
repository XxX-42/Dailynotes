import ast
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from config import Config
from dailynotes.format_core import FormatCore
from dailynotes.manager import FusionManager
from external.task_sync_core.obsidian_service import parse_obsidian_line, get_obsidian_state


PANEL = "# Thinking 🧠\n\n| id | 随记 |\n| --- | --- |\n| [[项目]] | 用户手写内容 ![[照片.png\\|L\\|200]] |\n"


class ThinkingPanelTests(unittest.TestCase):
    def test_preserve_manual_panel_with_and_without_tasks(self):
        task = '- [ ] 03:00 - 05:00 <span id="abcdef"></span> [[项目#^abcdef|⮐]] [[项目]]\n'
        for prefix in ('# Deployment 🚀\n', '# Deployment 🚀\n' + task):
            for instant in (False, True):
                content = prefix + PANEL
                self.assertEqual(FormatCore.update_insights_table(content, instant), content)

    def test_no_panel_is_automatically_created(self):
        text = '# Deployment 🚀\n- [ ] <span id="abcdef"></span> 任务\n'
        self.assertEqual(FormatCore.update_insights_table(text), text)

    def test_execute_keeps_two_columns_and_manual_text_on_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, '2026-10-10.md')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write('# Deployment 🚀\n- [ ] 03:00 - 05:00 <span id="abcdef"></span> 任务\n' + PANEL)
            for _ in range(2):
                FormatCore.execute(path)
                text = Path(path).read_text()
                self.assertIn('| id | 随记 |', text)
                self.assertIn('用户手写内容', text)
                self.assertNotIn('ICE Score', text)
                self.assertEqual(text[text.index('# Thinking'):], PANEL)

    def test_legacy_scores_no_longer_weight_progress(self):
        self.assertFalse(Config.ENABLE_LEGACY_ICE)
        self.assertEqual(FormatCore._parse_ice_scores('# Thinking 🧠\n| 项目 | 0 | 0 | 0 | 10 | 10 | 10 | 1000 |'), {})

    def test_legacy_scores_do_not_override_explicit_calendar_tag(self):
        _, task = parse_obsidian_line('- [ ] 10:00 任务 ICE:1000 #D', 0)
        self.assertEqual(task['tag'], '#D')
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, '2026-10-10.md')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write('# Deployment 🚀\n## [[项目]]\n- [ ] 10:00 任务 #D\n# Thinking 🧠\n| id | cost | aim to | progress | Impact | Confidence | Ease | ICE Score |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n| [[项目]] | | | | 10 | 10 | 10 | 1000 |\n')
            tasks, *_ = get_obsidian_state(path)
            self.assertTrue(tasks)
            self.assertTrue(all(task['tag'] == '#D' for task in tasks.values()))


class SharedGUIEngineTests(unittest.TestCase):
    def test_gui_delegates_to_shared_run_without_signals(self):
        path = Path(__file__).resolve().parents[1] / 'LyubishchevSync' / 'gui_main.py'
        tree = ast.parse(path.read_text())
        function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'gui_run')
        original = mock.Mock(return_value='done')
        namespace = {'original_run': original}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
        manager = object()
        self.assertEqual(namespace['gui_run'](manager), 'done')
        original.assert_called_once_with(manager, register_signals=False)

    def test_notifications_during_sync_remain_pending(self):
        manager = FusionManager.__new__(FusionManager)
        manager._calendar_event_lock = threading.Lock()
        manager._calendar_dirty_flag = True
        manager._reminder_dirty_flag = True
        manager.sync_recent_window = mock.Mock(side_effect=lambda: setattr(manager, '_calendar_dirty_flag', True))
        manager.sync_reminders = mock.Mock(side_effect=lambda: setattr(manager, '_reminder_dirty_flag', True))
        manager._process_pending_changes()
        self.assertTrue(manager._calendar_dirty_flag)
        self.assertTrue(manager._reminder_dirty_flag)
        manager.sync_recent_window.assert_called_once()
        manager.sync_reminders.assert_called_once()

    def test_gui_mode_starts_and_stops_reminder_listener(self):
        manager = FusionManager.__new__(FusionManager)
        manager._startup_sync_done = True
        manager._observer = None
        manager._ek_client = None
        manager._reminder_client = mock.Mock()
        manager._calendar_event_lock = threading.Lock()
        manager._calendar_debounce_timer = None
        manager.app_ref = SimpleNamespace(should_run=False)
        manager.sm = mock.Mock()
        with mock.patch('dailynotes.manager.WATCHDOG_AVAILABLE', False), mock.patch('dailynotes.manager.signal.signal') as signal_handler:
            manager.run(register_signals=False)
        signal_handler.assert_not_called()
        manager._reminder_client.start_watching.assert_called_once_with(manager._on_reminder_push_event)
        manager._reminder_client.stop_watching.assert_called_once()
        manager.sm.save.assert_called_once()
