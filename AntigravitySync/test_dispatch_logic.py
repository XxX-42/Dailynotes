import sys
import os

sys.path.append(os.path.join(os.getcwd(), 'src'))
from dailynotes.sync.discovery import scan_projects

project_map, project_path_map, file_path_map = scan_projects()
for p_name, p_path in project_path_map.items():
    if "测试" in p_path:
        print(f"FOUND IN PROJECT MAP: {p_name} -> {p_path}")
