import re
import unicodedata

def _get_indent_depth(line):
    no_quote = re.sub(r'^>\s?', '', line)
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

    # 6. If context_name provided, try to remove context tag ONLY if it looks like a tag (e.g. at end or specific format?)
    # The original sync_core logic didn't aggressively remove context tags here for display, 
    # but `dispatch_project_tasks` logic usually handles tagging explicitly.
    # We will leave simple text cleaning here.
    
    return clean_text.strip()

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
    
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        if not line.strip(): # Empty line, include it but...
             block.append(line)
             consumed += 1
             continue
             
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
