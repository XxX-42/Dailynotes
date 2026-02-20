import re

time_pat = re.compile(r'^\s*(\d{1,2}[:：]\d{2})')
completion_pat = re.compile(
    r'^\s*(\d{1,2}:\d{2}(?::\d{2})?)?\s*.*?'
    r'(?:\*([a-zA-Z0-9:_]+)\*?|\(\s*id=([a-zA-Z0-9:_]+)\s*\)?|（\s*id=([a-zA-Z0-9:_]+)\s*）?)'
)

dels = ["15:45:33 #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t)"]
adds = ["15:45:33 #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]] (id=5utl1t) ✅"]

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
        print(f"[MOD] {d_line} -> {adds[matched_idx]}")
        # Check if the NEW line has completion markers
        if completion_pat.match(adds[matched_idx].strip()):
            print("Set used_adds=False (let it fall through)")
            used_adds[matched_idx] = False # Let it fall through to ADD loop
        else:
            used_adds[matched_idx] = True

print("After MOD matching, used_adds =", used_adds)

for i, a_line in enumerate(adds):
    if not used_adds[i]:
        print(f"Processing ADD: {a_line}")
        comp_match = completion_pat.match(a_line.strip())
        if comp_match:
            print("Found Heartbeat. Task ID:", comp_match.group(2) or comp_match.group(3) or comp_match.group(4))

