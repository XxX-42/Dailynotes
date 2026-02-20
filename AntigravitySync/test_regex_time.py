import re

time_pat = re.compile(r'(\d{1,2}[:：]\d{2}(?::\d{2})?)')

completion_pat = re.compile(
    r'(?:\*([a-zA-Z0-9:_]+)\*?|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)'
)

line = "\ufeff\u200b 15:45:33 #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t) ✅"

# Extract ID
comp_match = completion_pat.search(line)
if comp_match:
    task_id = comp_match.group(1) or comp_match.group(2) or comp_match.group(3)
    print("Task ID:", task_id)
    
    # Extract Time
    time_match = time_pat.search(line)
    if time_match:
        print("Time:", time_match.group(1))
    else:
        print("Time: Fallback to now")

