import re

pat = re.compile(r'\(\s*id=[a-zA-Z0-9:_]+\s*(?![\)✅])')
s = "15:11:19 #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t ✅"
print("Match test 1:", bool(pat.search(s)))

s2 = "15:11:19 #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t)"
print("Match test 2:", bool(pat.search(s2)))
