import re
import difflib

old_txt = """15:45:33 #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t)
"""
new_txt = """15:45:33 #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t) ✅
"""

diff = list(difflib.unified_diff(old_txt.splitlines(), new_txt.splitlines(), n=0, lineterm=''))
adds = [line[1:] for line in diff if line.startswith('+') and not line.startswith('+++')]
dels = [line[1:] for line in diff if line.startswith('-') and not line.startswith('---')]

time_pat = re.compile(r'^\s*(\d{1,2}[:：]\d{2})')
completion_pat = re.compile(
    r'^\s*(\d{1,2}:\d{2}(?::\d{2})?)?\s*.*?'
    r'(?:\*([a-zA-Z0-9:_]+)\*?|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)'
)

used_adds = [False] * len(adds)

for d_line in dels:
    d_match = time_pat.match(d_line.strip())
    matched_idx = -1
    if d_match:
        d_time = d_match.group(1)
        for i, a_line in enumerate(adds):
            if not used_adds[i]:
                a_match = time_pat.match(a_line.strip())
                if a_match and a_match.group(1) == d_time:
                    matched_idx = i
                    break
    
    if matched_idx != -1:
        print("MOD Line:", repr(adds[matched_idx]))
        _mod_match = completion_pat.match(adds[matched_idx].strip())
        print("Matched?", bool(_mod_match))

