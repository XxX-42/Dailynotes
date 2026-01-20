import re
import unicodedata

# [P3 FIX] Pre-compiled regex patterns for performance
_RE_QUOTE_PREFIX = re.compile(r'^>\s?')
_RE_STATUS_INDENT = re.compile(r'^[\s>]*-\s*\[.\]')
_RE_TIME_RANGE = re.compile(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}')
_RE_TIME_SINGLE = re.compile(r'\d{1,2}:\d{2}')
_RE_BLOCK_ID = re.compile(r'\^[a-zA-Z0-9]{6,}\s*$')
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
    
    # 3. remove ID
    if block_id:
        clean_text = re.sub(r'\^' + re.escape(block_id) + r'\s*$', '', clean_text)
    else:
        clean_text = re.sub(r'\^[a-zA-Z0-9]{6,}\s*$', '', clean_text)
        
    # 4. remove return links
    clean_text = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', clean_text)
    
    # 5. remove date links
    clean_text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}]]', '', clean_text)
    # remove emoji date
    clean_text = re.sub(r'📅\s?\[\[\d{4}-\d{2}-\d{2}]]', '', clean_text)

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
        clean = re.sub(r'^[\s>]+', '', line).strip()
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
        pot = unicodedata.normalize('NFC', pot)
        
        if pot in file_path_map:
            return file_path_map[pot], raw_text
            
    return None, None

def extract_routing_target(line, file_path_map):
    """
    Compatibility wrapper for extract_routing_info.
    Returns just the path.
    """
    path, _ = extract_routing_info(line, file_path_map)
    return path
