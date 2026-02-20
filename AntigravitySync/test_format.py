import re

raw_first = '- [x] 10:22 - 15:04<span id="5utl1t" data-timestamps="15:03:34"></span> #B [[测试/测试|测试]]'

# 1. Extract status, time, bid, data_ts
st_m = re.search(r'-\s*\[(.)\]', raw_first)
status = st_m.group(1) if st_m else ' '

bid_m = re.search(r'(?:\^([a-zA-Z0-9]{6,})\s*$|<span id="([a-zA-Z0-9]{6,})"(?: data-timestamps="([^"]*)")?></span>)', raw_first)
bid = (bid_m.group(1) or bid_m.group(2)) if bid_m else 'xxxxxx'
data_ts = bid_m.group(3) if bid_m and len(bid_m.groups()) >= 3 else None

time_part = ""
body_only = re.sub(r'^\s*-\s*\[.\]\s?', '', raw_first)
tm = re.match(r'^(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)', body_only)
if tm: 
    time_part = tm.group(1)

# Extract sync tags (#A, #B, etc.)
sync_tag_m = re.search(r'(#[A-D]\b)', raw_first)
sync_tag = sync_tag_m.group(1) if sync_tag_m else ''

# Extract return target
m_links = re.findall(r'\[\[(.*?)(?:[\|#].*)?\]\]', raw_first)
ret_target = m_links[0] if m_links else 'Unknown'

# Clean pure
clean_pure = re.sub(r'^[\s>]*-\s*\[.\]\s?', '', raw_first)
clean_pure = re.sub(r'^\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?\s*', '', clean_pure)
clean_pure = re.sub(r'\^[a-zA-Z0-9]{6,}\s*$', '', clean_pure)
clean_pure = re.sub(r'<span id="[a-zA-Z0-9]{6,}"(?: data-timestamps="[^"]*")?></span>', '', clean_pure)
clean_pure = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', clean_pure)
clean_pure = re.sub(r'##\s*\[\[[^\]]+\]\]', '', clean_pure)
if sync_tag:
    clean_pure = clean_pure.replace(sync_tag, '') # remove tag from pure
clean_pure = re.sub(r'\s+', ' ', clean_pure).strip()

span_id = f'<span id="{bid}" data-timestamps="{data_ts}"></span>' if data_ts else f'<span id="{bid}"></span>'
ret_link = f"[[{ret_target}#^{bid}|⮐]]"

# Final assembly exactly as requested
# - [x] 10:22 - 15:04 <span id="5utl1t" data-timestamps="15:03:34"></span> #B [[测试/测试#^5utl1t|⮐]] [[测试/测试|测试]]
time_str = f"{time_part} " if time_part else ""
sync_str = f"{sync_tag} " if sync_tag else ""

final_head_line = f"- [{status}] {time_str}{span_id} {sync_str}{ret_link} {clean_pure}\n"
print(final_head_line, end='')
