import sys
import os

# add src to path so we can import
sys.path.append(os.path.join(os.getcwd(), 'src'))
from dailynotes.sync.engine import SyncCore

class MockSM:
    def __init__(self):
        self.state = {}

core = SyncCore(MockSM())
core.initialize_registry()

line = '- [x] 10:22 - 14:37<span id="5utl1t" data-timestamps="10:21:20,10:22:00,10:22:31,10:36:59,10:41:04,14:24:09,14:29:24,14:35:43,14:36:15"></span> #B [[测试/测试|测试]]'

from dailynotes.sync.parsing import extract_routing_info
target_path, link_text = extract_routing_info(line, core.file_path_map)
print(f"Extraction result target_path: {target_path}")

if target_path:
    # This simulates what engine.py does
    p_name = core.calculate_nearest_project(target_path)
    print(f"Calculated nearest project from {target_path} -> {p_name}")

