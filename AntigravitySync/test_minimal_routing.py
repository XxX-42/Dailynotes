import sys
import os

# add src to path so we can import
sys.path.append(os.path.join(os.getcwd(), 'src'))
from dailynotes.sync.discovery import scan_projects
from dailynotes.sync.parsing import extract_routing_info
from config import Config

project_map, project_path_map, file_path_map = scan_projects()
line = '- [x] 10:22 - 14:37<span id="5utl1t" data-timestamps="10:21:20,10:22:00,10:22:31,10:36:59,10:41:04,14:24:09,14:29:24,14:35:43,14:36:15"></span> #B [[测试/测试|测试]]'

target_path, link_text = extract_routing_info(line, file_path_map)
print(f"[1] Extracted Path: {target_path}")

def calculate_nearest_project(routing_path):
    if not routing_path: return None
    curr_search = os.path.dirname(routing_path)
    # Traverse upwards
    while curr_search.startswith(Config.ROOT_DIR):
        if curr_search in project_map:
            return project_map[curr_search]
        parent = os.path.dirname(curr_search)
        if parent == curr_search: break 
        curr_search = parent
    return None

if target_path:
    # This simulates what engine.py does to calculate nearest project
    p_name = calculate_nearest_project(target_path)
    print(f"[2] Resolved Project Scope: {p_name}")

