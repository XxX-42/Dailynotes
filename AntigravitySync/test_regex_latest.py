import re

# Test string 1: empty content timestamp
s1 = "15:35<span id=\"15:35:12\"></span> "
time_pat = re.compile(r'^\s*(\d{1,2}[:：]\d{2})')
m1 = time_pat.match(s1)
print("Time entry match:", bool(m1))

# Test string 2: Valid Apple Notes Heartbeat (Failed to sync)
s2 = "15:39:44 #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t) ✅"
completion_pat = re.compile(
    r'^\s*(\d{1,2}:\d{2}(?::\d{2})?)?\s*.*?'
    r'(?:\*([a-zA-Z0-9:_]+)\*?|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)'
)
m2 = completion_pat.match(s2)
print("Heartbeat match:", bool(m2))
if m2:
    print("Heartbeat groups:", m2.groups())

