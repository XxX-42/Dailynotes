#!/usr/bin/env python3
"""
测试脚本：找出哪个函数在处理 "- " 时删除了空格
"""
import sys
sys.path.insert(0, '/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta/AntigravitySync')

from src.dailynotes.format_core import FormatCore
from src.dailynotes.sync.parsing import normalize_block_content, clean_task_text
from src.dailynotes.sync.rendering import normalize_child_lines, aggressive_daily_clean

# 测试用例
test_line = "- "
test_lines = ["# Day planner\n", "\n", "- \n", "\n"]

print("=" * 50)
print("测试输入行: repr =", repr(test_line))
print("=" * 50)

# 测试 1: normalize_block_content
print("\n[TEST 1] normalize_block_content")
result1 = normalize_block_content([test_line])
print(f"  输入: {repr([test_line])}")
print(f"  输出: {repr(result1)}")

# 测试 2: clean_task_text
print("\n[TEST 2] clean_task_text")
result2 = clean_task_text(test_line)
print(f"  输入: {repr(test_line)}")
print(f"  输出: {repr(result2)}")

# 测试 3: normalize_child_lines
print("\n[TEST 3] normalize_child_lines")
result3 = normalize_child_lines([test_line], 0)
print(f"  输入: {repr([test_line])}")
print(f"  输出: {repr(result3)}")

# 测试 4: aggressive_daily_clean
print("\n[TEST 4] aggressive_daily_clean")
result4 = aggressive_daily_clean(test_lines)
print(f"  输入: {repr(test_lines)}")
print(f"  输出: {repr(result4)}")

# 测试 5: FormatCore.sort_day_planner_content
print("\n[TEST 5] FormatCore.sort_day_planner_content")
test_content = "- \n"
result5 = FormatCore.sort_day_planner_content(test_content)
print(f"  输入: {repr(test_content)}")
print(f"  输出: {repr(result5)}")

# 测试 6: FormatCore.sort_markdown_sections
print("\n[TEST 6] FormatCore.sort_markdown_sections")
test_md = "# Day planner\n\n- \n\n# Journey\n"
result6 = FormatCore.sort_markdown_sections(test_md)
print(f"  输入: {repr(test_md)}")
print(f"  输出: {repr(result6)}")

print("\n" + "=" * 50)
print("完成测试")
