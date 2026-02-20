import re
completion_pat = re.compile(
    r'^\s*(\d{1,2}:\d{2}(?::\d{2})?)?\s*.*?'
    r'(?:\*([a-zA-Z0-9:_]+)\*?|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)'
)

stripped_line = "15:45:33 #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t) ✅"
comp_match = completion_pat.match(stripped_line)
print("Regex match:", bool(comp_match))
