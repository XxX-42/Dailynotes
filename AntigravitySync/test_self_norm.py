import sys
import os
import unicodedata

# add src to path so we can import
sys.path.append(os.path.join(os.getcwd(), 'src'))
from dailynotes.sync.discovery import scan_projects

project_map, project_path_map, file_path_map = scan_projects()

# Get a real file path from the map to test
sample_name = list(project_path_map.keys())[0]
sample_path = project_path_map[sample_name]

# Now let's pretend filepath comes from somewhere else and might be in a different normalization form, or exactly the same
filepath_test = unicodedata.normalize('NFD', sample_path) # simulate mac os behavior

self_project_name = None
norm_filepath = unicodedata.normalize('NFC', filepath_test)
for p_name, p_path in project_path_map.items():
    if unicodedata.normalize('NFC', p_path) == norm_filepath:
        self_project_name = p_name
        break

print(f"Original Name: {sample_name}")
print(f"Match logic result: {self_project_name}")

