"""Shared, conservative boundaries and guarded writes for source task sections."""
import hashlib
import os
import re
from dataclasses import dataclass

from config import Config
from ..utils import FileUtils, Logger


class UnsafeTaskSection(ValueError):
    pass


@dataclass(frozen=True)
class TaskSection:
    start: int
    end: int
    after: int
    before: int


def visible_lines(lines):
    """Ignore YAML frontmatter and fenced examples, including indented fences."""
    visible = set()
    yaml = bool(lines and lines[0].strip() == '---')
    fence = None
    for index, line in enumerate(lines):
        if yaml:
            if index and line.strip() in ('---', '...'):
                yaml = False
            continue
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line.rstrip('\r\n'))
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        visible.add(index)
    if yaml or fence:
        raise UnsafeTaskSection('未闭合 YAML 或代码块，无法安全确定任务区边界')
    return visible


def find_task_section(lines):
    visible = visible_lines(lines)
    starts = [i for i in visible if lines[i].rstrip('\r\n').rstrip() == '# Tasks']
    if len(starts) > 1:
        raise UnsafeTaskSection('存在多个 # Tasks，禁止猜测迁移范围')
    if not starts:
        return None
    start = starts[0]
    # New layout owns the immediately preceding divider. Keep accepting the
    # old trailing divider so legacy files can migrate without duplicates.
    before = start - 1 if start > 0 and start - 1 in visible and lines[start - 1].strip() == '----------' else start
    for i in range(start + 1, len(lines)):
        if i not in visible:
            continue
        if lines[i].strip() == '----------':
            return TaskSection(start, i, i + 1, before)
        if re.match(r'^#\s+', lines[i]):
            return TaskSection(start, i, i, before)
    return TaskSection(start, len(lines), len(lines), before)


def task_id(line):
    match = re.search(r'<span id="([a-zA-Z0-9]{6,})"(?: data-timestamps="[^"]*")?></span>|\^([a-zA-Z0-9]{6,})\s*$', line)
    if match:
        return match[1] or match[2]
    legacy = re.search(r'\(connect::.*?\^([a-zA-Z0-9]{6,})\)', line)
    return legacy[1] if legacy else None


def write_task_file(path, original, updated):
    """Back up the exact original outside the vault, then compare before replace."""
    original_text = ''.join(original)
    updated_text = ''.join(updated)
    def body_content(lines):
        region = find_task_section(lines)
        body = lines[:region.before] + lines[region.after:] if region else list(lines)
        while body and not body[-1].strip():
            body.pop()
        return ''.join(body).rstrip('\r\n')
    if body_content(original) != body_content(updated):
        raise UnsafeTaskSection('任务区之外的正文发生变化，取消写入')
    if original_text == updated_text:
        return True
    try:
        directory = os.path.abspath(Config.TASK_SECTION_BACKUP_DIR)
        vault = os.path.abspath(Config.VAULT_ROOT)
        if os.path.commonpath([os.path.realpath(directory), os.path.realpath(vault)]) == os.path.realpath(vault):
            raise OSError('任务区备份目录必须位于 Vault 外')
        os.makedirs(directory, exist_ok=True)
        key = hashlib.sha256((os.path.abspath(path) + '\0' + original_text).encode('utf-8')).hexdigest()
        backup = os.path.join(directory, key + '.md')
        data = original_text.encode('utf-8')
        try:
            with open(backup, 'xb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            pass
        with open(backup, 'rb') as handle:
            if handle.read() != data:
                raise OSError('备份文件校验失败')
        if not FileUtils.write_file(path, updated, expected_content=original_text):
            raise OSError('原文件并发变化或写入失败')
        Logger.info(f'📦 [Tasks] 原笔记备份: {backup}')
        return True
    except OSError as error:
        raise UnsafeTaskSection(f'取消任务区写入 {path}: {error}') from error
