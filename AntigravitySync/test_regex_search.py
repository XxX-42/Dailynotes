import re

completion_pat = re.compile(
    r'(?:\s*(\d{1,2}:\d{2}(?::\d{2})?)?\s*.*?)?'
    r'(?:\*([a-zA-Z0-9:_]+)\*?|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)'
)

# test with weird prefix
line = "\ufeff\u200b 15:45:33 #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t) ✅"
m = completion_pat.search(line)
print("Matched?", bool(m))
if m:
    print("Groups:", m.groups())

