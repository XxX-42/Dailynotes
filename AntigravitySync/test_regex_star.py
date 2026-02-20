import re

pat3 = re.compile(
    r'^\s*(\d{1,2}:\d{2}(?::\d{2})?)?\s*.*?'
    r'(?:\*([a-zA-Z0-9:_]+)\*?|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)'
)

s1 = "*5utl1t*#B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]]"
m3 = pat3.match(s1)
print(m3.groups() if m3 else None)

