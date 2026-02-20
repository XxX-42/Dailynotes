import re

completion_pat = re.compile(
    r'^\s*(?:(\d{1,2}:\d{2}(?::\d{2})?)(?:\s+|<span[^>]*></span>\s*))?.*?'
    r'(?:\*([a-zA-Z0-9:_]+)\*|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)'
)

s1 = "15:11<span id=\"15:11:19\"></span> #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t"
m = completion_pat.match(s1)
print("Match loose?", bool(m))
if m:
    print("Time:", m.group(1))
    print("ID v1:", m.group(2))
    print("ID v2:", m.group(3))
    print("ID v3:", m.group(4))
