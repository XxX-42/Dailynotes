#!/usr/bin/env python3
import re

text = """---
tags:
  - DayPlan
---
# Day planner

content here
"""
sections = re.split(r'^(#\s.*)$', text.strip(), flags=re.MULTILINE)
for i, s in enumerate(sections):
    print(f'[{i}]: {repr(s)}')
