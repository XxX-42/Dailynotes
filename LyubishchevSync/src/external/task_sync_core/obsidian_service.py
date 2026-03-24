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

    # Flexible regex to match task format (now supports optional HTML span tags before time)
    pattern = re.compile(r"^\s*- \[(.)\]\s+(?:(<span[^>]*>.*?</span>)\s*)?(?:(\d{1,2}:\d{2})(?:\s*-\s*(\d{1,2}:\d{2}))?\s+)?(.*)")
    match = pattern.match(line)
    if not match:
        return None

    status, span_tag, start_time, end_time, raw_text = match.groups()

    # Normalize time format
    if not start_time:
        start_time = "00:00"
    else:
        start_time = start_time.zfill(5)  # "9:00" -> "09:00"

    if end_time:
        end_time = end_time.zfill(5)

    target_calendar = DEFAULT_CALENDAR
    
    # [安全增强] 提取展示层专用名称（过滤 HTML 标签、双向链接方括号）
    display_name = raw_text.strip()
    display_name = re.sub(r"<[^>]*>", "", display_name).strip() 
    display_name = re.sub(r"\[\[(.*?)\]\]", r"\1", display_name).strip()

    found_tag = ""

    # [NEW] ICE 模型自适应路由逻辑
    ice_match = re.search(r'(?:🚀ICE:|ICE:)\s*(\d+)', display_name)
    if ice_match:
        try:
            score = int(ice_match.group(1))
            for entry in Config.ICE_THRESHOLDS:
                if score >= entry["min"]:
                    target_calendar = entry["calendar"]
                    found_tag = entry["tag"]
                    break
            # 将 ICE 分数从日历展示名中剔除，保持清爽
            display_name = re.sub(r'(?:🚀ICE:|ICE:)\s*\d+', '', display_name).strip()
        except ValueError:
            pass

    # 如果没有 ICE 分数，则回退到旧的标签映射逻辑
    if not found_tag:
        for mapping in TAG_MAPPINGS:
            tag = mapping["tag"]
            if tag in display_name:
                target_calendar = mapping["calendar"]
                display_name = display_name.replace(tag, "", 1).strip()
                found_tag = tag
                break

    display_name = re.sub(r'\s+', ' ', display_name).strip()

    key = f"{display_name}_{start_time}"
    return key, {
        'name': display_name,
        'start_time': start_time,
        'end_time': end_time,
        'target_calendar': target_calendar,
        'tag': found_tag,
        'span_tag': span_tag,
        'line_index': line_index,
        'raw_text': raw_text.strip(),
        'status': status.lower()
    }


def get_obsidian_state(file_path):
    """
    Get the current state of tasks from an Obsidian file.
    
    Returns:
        tuple: (tasks, lines, mod_time, insertion_index)
    """
    tasks = {}
    if not os.path.exists(file_path):
        return tasks, [], 0, -1

    mod_time = os.path.getmtime(file_path)
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # --- 1. [NEW] 预解析 Insights 表格以获取项目 ICE 权重 ---
    project_ice_map = {}
    in_insights = False
    for line in lines:
        stripped = line.strip().lower().replace(" ", "")
        if stripped == "##insights":
            in_insights = True
            continue
        if in_insights:
            if stripped.startswith("#"): # 结束 Insights 区域
                in_insights = False
                continue
            # 解析表格行: | [[项目名]] | ... | Impact | Conf | Ease | ICE Score |
            if line.strip().startswith("|") and "ice score" not in line.lower() and "---" not in line:
                cols = [c.strip() for c in line.split("|")[1:-1]]
                if len(cols) >= 8:
                    try:
                        p_name = re.sub(r'[\[\]]', '', cols[0]).strip()
                        # 尝试从最后一列提取 ICE Score (可能包含 HTML 标签)
                        ice_text = cols[7]
                        score_m = re.search(r'(\d+)', ice_text)
                        if score_m:
                            project_ice_map[p_name] = int(score_m.group(1))
                    except (ValueError, IndexError):
                        pass

    # --- 2. Locate write region (Anchor) ---
    header_line_index = -1
    section_end_index = len(lines)

    for i, line in enumerate(lines):
        clean_line = line.strip().lower().replace(" ", "")
        # 优先查找 ## Single（新架构），其次 # Day planner（旧架构）
        if line.strip().startswith("#") and ("##single" in clean_line or "#dayplanner" in clean_line):
            header_line_index = i
            break

    if header_line_index != -1:
        for i in range(header_line_index + 1, len(lines)):
            if lines[i].strip().startswith("#"):
                section_end_index = i
                break
        insertion_index = section_end_index
    else:
        insertion_index = len(lines)

    # --- 3. Global task scan (With project context) ---
    current_parent_project = None
    for i, line in enumerate(lines):
        # 跟踪当前所在的项目标题上下文 (### [[Project]])
        h3_m = re.match(r'^###\s+\[\[(.*?)\]\]', line.strip())
        if h3_m:
            current_parent_project = h3_m.group(1).split('|')[0].strip()
        elif line.strip().startswith("## "):
            current_parent_project = None

        result = parse_obsidian_line(line, i)
        if result:
            key, data = result
            
            # 如果这行任务本身没有 ICE 分数，但它处于某个有分数项目的项目标题下
            if "ICE" not in data['raw_text'] and "🚀ICE" not in data['raw_text']:
                project_score = project_ice_map.get(current_parent_project)
                if project_score is not None:
                    # 重新计算该任务的日历和标签
                    for entry in Config.ICE_THRESHOLDS:
                        if project_score >= entry["min"]:
                            data['target_calendar'] = entry["calendar"]
                            data['tag'] = entry["tag"]
                            break
            
            tasks[key] = data

    return tasks, lines, mod_time, insertion_index
