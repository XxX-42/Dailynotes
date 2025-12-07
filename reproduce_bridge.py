import sys
import os

# Ensure we can import from current directory
sys.path.append(os.getcwd())

try:
    from sync_core import SyncCore
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

class MockStateManager:
    pass

# Instantiate real SyncCore with mock SM
scanner = SyncCore(MockStateManager())

# Overwrite capture_block? No, I want to test the REAL one.
# SyncCore.capture_block is what I modified.

print("--- Test Case: Header Swallowing (Real SyncCore) ---")
# Scenario: Task -> Empty Line -> Header (maybe indented?)
# If Header is NOT indented, get_indent=0. If base_indent=0. 0 > 0 False. Breaks.
# If Header IS indented?
lines = [
    "- [ ] Task 1",
    "",
    "  # Log (Indented Header)"
]
print("Input:")
for l in lines: print(repr(l))

block, consumed = scanner.capture_block(lines, 0)
print("\nCaptured:")
for l in block: print(repr(l))

if len(block) > 2:
    print("\n[FAIL] Header was captured!")
else:
    print("\n[PASS] Header was NOT captured.")

print("\n--- Test Case: Divider Swallowing ---")
lines_div = [
    "- [ ] Task 2",
    "",
    "   ---"
]
print("Input:")
for l in lines_div: print(repr(l))
block_div, _ = scanner.capture_block(lines_div, 0)
print("Captured:")
for l in block_div: print(repr(l))

if len(block_div) > 2:
    print("\n[FAIL] Divider was captured!")
else:
    print("\n[PASS] Divider was NOT captured.")
