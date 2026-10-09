"""Explicit single-note migration. Preview by default; --apply makes a guarded write."""
import argparse
import difflib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'LyubishchevSync'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'LyubishchevSync', 'src'))

from dailynotes.utils import FileUtils
from dailynotes.sync.rendering import inject_into_task_section
from dailynotes.sync.task_section import find_task_section, write_task_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('note', help='One existing project note, never a directory')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not os.path.isfile(args.note):
        parser.error('note must be an existing file')
    original = FileUtils.read_file(args.note)
    if original is None:
        parser.error('note could not be read')
    before = find_task_section(original)
    if before is None:
        print('No Tasks section; no change.')
        return
    updated = inject_into_task_section(list(original), [])
    after = find_task_section(updated)
    # A migration must never modify the YAML/body or the section contents.
    original_body = ''.join(original[:before.before] + original[before.after:]).rstrip('\r\n')
    updated_body = ''.join(updated[:after.before]).rstrip('\r\n')
    assert original_body == updated_body, 'Non-Tasks content changed'
    assert ''.join(original[before.start + 1:before.end]).strip('\r\n') == ''.join(updated[after.start + 1:after.end]).strip('\r\n'), 'Task content changed'
    if args.apply:
        write_task_file(args.note, original, updated)
        print('Migrated to EOF; body and task content verified unchanged.')
    else:
        sys.stdout.writelines(difflib.unified_diff(original, updated, fromfile=args.note, tofile=args.note + ' (preview)'))


if __name__ == '__main__':
    main()
