git pushimport sys
import os
import unicodedata

sys.path.append(os.path.join(os.getcwd(), 'src'))
from dailynotes.sync.parsing import extract_routing_info
from dailynotes.sync.discovery import scan_projects
from config import Config

project_map, project_path_map, file_path_map = scan_projects()
line = '- [x] 10:22 - 14:37<span id="xxx"></span> #B [[测试/测试|测试]]'

target_path, link_text = extract_routing_info(line, file_path_map)
print(f"Extraction result path: {target_path}")

if target_path:
    # 1. Exact direct match
    norm_routing = unicodedata.normalize('NFC', target_path)
    p_name = None
    for k, v in project_path_map.items():
        if unicodedata.normalize('NFC', v) == norm_routing:
            p_name = k
            break
            
    if not p_name:
        curr_search = os.path.dirname(target_path)
        while curr_search.startswith(Config.ROOT_DIR):
            if curr_search in project_map:
                p_name = project_map[curr_search]
                break
            parent = os.path.dirname(curr_search)
            if parent == curr_search: break 
            curr_search = parent
            
    print(f"Calculated target project namespace: {p_name}")

