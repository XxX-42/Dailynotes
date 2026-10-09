import copy
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from config import Config
from dailynotes.utils import FileUtils
from dailynotes.sync.task_section import find_task_section, UnsafeTaskSection, write_task_file
from dailynotes.sync.rendering import inject_into_task_section
from dailynotes.sync.parsing import parse_file_tasks
from dailynotes.sync.engine import SyncCore
from dailynotes.sync.task_registry import TaskRegistry


TASK = '- [ ] <span id="kaithn"></span>[[2026-10-10#^kaithn|⮐]] 任务\n'
SECTION = '# Tasks\n\n## [[2026-10-10]]\n\n' + TASK + '\n----------\n'


def lines(text):
    return text.splitlines(keepends=True)


class TaskSectionTailTests(unittest.TestCase):
    def render(self, text, incoming=''):
        result = lines(text)
        self.assertIs(inject_into_task_section(result, lines(incoming)), result)
        return ''.join(result)

    def test_new_section_at_tail_preserves_yaml_and_unrelated_dividers(self):
        original = '---\ntags: [main]\n---\n\n# 正文\n内容\n----------\n'
        output = self.render(original, TASK)
        self.assertTrue(output.startswith(original.rstrip('\n') + '\n' * 11 + '----------\n# Tasks\n'))
        self.assertFalse(output.rstrip().endswith('----------'))
        self.assertEqual(output.count('----------'), 2)
        self.assertEqual(output, self.render(output))

    def test_existing_top_middle_and_tail_move_idempotently(self):
        for text in (SECTION + '\n# 正文\n内容\n', '# 前文\n内容\n\n' + SECTION + '\n# 后文\n内容\n', '# 正文\n内容\n\n' + SECTION):
            output = self.render(text)
            self.assertGreater(output.index('# Tasks'), output.index('内容'))
            self.assertIn(TASK, output)
            self.assertEqual(output.count('# Tasks'), 1)
            self.assertEqual(output, self.render(output))

    def test_exactly_ten_blank_lines_before_tasks_on_repeat(self):
        for padding in ('', '\n', '\n' * 4, '\n' * 15, '\n \n\t\n'):
            text = '# 正文\n内容' + padding + '\n' + SECTION
            for _ in range(3):
                text = self.render(text)
                rows = text.splitlines()
                header = rows.index('# Tasks')
                self.assertEqual(rows[header - 1], '----------')
                index = header - 2
                count = 0
                while index >= 0 and not rows[index].strip():
                    count += 1
                    index -= 1
                self.assertEqual(count, 10)
                self.assertEqual(rows[index], '内容')

    def test_missing_end_stops_at_next_l1_or_eof(self):
        for suffix in ('', '# 正文\n不迁移的内容\n'):
            original = SECTION.replace('----------\n', '') + suffix
            output = self.render(original)
            self.assertIn('----------\n# Tasks\n', output)
            self.assertFalse(output.rstrip().endswith('----------'))
            if suffix:
                self.assertTrue(output.startswith(suffix.rstrip('\n')))
            self.assertIn(TASK, output)

    def test_yaml_and_fenced_examples_are_not_sections(self):
        yaml = '---\ntest: |-\n  # Tasks\n  ----------\n---\n'
        code = '\n```markdown\n' + SECTION + '```\n'
        output = self.render(yaml + code + '\n' + SECTION)
        self.assertTrue(output.startswith(yaml + code))
        section = find_task_section(lines(output))
        self.assertGreater(section.start, len(lines(yaml + code)))

    def test_manual_content_and_children_preserved(self):
        body = '\n手写前言\n\n## [[2026-10-10]]\n\n' + TASK + '\t- [x] 子任务\n\t![[图片.png|L|200]]\n\n手写后记\n\n'
        original = '# Tasks\n' + body + '----------\n\n# 正文\n内容\n'
        output = self.render(original)
        self.assertIn('----------\n# Tasks\n' + body, output)

    def test_old_and_new_divider_layouts_parse_and_repeat(self):
        sm = SimpleNamespace(calc_hash=lambda *args: repr(args), find_id_by_hash=lambda *args: None)
        new = '----------\n' + SECTION.replace('----------\n', '')
        for section in (SECTION, new):
            original = '# 正文\n内容\n\n' + section
            output = self.render(original)
            self.assertEqual(output.count('----------'), 1)
            self.assertEqual(output, self.render(output))
            tasks, _, _ = parse_file_tasks('/tmp/example.md', lines(output), '项目', sm, write_back=False)
            self.assertEqual([task['bid'] for task in tasks], ['kaithn'])

    def test_span_and_legacy_ids_update_not_duplicate(self):
        for task in (TASK, '- [ ] 旧任务 [[2026-10-10]] ^kaithn\n'):
            original = SECTION.replace(TASK, task) + '# 正文\n内容\n'
            updated = TASK.replace('- [ ]', '- [x]').replace('任务', '更新后的任务')
            output = self.render(original, updated)
            self.assertIn(updated, output)
            self.assertEqual(output.count('<span id="kaithn">'), 1)
            self.assertNotIn('^kaithn\n', output)
            self.assertEqual(output, self.render(output, updated))

    def test_indented_synced_task_and_child_image_not_lost(self):
        incoming = '\t' + TASK + '\t\t- [x] 子任务\n\t\t![[照片.png|L|200]]\n'
        output = self.render('# 正文\n内容\n', incoming)
        self.assertIn(incoming, output)
        self.assertEqual(output, self.render(output, incoming))

    def test_incoming_blank_lines_do_not_drop_children_or_code(self):
        incoming = TASK + '\n\t- [x] 子任务\n\n\t![[照片.png|L|200]]\n\n> 手写引用\n```text\n代码内容\n```\n'
        output = self.render('# 正文\n内容\n', incoming)
        self.assertIn(incoming.rstrip('\n'), output)
        updated = incoming.replace('任务\n', '更新任务\n', 1)
        output = self.render(output, updated)
        self.assertIn(updated.rstrip('\n'), output)
        self.assertEqual(output.count('子任务'), 1)
        self.assertEqual(output.count('照片.png'), 1)

    def test_duplicate_and_unclosed_boundaries_rejected_without_mutation(self):
        for text in (SECTION + SECTION, '```\n' + SECTION, '---\ntags: main\n' + SECTION):
            original = lines(text)
            snapshot = list(original)
            with self.assertRaises(UnsafeTaskSection):
                inject_into_task_section(original, [])
            self.assertEqual(original, snapshot)

    def test_parser_ignores_yaml_code_and_following_section(self):
        example = '---\ntest: |-\n  ' + TASK.strip() + '\n---\n```md\n' + SECTION + '```\n'
        original = lines(example + SECTION.replace('----------\n', '') + '# 正文\n' + TASK.replace('kaithn', 'aaaaaa'))
        sm = SimpleNamespace(calc_hash=lambda *args: repr(args), find_id_by_hash=lambda *args: None)
        tasks, _, _ = parse_file_tasks('/tmp/example.md', original, '项目', sm, write_back=False)
        self.assertEqual([task['bid'] for task in tasks], ['kaithn'])


class TaskSectionWriteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.vault = Path(self.directory.name) / 'vault'
        self.vault.mkdir()
        self.path = self.vault / '项目.md'
        self.path.write_text(SECTION + '\n# 正文\n内容\n')
        self.backups = Path(self.directory.name) / 'backups'
        self.config = mock.patch.multiple(Config, VAULT_ROOT=str(self.vault), TASK_SECTION_BACKUP_DIR=str(self.backups))
        self.config.start()
        self.addCleanup(self.config.stop)

    def test_backup_original_then_write_and_repeat(self):
        original = lines(self.path.read_text())
        updated = inject_into_task_section(list(original), [])
        self.assertTrue(write_task_file(str(self.path), original, updated))
        backup = list(self.backups.glob('*.md'))
        self.assertEqual(len(backup), 1)
        self.assertEqual(backup[0].read_text(), ''.join(original))
        self.assertTrue(write_task_file(str(self.path), updated, updated))
        self.assertEqual(len(list(self.backups.glob('*.md'))), 1)

    def test_backup_failure_cancels_write(self):
        original = lines(self.path.read_text())
        with mock.patch('dailynotes.sync.task_section.os.makedirs', side_effect=OSError('denied')):
            with self.assertRaises(UnsafeTaskSection):
                write_task_file(str(self.path), original, inject_into_task_section(list(original), []))
        self.assertEqual(self.path.read_text(), ''.join(original))

    def test_body_change_rejected_even_if_task_output_is_valid(self):
        original = lines(self.path.read_text())
        updated = inject_into_task_section(list(original), [])
        updated = lines(''.join(updated).replace('内容', '意外删改正文'))
        with self.assertRaises(UnsafeTaskSection):
            write_task_file(str(self.path), original, updated)
        self.assertEqual(self.path.read_text(), ''.join(original))

    def test_inplace_write_also_rejects_stale_snapshot(self):
        self.path.write_text('用户最新输入\n')
        self.assertFalse(FileUtils.write_file(str(self.path), '程序旧版本\n', strategy='inplace', expected_content='旧内容\n'))
        self.assertEqual(self.path.read_text(), '用户最新输入\n')

    def test_formatting_cancels_if_user_edits_after_read(self):
        from dailynotes.format_core import FormatCore
        self.path.write_text('# Deployment 🚀\n- [ ] 10:00 任务\n')
        original_method = FormatCore.sort_markdown_sections
        def edit_then_format(content, **kwargs):
            self.path.write_text('用户最新输入\n')
            return original_method(content, **kwargs)
        with mock.patch.object(FormatCore, 'sort_markdown_sections', side_effect=edit_then_format):
            self.assertFalse(FormatCore.execute(str(self.path)))
        self.assertEqual(self.path.read_text(), '用户最新输入\n')

    def test_concurrent_edit_cancels_write(self):
        original = lines(self.path.read_text())
        self.path.write_text('用户并发修改\n')
        with self.assertRaises(UnsafeTaskSection):
            write_task_file(str(self.path), original, inject_into_task_section(list(original), []))
        self.assertEqual(self.path.read_text(), '用户并发修改\n')

    def test_backup_inside_vault_rejected(self):
        original = lines(self.path.read_text())
        with mock.patch.object(Config, 'TASK_SECTION_BACKUP_DIR', str(self.vault / 'backups')):
            with self.assertRaises(UnsafeTaskSection):
                write_task_file(str(self.path), original, inject_into_task_section(list(original), []))

    def test_failed_sync_rolls_back_task_state(self):
        core = SyncCore.__new__(SyncCore)
        core.sm = SimpleNamespace(state={'kaithn': {'hash': 'old'}})
        snapshot = copy.deepcopy(core.sm.state)
        def fail(*args):
            core.sm.state['kaithn']['hash'] = 'new'
            raise UnsafeTaskSection('cancelled')
        core._process_date_impl = fail
        with self.assertRaises(UnsafeTaskSection):
            core.process_date('2026-10-10', {})
        self.assertEqual(core.sm.state, snapshot)

    def test_invalid_rescan_does_not_drop_cached_tasks(self):
        registry = TaskRegistry()
        path = str(self.path)
        task = {'bid': 'kaithn', '_task_date': '2026-10-10'}
        registry._file_cache = {path: [task]}
        registry._file_to_dates = {path: {'2026-10-10'}}
        registry._date_index = {'2026-10-10': {'kaithn': task}}
        registry._resolve_project = lambda directory: '项目'
        with mock.patch.object(registry, '_scan_single_file', side_effect=UnsafeTaskSection('ambiguous')):
            with self.assertRaises(UnsafeTaskSection):
                registry.update_file(path, SimpleNamespace())
        self.assertEqual(registry._file_cache[path], [task])
        self.assertIn('kaithn', registry._date_index['2026-10-10'])

    def test_completion_only_changes_real_task_and_migrates(self):
        example = '---\ntest: |-\n  ' + TASK.strip() + '\n---\n'
        self.path.write_text(example + SECTION + '\n# 正文\n内容\n')
        core = SyncCore.__new__(SyncCore)
        self.assertTrue(core._update_task_status_in_file(str(self.path), 'kaithn', 'x'))
        output = self.path.read_text()
        self.assertTrue(output.startswith(example))
        self.assertIn(TASK.replace('- [ ]', '- [x]'), output)
        self.assertGreater(output.rindex('# Tasks'), output.index('# 正文'))

    def test_source_update_and_delete_preserve_manual_body(self):
        prefix = '---\ntest: |-\n  ' + TASK.strip() + '\n---\n'
        self.path.write_text(prefix + SECTION + '\n# 正文\n手写正文\n')
        core = SyncCore.__new__(SyncCore)
        core.sm = SimpleNamespace(state={})
        core._task_registry = mock.Mock()
        core.trigger_delayed_verification = mock.Mock()
        updated = TASK.replace('- [ ]', '- [x]').replace('任务', '更新任务')
        core._apply_source_changes(str(self.path), {'kaithn': [updated]})
        output = self.path.read_text()
        self.assertTrue(output.startswith(prefix))
        self.assertEqual(output.count(updated), 1)
        self.assertIn('手写正文', output)
        core._apply_source_changes(str(self.path), deletions={'kaithn'})
        output = self.path.read_text()
        self.assertTrue(output.startswith(prefix))
        self.assertNotIn(updated, output)
        self.assertIn('手写正文', output)

    def test_date_rebind_and_new_task_creation(self):
        core = SyncCore.__new__(SyncCore)
        core.sm = SimpleNamespace(state={})
        core._task_registry = mock.Mock()
        core.trigger_delayed_verification = mock.Mock()
        updated = TASK.replace('2026-10-10', '2026-10-11')
        core._apply_source_changes(str(self.path), {'kaithn': [updated]})
        output = self.path.read_text()
        self.assertEqual(output.count('<span id="kaithn">'), 1)
        self.assertIn('## [[2026-10-11]]', output)
        new_task = TASK.replace('kaithn', 'bbbbbb')
        core._apply_source_changes(str(self.path), {'bbbbbb': [new_task]})
        self.assertIn(new_task, self.path.read_text())
