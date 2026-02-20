import re

raw_first = '- [x] 10:22 - 14:37<span id="xxx123" data-timestamps="111,222,333"></span> #B [[测试/测试|测试]]'

# Old regex (didn't capture group 3)
bid_m_old = re.search(r'(?:\^([a-zA-Z0-9]{6,})\s*$|<span id="([a-zA-Z0-9]{6,})"(?: data-timestamps="[^"]*")?></span>)', raw_first)

# New regex
bid_m = re.search(r'(?:\^([a-zA-Z0-9]{6,})\s*$|<span id="([a-zA-Z0-9]{6,})"(?: data-timestamps="([^"]*)")?></span>)', raw_first)

bid = (bid_m.group(1) or bid_m.group(2))
data_ts = bid_m.group(3) if bid_m and len(bid_m.groups()) >= 3 else None

print(f"Captured ID: {bid}")
print(f"Captured TS: {data_ts}")

span_id = f'<span id="{bid}" data-timestamps="{data_ts}"></span>' if data_ts else f'<span id="{bid}"></span>'
print(f"Reconstructed Span: {span_id}")
