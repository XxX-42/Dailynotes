import difflib

old = """12:08:19"水":"50ml" ✅
12:09:10"水":"50ml" ✅
*5utl1t*#B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]]
15:35:12 ✅
"""

new = """12:08:19"水":"50ml" ✅
12:09:10"水":"50ml" ✅
*5utl1t*#B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]]
15:35:12 ✅

15:35:32 #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t) ✅
"""

diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(), n=0, lineterm=''))
print("Diff output:")
for d in diff:
    print(d)

