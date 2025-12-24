import re
import unicodedata

def get_indent_depth(line):
    """
    [Helper] 统一计算缩进视觉深度 (Tab=4 spaces)
    解决 Tab/Space 混用导致的层级判断失效问题。
    """
    no_quote = re.sub(r'^>\s?', '', line)
    expanded = no_quote.expandtabs(4)
    return len(expanded) - len(expanded.lstrip())

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
    """
    [v10.7 Aggressive Clean]
    增加通用尾部清理，防止救援模式下残缺 ID (如 ^04cn) 未被清除导致 ID 重复。
    [v10.8 Time Strip] 增加时间段剥离，防止 07:00 - 11:20 污染源文件。
    """
    # 1. 移除 Checkbox (保留)
    line = re.sub(r'^\s*-\s*\[.\]\s?', '', line)

    # === [新增] 2. 移除 Day Planner 时间段 ===
    # 匹配: "07:00 " 或 "07:00 - 11:20 "
    # 逻辑: 只有位于行首（去除 checkbox 后）的时间才会被视为调度信息
    line = re.sub(r'^\s*\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?\s+', '', line)

    clean_text = line

    # 3. 移除指定块 ID (原逻辑)
    if block_id:
        clean_text = re.sub(rf'(?<=\s)\^{re.escape(block_id)}\s*$', '', clean_text)

    # 4. 通用尾部清理 (原逻辑)
    clean_text = re.sub(r'\s+\^[a-zA-Z0-9]*$', '', clean_text)

    # 5. 移除日期链接 (原逻辑)
    clean_text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}(?:#\^[a-zA-Z0-9]+)?(?:\|.*?)?\]\]', '', clean_text)

    # 6. 移除文件自身链接 (原逻辑)
    if context_name:
        clean_text = re.sub(rf'\[\[{re.escape(context_name)}(?:#\^[a-zA-Z0-9]+)?(?:\|.*?)?\]\]', '', clean_text)

    # 7. 移除 Emoji 日期 (原逻辑)
    clean_text = re.sub(r'[📅✅]\s*\d{4}-\d{2}-\d{2}', '', clean_text)
    clean_text = re.sub(r'\(connect::.*?\)', '', clean_text)

    return clean_text.strip()

def normalize_block_content(block_lines):
    normalized = []
    for line in block_lines:
        clean = re.sub(r'^[\s>]+', '', line).strip()
        if not clean or clean in ['-', '- ']: continue
        normalized.append(clean)
    return "\n".join(normalized) + "\n"

def capture_block(lines, start_idx):
    """
    [v14.2 Indent-Priority Capture]
    修复双重缩进任务 (- [ ]) 被截断的 Bug。
    核心逻辑变更：确立【缩进霸权】。
    只要当前行缩进 > 父级缩进，无条件视为子内容，跳过任何内容检查（如 # 或 ---）。
    只有缩进 <= 父级时，才进行结束判定。
    """
    if start_idx >= len(lines): return [], 0

    # 1. 获取父级（锚点）的视觉缩进深度
    base_depth = get_indent_depth(lines[start_idx])

    block = [lines[start_idx]]
    consumed = 1
    j = start_idx + 1

    while j < len(lines):
        nl = lines[j]

        # 1. 空行处理：始终保留，不作为判定依据
        if not nl.strip():
            block.append(nl)
            consumed += 1
            j += 1
            continue

        # 2. 强分隔符：唯一的例外，必须截断
        if nl.strip() == '----------': break

        # 3. 计算当前行缩进
        curr_depth = get_indent_depth(nl)

        # === [核心修复] 缩进优先原则 ===
        # 如果当前行比父级缩进深，它就是子元素。
        # 不检查它是否以 '#' 开头，也不做任何正则清洗。
        # 这保证了 `      - [ ]` 这种结构绝对会被捕获。
        if curr_depth > base_depth:
            block.append(nl)
            consumed += 1
            j += 1
            continue

        # 4. 只有当缩进 <= 父级时，才视为潜在的结束
        # 此时遇到同级任务、同级标题或更浅的内容，均结束捕获
        break

    return block, consumed

def extract_routing_target(line, file_path_map):
    clean = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', line)
    matches = re.findall(r'\[\[(.*?)\]\]', clean)
    for match in matches:
        pot = match.split('|')[0]
        pot = unicodedata.normalize('NFC', pot)
        if pot in file_path_map: return file_path_map[pot]
    return None
