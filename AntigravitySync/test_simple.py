#!/usr/bin/env python3
"""
简化测试：找出 "- " -> "-" 的问题
"""
import sys
sys.path.insert(0, '/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta/AntigravitySync')

result_lines = []

def log(msg):
    result_lines.append(msg)
    print(msg)

from src.dailynotes.format_core import FormatCore

# 测试 sort_day_planner_content
test_content = "- "
log(f"INPUT: {repr(test_content)}")
result = FormatCore.sort_day_planner_content(test_content)
log(f"OUTPUT: {repr(result)}")

if test_content.endswith(" ") and not result.endswith(" "):
    log("PROBLEM FOUND: 尾部空格被删除!")
else:
    log("OK")

# 写结果到文件
with open('/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta/AntigravitySync/test_output.txt', 'w') as f:
    f.write("\n".join(result_lines))
