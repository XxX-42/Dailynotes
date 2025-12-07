import sys
import os
import re

# Ensure we can import from current directory
sys.path.append(os.getcwd())

from sync_core import SyncCore
from config import Config

class MockStateManager:
    def calc_hash(self, status, content):
        return f"HASH({content})"

print("\n=== VERIFICATION: SyncCore Critical Fixes ===")
sync = SyncCore(MockStateManager())

# --- 测试 1: Ping-Pong 循环（幽灵子弹）---
print("\n[Test 1] Ghost Bullet Filtering")
print("Input Block: Normal line, Empty line, Dash line, Dash-Space line")
block = [
    "- [ ] Normal Task",
    "",        # 空
    "-",       # 仅连字符
    "- ",      # 连字符空格
    "  - "     # 缩进连字符空格
]
normalized = sync.normalize_block_content(block)
print(f"Normalized Block Content: {repr(normalized)}")

if normalized == "Normal Task":
    print("PASS: Ghost bullets filtered from Block Content.")
else:
    print(f"FAIL: Ghost bullets remain! Got: {repr(normalized)}")

# 测试子项标准化
print("Input Children: ['- Child', '', '- ', '-']")
children = sync.normalize_child_lines(['- Child', '', '- ', '-'], 0, as_quoted=False)
print("Normalized Children output:")
for c in children: print(repr(c))

if len(children) == 1 and "Child" in children[0]:
    print("PASS: Ghost bullets filtered from Child Lines.")
else:
    print(f"FAIL: Children not filtered correctly. Len={len(children)}")


# --- 测试 2: 标题吞噬 ---
print("\n[Test 2] Header Swallowing (Neutered Cleanup)")
lines_with_header = [
    "# Day planner\n",
    "\n",
    "## [[Project A]]",   # 空标题
    "\n",
    "# Journey\n"
]
print("Input Lines (Header Check):")
for l in lines_with_header: print(repr(l))

cleaned_lines, modified = sync.cleanup_empty_headers(list(lines_with_header), "2025-01-01")
print(f"Modified: {modified}")
print("Output Lines:")
for l in cleaned_lines: print(repr(l))

if "## [[Project A]]" in [l.strip() for l in cleaned_lines]:
    print("PASS: Empty header preserved.")
else:
    print("FAIL: Header was deleted!")


# --- 测试 3: 格式崩溃保护（保守清理）---
print("\n[Test 3] Format Collapse protection")
raw_line = "  - [ ] [[Project|Link]] Task Name ^123456"
print(f"Raw: '{raw_line}'")

# 旧的激进清理会剥离 'Link' 或者可能做一些奇怪的事情？
# 我们只想检查现在是否更干净。
cleaned = sync.clean_task_text(raw_line, "123456", "Project")
print(f"Cleaned: '{cleaned}'")

# 预期："Task Name"（链接已移除因为上下文匹配，状态已移除，ID 已移除）
if cleaned == "Task Name":
    print("PASS: Cleaned correctly.")
else:
    print(f"FAIL: Cleaned text unexpected: '{cleaned}'")

# 检查正则是否保留空格
raw_spaced = "- [ ] Task  With   Spaces"
cleaned_spaced = sync.clean_task_text(raw_spaced)
print(f"Cleaned Spaced: '{cleaned_spaced}'")
if "Task  With   Spaces" in cleaned_spaced:
    print("PASS: Internal spaces preserved.")
else:
    print("FAIL: Internal spaces collapsed.")

# --- 测试 4: 格式循环修复（阉割版 _enforce_hyphen_space）---
print("\n[Test 4] Format Loop Fix (Neutered _enforce_hyphen_space)")
from format_core import FormatCore

# 情况 A: "-Text"（现在该函数应保持原样）
# 暴力方式已移除。现在依赖于全局清理器。
bad_hyphen = "\t-Text"
fixed_hyphen = FormatCore._enforce_hyphen_space(bad_hyphen)
print(f"Input: '{bad_hyphen}' -> Output: '{fixed_hyphen}'")
if fixed_hyphen == bad_hyphen:
    print("PASS: Bad hyphen ignored by neutered function (will be caught by global cleaner).")
else:
    print(f"FAIL: Function still modifying text! Got '{fixed_hyphen}'")

# 情况 B: "\t-"（应被忽略）
empty_hyphen = "\t-"
fixed_empty = FormatCore._enforce_hyphen_space(empty_hyphen)
print(f"Input: '{empty_hyphen}' -> Output: '{fixed_empty}'")
if fixed_empty == empty_hyphen:
    print("PASS: Trailing bullet IGNORED.")
else:
    print(f"FAIL: Function modifying trailing bullet! Got '{fixed_empty}'")

