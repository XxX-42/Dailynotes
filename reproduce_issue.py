import re

# Mocking SyncCore methods for isolation
class MockSyncCore:
    def format_line(self, indent, status, text, dates, fname, bid, is_daily):
        tab_count = indent // 4 
        indent_str = '\t' * tab_count
        return f"{indent_str}- [{status}] {text} ^{bid}\n"

    def reconstruct_daily_block(self, sd, target_date):
        fname = sd['fname']
        bid = sd['bid']
        status = sd['status']
        text = sd['pure'] # Simplified
        
        parent_line = self.format_line(sd['indent'], status, text, "", fname, bid, True)
        
        children = []
        for line in sd['raw'][1:]:
            # [Logic from sync_core.py]
            # Remove '> ' prefix and leading spaces to get pure content
            child_clean = re.sub(r'^[\s>]+', '', line).rstrip('\n\r')
            
            trimmed_content = child_clean.strip()

            if trimmed_content.startswith('- '):
                children.append(f"\t{child_clean}\n")
            elif trimmed_content == "-":
                children.append(f"\t{child_clean}\n")
            else:
                children.append(f"\t- {child_clean}\n")
            
        return [parent_line] + children

    def capture_block_mock(self, lines, start_idx):
        def get_indent(s):
            no_quote = re.sub(r'^>\s?', '', s)
            return len(no_quote) - len(no_quote.lstrip())

        base_indent = get_indent(lines[start_idx])
        block = [lines[start_idx]]
        j = start_idx + 1
        while j < len(lines):
            nl = lines[j]
            if nl.strip() == "": 
                block.append(nl); j += 1; continue
            
            if get_indent(nl) > base_indent:
                block.append(nl); j += 1
            else:
                break
        return block

    def aggressive_callout_clean(self, lines):
        if not lines: return []
        garbage_pattern = re.compile(r'^\s*>\s*[- ]*$')
        garbage_buffer = []
        while lines:
            line = lines[-1].strip()
            if not line or garbage_pattern.fullmatch(line):
                garbage_buffer.append(lines.pop())
            else:
                break
        if garbage_buffer:
            lines.append(garbage_buffer[0])
        return lines

scanner = MockSyncCore()


# Test Data 2: Indented Empty Lines
source_lines_2 = [
    "> - [ ] Parent",
    ">     - Child 1",
    ">     ",  # Indented empty line
    ">     "   # Another indented empty line
]

print("\n--- Test 2: Indented Empty Lines ---")
# 1. Clean
clean_lines = scanner.aggressive_callout_clean(list(source_lines_2))
print("Cleaned Lines:")
for l in clean_lines: print(repr(l))

# 2. Capture (on Cleaned)
raw_block = scanner.capture_block_mock(clean_lines, 0)
print("Captured:")
for l in raw_block: print(repr(l))

# 3. Reconstruct
sd = {'fname': 'Test', 'bid': 'x', 'status': ' ', 'pure': 'P', 'indent': 0, 'raw': raw_block}
daily_lines = scanner.reconstruct_daily_block(sd, "Date")
print("Reconstructed:")
for l in daily_lines: print(repr(l))
