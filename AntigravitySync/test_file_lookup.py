import sys
import os
import unicodedata

sys.path.append(os.path.join(os.getcwd(), 'src'))
from dailynotes.sync.discovery import scan_projects

project_map, project_path_map, file_path_map = scan_projects()
tests = []
for k, v in file_path_map.items():
    if "测试" in k:
        tests.append(v)
        
print("Paths in file_path_map with '测试' stem:")
for t in tests:
    print(t)
    
