import re

line = '- [x] 10:22 - 10:23<span id="5utl1t" data-timestamps="10:21:20,10:22:00,10:22:31"></span> #B [[测试/测试|测试]]'
st_m = re.search(r'-\s*\[(.)\]', line)
status = st_m.group(1) if st_m else ' '
has_sync_tag = bool(re.search(r'#[A-D]\b', line))

print(f"Status: '{status}', Has Sync Tag: {has_sync_tag}")
