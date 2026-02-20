import sys
import os

# add src to path so we can import
sys.path.append(os.path.join(os.getcwd(), 'src'))
from dailynotes.sync.discovery import scan_projects

project_map, project_path_map, file_path_map = scan_projects()
print("Project Path Map values:")
for k, v in list(project_path_map.items())[:10]:
    print(f"{k} -> {v}")

