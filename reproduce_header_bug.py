import sys
import os
sys.path.append(os.getcwd())
from sync_core import SyncCore
from state_manager import StateManager

# Mock State Manager
class MockSM:
    pass

sync = SyncCore(MockSM())

print("--- Test: Quoted Header Guard ---")
lines = [
    "> - Task 1\n",
    ">   - Child 1\n",
    ">     # Log\n",  # INDENTED Header - This SHOULD NOT be captured ideally?
    "> - Task 2\n"
]

print("Input Lines:")
for l in lines: print(repr(l))

block, length = sync.capture_block(lines, 0)
print(f"\nCaptured Length: {length}")
print("Captured Block:")
for l in block: print(repr(l))

# Verification
has_header = any("# Log" in l for l in block)
if has_header:
    print("\n[FAIL] Header was incorrectly captured!")
    sys.exit(1)
else:
    print("\n[PASS] Header was correctly excluded.")
    sys.exit(0)
