import re
import unicodedata

# [P3 FIX] Pre-compiled regex patterns for performance
_RE_QUOTE_PREFIX = re.compile(r'^>\s?')
_RE_STATUS_INDENT = re.compile(r'^[\s>]*-\s*\[.\]')
_RE_TIME_RANGE = re.compile(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}')
_RE_TIME_SINGLE = re.compile(r'\d{1,2}:\d{2}')
_RE_BLOCK_ID = re.compile(r'(?:\^[a-zA-Z0-9]{6,}|<span id="[a-zA-Z0-9]{6,}"(?: data-timestamps="[^"]*")?></span>)\s*$')
_RE_RETURN_LINK = re.compile(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]')
_RE_DATE_LINK = re.compile(r'\[\[\d{4}-\d{2}-\d{2}]]')
_RE_EMOJI_DATE = re.compile(r'📅\s?\[\[\d{4}-\d{2}-\d{2}]]')
_RE_MULTI_SPACE = re.compile(r'\s+')
_RE_WIKI_LINK = re.compile(r'\[\[(.*?)\]\]')
_RE_MAIN_TAG = re.compile(r'\bmain\b')

def _get_indent_depth(line):
    no_quote = _RE_QUOTE_PREFIX.sub('', line)
    expanded = no_quote.expandtabs(4)
    return len(expanded) - len(expanded.lstrip())

# Alias for external use
get_indent_depth = _get_indent_depth

def parse_yaml_tags(lines):
    tags = []
    if not lines or lines[0].strip() != '---': return []
    in_yaml = False
    for i, line in enumerate(lines):
        if i == 0: in_yaml = True; continue
        if line.strip() == '---': break
        if in_yaml and ('tags:' in line or 'main' in line):
            if re.search(r'\bmain\b', line): tags.append('main')
    return tags

def clean_task_text(line, block_id=None, context_name=None):
    # 1. remove status and indent
    clean_text = re.sub(r'^[\s>]*-\s*\[.\]', '', line)
    
    # 2. remove time (00:00 - 00:00)
    clean_text = re.sub(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', '', clean_text)
    clean_text = re.sub(r'\d{1,2}:\d{2}', '', clean_text)
    
    # 3. remove ID (^xxxxxx, or <span id="xxx" data-timestamps="..."></span>)
    if block_id:
        clean_text = re.sub(r'\^' + re.escape(block_id) + r'\s*$', '', clean_text)
        clean_text = re.sub(r'<span id="' + re.escape(block_id) + r'"(?: data-timestamps="[^"]*")?></span>', '', clean_text)
    else:
        clean_text = re.sub(r'\^[a-zA-Z0-9]{6,}\s*$', '', clean_text)
        clean_text = re.sub(r'<span id="[a-zA-Z0-9]{6,}"(?: data-timestamps="[^"]*")?></span>', '', clean_text)
        
    # 4. remove return links
    clean_text = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', clean_text)
    
    # 5. remove date links
    clean_text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}]]', '', clean_text)
    # remove emoji date
    clean_text = re.sub(r'📅\s?\[\[\d{4}-\d{2}-\d{2}]]', '', clean_text)

    # 5.5 [FIX] Remove routing markers like "## [[ProjectName]]"
    clean_text = re.sub(r'##\s*\[\[[^\]]+\]\]', '', clean_text)

    # 6. [NEW] Remove self-referencing project links if context is known
    # If we are syncing to "ProjectA.md", remove "[[ProjectA]]" from the text
    if context_name:
        # Normalize context name to handle NFC/NFD potential mismatch
        c_name = unicodedata.normalize('NFC', context_name)
        # Regex to match [[ContextName]] or [[ContextName|Alias]]
        # We use re.escape to handle filenames with special regex chars
        pattern = rf'\[\[{re.escape(c_name)}(?:\|.*?)?\]\]'
        clean_text = re.sub(pattern, '', clean_text)

    # 7. Final cleanup of extra spaces
    return re.sub(r'\s+', ' ', clean_text).strip()

def normalize_block_content(block_lines):
    normalized = []
    for line in block_lines:
        # [FIX] 使用 lstrip() 而非 strip()，保留尾部空格以支持 Obsidian "- " 列表语法
        clean = re.sub(r'^[\s>]+', '', line).lstrip()
        if not clean or clean in ['-', '- ']: continue
        normalized.append(clean)
    return "\n".join(normalized) + "\n"

def capture_block(lines, start_idx):
    parent_indent = _get_indent_depth(lines[start_idx])
    block = [lines[start_idx]]
    consumed = 1
    
    # [P2 FIX] Track consecutive empty lines to prevent infinite block extension
    consecutive_empty = 0
    MAX_CONSECUTIVE_EMPTY = 2
    
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        if not line.strip():  # Empty line
            consecutive_empty += 1
            if consecutive_empty > MAX_CONSECUTIVE_EMPTY:
                break  # Too many empty lines, end block
            block.append(line)
            consumed += 1
            continue
        
        # Reset counter on non-empty line
        consecutive_empty = 0
             
        curr_indent = _get_indent_depth(line)
        if curr_indent > parent_indent:
            block.append(line)
            consumed += 1
        else:
            break
            
    return block, consumed

def extract_routing_info(line, file_path_map):
    """
    Extracts routing target from a line.
    Returns: (absolute_path_to_file, raw_link_text)
    """
    # Remove return links first to avoid false positives
    clean = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', line)
    
    matches = re.finditer(r'\[\[(.*?)\]\]', clean)
    for m in matches:
        raw_text = m.group(0) # [[WikiLink]]
        inner = m.group(1)
        pot = inner.split('|')[0].split('#')[0]
        # In Obsidian, `[[Folder/File|Alias]]` points to `File`. But our `file_path_map` 
        # is keyed ONLY by `stem` (i.e. `File`). We must extract just the basename.
        import os
        pot_basename = os.path.basename(pot)
        pot_basename = unicodedata.normalize('NFC', pot_basename)
        
        if pot_basename in file_path_map:
            return file_path_map[pot_basename], raw_text
            
    return None, None

def extract_routing_target(line, file_path_map):
    """
    Compatibility wrapper for extract_routing_info.
    Returns just the path.
    """
    path, _ = extract_routing_info(line, file_path_map)
    return path


def generate_block_id() -> str:
    """Generate a unique block ID."""
    import random
    import string
    return '^' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))


def parse_file_tasks(filepath: str, lines: list, project_name: str, sm, 
                     write_back: bool = True) -> tuple:
    """
    [v1.8.1 DRY] Central parsing function for extracting tasks from a markdown file.
    
    This is the SINGLE SOURCE OF TRUTH for file parsing logic.
    Used by TaskRegistry for both initial scan and incremental updates.
    
    Args:
        filepath: Absolute path to the .md file
        lines: List of line strings (already read from file)
        project_name: The project this file belongs to
        sm: StateManager for hash calculations
        write_back: If True, write modified lines back to file
        
    Returns:
        Tuple of (tasks_list, modified_lines, was_modified)
        - tasks_list: List of task dictionaries
        - modified_lines: The (potentially modified) lines
        - was_modified: Boolean indicating if lines were changed
    """
    import os
    import datetime
    from config import Config
    from ..utils import Logger, FileUtils
    
    # Lazy import to avoid circular dependency
    from .rendering import format_line, inject_into_task_section
    
    if not lines:
        return [], lines, False
    
    tasks = []
    mod = False
    fname = os.path.splitext(os.path.basename(filepath))[0]
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    i = 0
    in_task_section = False
    current_section_date = None
    seen_section_dates = set()
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Detect section markers
        if stripped == '# Tasks':
            in_task_section = True
            current_section_date = None
            seen_section_dates.clear()
            i += 1
            continue
        
        if stripped == '----------':
            in_task_section = False
            current_section_date = None
            i += 1
            continue
        
        if not in_task_section:
            i += 1
            continue
        
        # Check for date headers
        header_match = re.match(r'^#+\s*\[\[\s*(\d{4}-\d{2}-\d{2})\s*\]\]', stripped)
        if header_match:
            date_str = header_match.group(1)
            if date_str in seen_section_dates:
                Logger.info(f"   🔍 发现重复标题 {date_str}，将触发重组...")
                mod = True
            else:
                seen_section_dates.add(date_str)
            current_section_date = date_str
            i += 1
            continue
        
        if stripped.startswith('#'):
            current_section_date = None
            i += 1
            continue
        
        # Check for task lines
        if not re.match(r'^\s*-\s*\[.\]', line):
            i += 1
            continue
        
        # Determine task date
        task_date = None
        if current_section_date:
            task_date = current_section_date
        else:
            date_match = re.search(r'[📅✅]\s*(\d{4}-\d{2}-\d{2})', line)
            if date_match:
                task_date = date_match.group(1)
            else:
                link_match = re.search(r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\||\]\])', line)
                if link_match:
                    task_date = link_match.group(1)
        
        is_in_inbox_area = (current_section_date is None)
        if is_in_inbox_area and not task_date:
            i += 1
            continue
        
        if not task_date:
            task_date = today_str
            mod = True
        
        # Parse task properties
        indent = get_indent_depth(line)
        status_match = re.search(r'-\s*\[(.)\]', line)
        st = status_match.group(1) if status_match else ' '
        
        # Extract or generate block ID
        id_m = re.search(r'(?:\^([a-zA-Z0-9]{6,7})|<span id="([a-zA-Z0-9]{6,7})"(?: data-timestamps="[^"]*")?></span>)', line)
        bid = (id_m.group(1) or id_m.group(2)) if id_m else None
        
        if not bid:
            raw_block, _ = capture_block(lines, i)
            temp_clean = clean_task_text(line, None, fname)
            temp_clean = re.sub(r'\s+\^?[a-zA-Z0-9]*$', '', temp_clean).strip()
            combined_body = normalize_block_content(raw_block[1:])
            temp_combined_text = temp_clean + "|||" + combined_body
            recovery_hash = sm.calc_hash(st, temp_combined_text)
            found_id = sm.find_id_by_hash(filepath, recovery_hash)
            
            if found_id:
                Logger.info(f"   🚑 [RESCUE] 指纹匹配成功! '{temp_clean[:10]}...' -> 复活 ID: {found_id}")
                bid = found_id
                mod = True
            else:
                bid = generate_block_id().replace('^', '')
                mod = True
        
        # Clean task text
        clean_txt = clean_task_text(line, bid, context_name=fname)
        dates_pattern = r'([📅✅]\s*\d{4}-\d{2}-\d{2}|\[\[\d{4}-\d{2}-\d{2}(?:#\^[a-zA-Z0-9]+)?(?:\|[📅⮐])?\]\])'
        dates = " ".join(re.findall(dates_pattern, line))
        
        if current_section_date and current_section_date not in dates:
            dates = f"[[{task_date}]]"
            mod = True
        if task_date not in line and not dates:
            dates = f"[[{task_date}]]"
            mod = True
        
        # Format the line
        new_line = format_line(indent, st, clean_txt, dates, fname, bid, False)
        if new_line.strip() != line.strip():
            lines[i] = new_line
            mod = True
        
        # TIME GATE: Skip tasks before sync start date
        if task_date < Config.SYNC_START_DATE:
            _, consumed = capture_block(lines, i)
            i += consumed
            continue
        
        # Capture full block and build task dict
        block, consumed = capture_block(lines, i)
        combined_text = clean_txt + "|||" + normalize_block_content(block[1:])
        content_hash = sm.calc_hash(st, combined_text)
        
        tasks.append({
            'proj': project_name,
            'bid': bid,
            'pure': clean_txt,
            'status': st,
            'path': filepath,
            'fname': fname,
            'raw': block,
            'hash': content_hash,
            'indent': indent,
            'dates': dates,
            'is_quoted': False,
            '_task_date': task_date  # Internal field for date indexing
        })
        
        i += consumed
    
    # Write back if modified and requested
    if mod and write_back:
        lines = inject_into_task_section(lines, [])
        orig = FileUtils.read_file(filepath)
        new_c = "".join(lines)
        old_c = "".join(orig) if orig else ""
        if new_c != old_c:
            Logger.info(f"   💾 [WRITE] 自动格式化源文件: {os.path.basename(filepath)}")
            FileUtils.write_file(filepath, lines)
    
    return tasks, lines, mod
