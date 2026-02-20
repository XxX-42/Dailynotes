import sys
import os

sys.path.append(os.path.join(os.getcwd(), 'src'))
from dailynotes.sync.discovery import scan_projects

project_map, project_path_map, file_path_map = scan_projects()
print("Does '测试' exist in project_path_map keys?")
print("测试" in project_path_map)

