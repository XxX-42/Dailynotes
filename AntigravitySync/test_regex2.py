import re

# Old regex
pat = re.compile(
    r'^\s*(?:(\d{1,2}:\d{2}(?::\d{2})?)\s+)?.*?'
    r'(?:\*([a-zA-Z0-9:_]+)\*?|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)'
)

# New regex: make time non-optional at start, OR have a separate pass, OR use non-greedy but anchored?
# Actually, since the time is at the very beginning of the string, we can do:
# `^\s*(?:(\d{1,2}:\d{2}(?::\d{2})?)\b)?.*?`
# But `(?:...)?` with `.*?` is tricky. Let's just do `re.search` instead of `match`, or pull out the time separately.
# Wait, let's try another approach for pat
pat2 = re.compile(
    r'^\s*(?:(\d{1,2}:\d{2}(?::\d{2})?)(?:\s+|[^a-zA-Z0-9]*))?.*?'
    r'(?:\*([a-zA-Z0-9:_]+)\*?|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)'
)

s1 = "15:11:19 #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t ✅"
m2 = pat2.match(s1)
print(m2.groups())

# Wait, the best way to extract time at the start is to just use a separate regex, or make it not optional in a branch:
# ^(\d:\d)?.*(id)  -> if we use ^(\d{1,2}:\d{2}(?::\d{2})?)?\s*.*?(id=...)
pat3 = re.compile(
    r'^\s*(\d{1,2}:\d{2}(?::\d{2})?)?\s*.*?'
    r'(?:\*([a-zA-Z0-9:_]+)\*?|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)'
)
m3 = pat3.match(s1)
print("pat3:", m3.groups())
