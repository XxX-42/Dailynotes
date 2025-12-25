"""
Obsidian Service - Adapted for unified config.
Parses Obsidian daily notes for task extraction.
"""
import os
import re
import shutil
from config import Config

# Use config values
TAG_MAPPINGS = Config.TAG_MAPPINGS
DEFAULT_CALENDAR = Config.REMINDERS_LIST_NAME


def create_note_from_template(target_path, template_path):
    """Create a new note from template."""
    if template_path and os.path.exists(template_path):
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(template_path, target_path)
            print(f"📄 已通过模板创建日志: {os.path.basename(target_path)}")
            return True
        except Exception:
            return False
    else:
        return False


def parse_obsidian_line(line, line_index):
    """
    Parse a single line from Obsidian for task information.
    
    Returns:
        tuple: (key, data_dict) or None if not a valid task line
    """
    # Pre-check
    if not re.search(r"^\s*- \[[ xX]\]", line):
        return None

    # Flexible regex to match task format
    pattern = re.compile(r"^\s*- \[(.)\]\s+(?:(\d{1,2}:\d{2})(?:\s*-\s*(\d{1,2}:\d{2}))?\s+)?(.*)")
    match = pattern.match(line)
    if not match:
        return None

    status, start_time, end_time, raw_text = match.groups()

    # Normalize time format
    if not start_time:
        start_time = "00:00"
    else:
        start_time = start_time.zfill(5)  # "9:00" -> "09:00"

    if end_time:
        end_time = end_time.zfill(5)

    target_calendar = DEFAULT_CALENDAR
    clean_name = raw_text.strip()
    found_tag = ""

    for mapping in TAG_MAPPINGS:
        tag = mapping["tag"]
        if tag in clean_name:
            target_calendar = mapping["calendar"]
            clean_name = clean_name.replace(tag, "", 1).strip()
            clean_name = re.sub(r'\s+', ' ', clean_name).strip()
            found_tag = tag
            break

    key = f"{clean_name}_{start_time}"
    return key, {
        'name': clean_name,
        'start_time': start_time,
        'end_time': end_time,
        'target_calendar': target_calendar,
        'tag': found_tag,
        'line_index': line_index,
        'raw_text': raw_text.strip(),
        'status': status.lower()
    }


def get_obsidian_state(file_path):
    """
    Get the current state of tasks from an Obsidian file.
    
    Strategy:
    1. Read: Scan entire file for time-blocked tasks
    2. Write Anchor: Find '# Day planner' header for insertion point
    
    Returns:
        tuple: (tasks, lines, mod_time, insertion_index)
    """
    tasks = {}
    if not os.path.exists(file_path):
        return tasks, [], 0, -1

    mod_time = os.path.getmtime(file_path)
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # --- 1. Locate write region (Anchor) ---
    header_line_index = -1
    section_end_index = len(lines)

    # Find Day planner header
    for i, line in enumerate(lines):
        clean_line = line.strip().lower().replace(" ", "")
        if line.strip().startswith("#") and "#dayplanner" in clean_line:
            header_line_index = i
            break

    # If header found, find section end (next header)
    if header_line_index != -1:
        for i in range(header_line_index + 1, len(lines)):
            if lines[i].strip().startswith("#"):
                section_end_index = i
                break
        insertion_index = section_end_index
    else:
        # If no header found, default to end of file
        insertion_index = len(lines)

    # --- 2. Global task scan ---
    for i, line in enumerate(lines):
        result = parse_obsidian_line(line, i)
        if result:
            key, data = result
            tasks[key] = data

    return tasks, lines, mod_time, insertion_index
