import sys
import os

# 确保我们可以从当前目录导入
sys.path.append(os.getcwd())

try:
    from sync_core import SyncCore
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

class MockStateManager:
    pass

# 使用模拟 SM 实例化真实的 SyncCore
scanner = SyncCore(MockStateManager())

# 覆盖 capture_block？不，我想测试真实的那个。
# SyncCore.capture_block 是我修改过的。

print("--- Test Case: Header Swallowing (Real SyncCore) ---")
# 场景：任务 -> 空行 -> 标题（可能有缩进？）
# 如果标题未缩进，get_indent=0。如果 base_indent=0。0 > 0 False。中断。
# 如果标题已缩进？
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
