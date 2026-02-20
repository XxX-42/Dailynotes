import sys
import os

sys.path.append(os.path.join(os.getcwd(), 'src'))
from dailynotes.sync.discovery import scan_projects
from dailynotes.sync.parsing import extract_routing_info
from dailynotes.sync.engine import SyncCore
from config import Config

class MockSM:
    def __init__(self):
        self.state = {}

core = SyncCore(MockSM())

# 1. Simulate the discovery phase
core.project_map, core.project_path_map, core.file_path_map = scan_projects()

# 2. Simulate the routing info extraction with Path-Prefixed WikiLink
line = '- [x] 10:22 - 14:37<span id="xxx"></span> #B [[测试/测试|测试]]'
target_path, link_text = extract_routing_info(line, core.file_path_map)

print(f"Extraction result path: {target_path}")

# 3. Simulate Calculate Nearest Project
if target_path:
    # Because of the fix in parsing + fix in discovery, target_path is now the REAL MAIN 测试.md
    p_name = core.calculate_nearest_project(target_path)
    print(f"Calculated target project namespace (Should be '测试'): {p_name}")

    if p_name:
        print("✅ SUCCESS: The task will correctly route to its home project, un-fucking the wanderer behavior.")
    else:
        print("❌ FAILED: Still None")
else:
    print("❌ FAILED: No extraction path")

