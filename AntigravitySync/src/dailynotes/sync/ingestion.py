import os
import re
import datetime
import random
import string
from typing import Dict
from config import Config
from ..utils import Logger, FileUtils
from .parsing import capture_block, clean_task_text, normalize_block_content, get_indent_depth
from .rendering import format_line, inject_into_task_section

def generate_block_id():
    return '^' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

def scan_all_source_tasks(project_map, sm) -> Dict[str, Dict]:
    # Need to run scan_projects before this? No, project_map is passed in.
    # self.scan_projects() # Caller handles this.
    
    source_data_by_date = {}
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    for root, dirs, files in os.walk(Config.ROOT_DIR):
        dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
        if FileUtils.is_excluded(root): continue
        curr_proj = None
        temp = root
        while temp.startswith(Config.ROOT_DIR):
            if temp in project_map: curr_proj = project_map[temp]; break
            temp = os.path.dirname(temp)
            if temp == os.path.dirname(temp): break
        if not curr_proj: continue
        for f in files:
            if not f.endswith('.md'): continue
            path = os.path.join(root, f)
            lines = FileUtils.read_file(path)
            if not lines: continue
            mod = False
            fname = os.path.splitext(f)[0]
            i = 0

            in_task_section = False
            current_section_date = None
            seen_section_dates = set()
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                if stripped == '# Tasks':
                    in_task_section = True;
                    current_section_date = None;
                    seen_section_dates.clear();
                    i += 1;
                    continue
                if stripped == '----------':
                    in_task_section = False;
                    current_section_date = None;
                    i += 1;
                    continue
                if not in_task_section: i += 1; continue
                header_match = re.match(r'^#+\s*\[\[\s*(\d{4}-\d{2}-\d{2})\s*\]\]', stripped)
                if header_match:
                    date_str = header_match.group(1)
                    if date_str in seen_section_dates:
                        Logger.info(f"   🔍 发现重复标题 {date_str}，将触发重组...");
                        mod = True
                    else:
                        seen_section_dates.add(date_str)
                    current_section_date = date_str;
                    i += 1;
                    continue
                if stripped.startswith('#'): current_section_date = None; i += 1; continue
                if not re.match(r'^\s*-\s*\[.\]', line): i += 1; continue
                task_date = None
                if current_section_date:
                    task_date = current_section_date
                else:
                    date_match = re.search(r'[📅✅]\s*(\d{4}-\d{2}-\d{2})', line)
                    if date_match:
                        task_date = date_match.group(1)
                    else:
                        link_match = re.search(r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\||\]\])', line)
                        if link_match: task_date = link_match.group(1)
                is_in_inbox_area = (current_section_date is None)
                if is_in_inbox_area and not task_date: i += 1; continue
                if not task_date: task_date = today_str; mod = True

                # [MODIFIED] Use visual depth
                indent = get_indent_depth(line)

                status_match = re.search(r'-\s*\[(.)\]', line)
                st = status_match.group(1) if status_match else ' '
                id_m = re.search(r'\^([a-zA-Z0-9]{6,7})\s*$', line)
                bid = id_m.group(1) if id_m else None
                if not bid:
                    raw_block, _ = capture_block(lines, i)
                    temp_clean = clean_task_text(line, None, fname)
                    temp_clean = re.sub(r'\s+\^?[a-zA-Z0-9]*$', '', temp_clean).strip()
                    combined_body = normalize_block_content(raw_block[1:])
                    temp_combined_text = temp_clean + "|||" + combined_body
                    recovery_hash = sm.calc_hash(st, temp_combined_text)
                    found_id = sm.find_id_by_hash(path, recovery_hash)
                    if found_id:
                        Logger.info(f"   🚑 [RESCUE] 指纹匹配成功! '{temp_clean[:10]}...' -> 复活 ID: {found_id}")
                        bid = found_id;
                        mod = True
                    else:
                        bid = generate_block_id().replace('^', '');
                        mod = True
                clean_txt = clean_task_text(line, bid, context_name=fname)
                dates_pattern = r'([📅✅]\s*\d{4}-\d{2}-\d{2}|\[\[\d{4}-\d{2}-\d{2}(?:#\^[a-zA-Z0-9]+)?(?:\|[📅⮐])?\]\])'
                dates = " ".join(re.findall(dates_pattern, line))
                if current_section_date and current_section_date not in dates: dates = f"[[{task_date}]]"; mod = True
                if task_date not in line and not dates: dates = f"[[{task_date}]]"; mod = True
                new_line = format_line(indent, st, clean_txt, dates, fname, bid, False)
                if new_line.strip() != line.strip(): lines[i] = new_line; mod = True

                # [TIME GATE]
                if task_date < Config.SYNC_START_DATE:
                    _, consumed = capture_block(lines, i)
                    i += consumed
                    continue

                block, consumed = capture_block(lines, i)
                combined_text = clean_txt + "|||" + normalize_block_content(block[1:])
                content_hash = sm.calc_hash(st, combined_text)
                if task_date not in source_data_by_date: source_data_by_date[task_date] = {}
                source_data_by_date[task_date][bid] = {
                    'proj': curr_proj, 'bid': bid, 'pure': clean_txt, 'status': st,
                    'path': path, 'fname': fname, 'raw': block, 'hash': content_hash, 'indent': indent,
                    'dates': dates, 'is_quoted': False
                }
                i += consumed
            if mod:
                lines = inject_into_task_section(lines, [])
                # [CHECK] 比对磁盘文件，防止死循环
                orig = FileUtils.read_file(path)
                new_c = "".join(lines)
                old_c = "".join(orig) if orig else ""
                if new_c != old_c:
                    Logger.info(f"   💾 [WRITE] 自动格式化源文件 (Scan): {os.path.basename(path)}")
                    FileUtils.write_file(path, lines)
    for delta in range(3):
        target_d = datetime.date.today() - datetime.timedelta(days=delta)
        target_s = target_d.strftime('%Y-%m-%d')
        if target_s not in source_data_by_date: source_data_by_date[target_s] = {}
    return source_data_by_date
