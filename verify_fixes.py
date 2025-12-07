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

# --- Test 1: Ping-Pong Loop (Ghost Bullets) ---
print("\n[Test 1] Ghost Bullet Filtering")
print("Input Block: Normal line, Empty line, Dash line, Dash-Space line")
block = [
    "- [ ] Normal Task",
    "",        # Empty
    "-",       # Just dash
    "- ",      # Dash space
    "  - "     # Indented dash space
]
normalized = sync.normalize_block_content(block)
print(f"Normalized Block Content: {repr(normalized)}")

if normalized == "Normal Task":
    print("PASS: Ghost bullets filtered from Block Content.")
else:
    print(f"FAIL: Ghost bullets remain! Got: {repr(normalized)}")

# Test Child Normalization
print("Input Children: ['- Child', '', '- ', '-']")
children = sync.normalize_child_lines(['- Child', '', '- ', '-'], 0, as_quoted=False)
print("Normalized Children output:")
for c in children: print(repr(c))

if len(children) == 1 and "Child" in children[0]:
    print("PASS: Ghost bullets filtered from Child Lines.")
else:
    print(f"FAIL: Children not filtered correctly. Len={len(children)}")


# --- Test 2: Header Swallowing ---
print("\n[Test 2] Header Swallowing (Neutered Cleanup)")
lines_with_header = [
    "# Day planner\n",
    "\n",
    "## [[Project A]]",   # Empty header
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


# --- Test 3: Format Collapse (Conservative Clean) ---
print("\n[Test 3] Format Collapse protection")
raw_line = "  - [ ] [[Project|Link]] Task Name ^123456"
print(f"Raw: '{raw_line}'")

# Old aggressive clean would strip 'Link' or maybe do weird things? 
# We just want to check if it's cleaner now.
cleaned = sync.clean_task_text(raw_line, "123456", "Project")
print(f"Cleaned: '{cleaned}'")

# Expected: "Task Name" (Link removed because context matches, Status removed, ID removed)
if cleaned == "Task Name":
    print("PASS: Cleaned correctly.")
else:
    print(f"FAIL: Cleaned text unexpected: '{cleaned}'")

# Check regex for space preservation
raw_spaced = "- [ ] Task  With   Spaces"
cleaned_spaced = sync.clean_task_text(raw_spaced)
print(f"Cleaned Spaced: '{cleaned_spaced}'")
if "Task  With   Spaces" in cleaned_spaced:
    print("PASS: Internal spaces preserved.")
else:
    print("FAIL: Internal spaces collapsed.")

# --- Test 4: Format Loop Fix (Neutered _enforce_hyphen_space) ---
print("\n[Test 4] Format Loop Fix (Neutered _enforce_hyphen_space)")
from format_core import FormatCore

# Case A: "-Text" (Should be LEFT ALONE by this function now)
# The brute force is gone. It relies on Global Cleaner now.
bad_hyphen = "\t-Text"
fixed_hyphen = FormatCore._enforce_hyphen_space(bad_hyphen)
print(f"Input: '{bad_hyphen}' -> Output: '{fixed_hyphen}'")
if fixed_hyphen == bad_hyphen:
    print("PASS: Bad hyphen ignored by neutered function (will be caught by global cleaner).")
else:
    print(f"FAIL: Function still modifying text! Got '{fixed_hyphen}'")

# Case B: "\t-" (Should be IGNORED)
empty_hyphen = "\t-"
fixed_empty = FormatCore._enforce_hyphen_space(empty_hyphen)
print(f"Input: '{empty_hyphen}' -> Output: '{fixed_empty}'")
if fixed_empty == empty_hyphen:
    print("PASS: Trailing bullet IGNORED.")
else:
    print(f"FAIL: Function modifying trailing bullet! Got '{fixed_empty}'")

