import os
import re
import random
import string
import unicodedata
import datetime
import threading
import time
from typing import Dict, List, Optional, Any, Set
from config import Config
from utils import Logger, FileUtils

class SyncCore:
    def __init__(self, state_manager):
        self.sm = state_manager
        self.project_map = {}
        self.project_path_map = {}
        self.file_path_map = {}

    def trigger_delayed_verification(self, filepath, delay=10):
        def _job():
            time.sleep(delay)
            # Read content using FileUtils
            content = FileUtils.read_file(filepath) or []
            # Logging with distinct header
            Logger.debug_block(f"VERIFICATION (T+{delay}s) Snapshot: {os.path.basename(filepath)}", content)
        
        t = threading.Thread(target=_job, daemon=True)
        t.start()

    def generate_block_id(self):
        return '^' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    def parse_yaml_tags(self, lines):
        tags = []
        if not lines or lines[0].strip() != '---': return []
        in_yaml = False
        for i, line in enumerate(lines):
            if i == 0: in_yaml = True; continue
            if line.strip() == '---': break
            if in_yaml and ('tags:' in line or 'main' in line):
                if re.search(r'\bmain\b', line): tags.append('main')
        return tags

    def clean_task_text(self, line, block_id=None, context_name=None):
        line = re.sub(r'📅\s*\d{4}-\d{2}-\d{2}', '', line)
        line = re.sub(r'✅\s*\d{4}-\d{2}-\d{2}', '', line)
        # [FIX] Stricter ID Regex: Space + ^ + 6-7 alphanum + End
        line = re.sub(r'(?<=\s)\^[a-zA-Z0-9]{6,7}\s*$', '', line)
        line = re.sub(r'\(connect::.*?\)', '', line)
        line = re.sub(r'\s*\[\[[^\]]*?\|[⮐📅]\]\]', '', line)
        line = re.sub(r'\s*\[\[\d{4}-\d{2}-\d{2}\]\]', '', line)
        line = re.sub(r'^[\s>]*-\s*\[.\]\s*', '', line)
        if context_name:
            line = re.sub(rf'\[\[{re.escape(context_name)}(\|.*?)?\]\]', '', line)
        text = line.strip()
        if block_id:
            while text.endswith(block_id): text = text[:-len(block_id)].strip()
        return text

    def normalize_block_content(self, block_lines):
        normalized = []
        for line in block_lines:
            clean = re.sub(r'^[\s>]+', '', line).strip()
            normalized.append(clean)
        return "".join(normalized)

    def extract_routing_target(self, line):
        clean = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', line)
        matches = re.findall(r'\[\[(.*?)\]\]', clean)
        for match in matches:
            pot = match.split('|')[0]
            pot = unicodedata.normalize('NFC', pot)
            if pot in self.file_path_map: return self.file_path_map[pot]
        return None

    def capture_block(self, lines, start_idx):
        if start_idx >= len(lines): return [], 0
        
        def get_indent(s):
            # Calculate indent ignoring '>' prefix
            # 1. Strip '>' and optional space
            no_quote = re.sub(r'^>\s?', '', s)
            # 2. Count leading whitespace relative to clean string
            return len(no_quote) - len(no_quote.lstrip())

        base_indent = get_indent(lines[start_idx])
        block = [lines[start_idx]]
        consumed = 1
        j = start_idx + 1
        while j < len(lines):
            nl = lines[j]
            # Blank line is part of block? Yes, if indented or if inside block logic.
            # But here we just check if it's "indented relative to base".
            # For blank lines, get_indent might be 0.
            if nl.strip() == "": 
                block.append(nl); consumed += 1; j += 1; continue
            
            if get_indent(nl) > base_indent:
                block.append(nl); consumed += 1; j += 1
            else:
                break
        return block, consumed
    def normalize_raw_tasks(self, lines, filename_stem):
        """
        Auto-Registration: Detect raw tasks '> - [ ]' without ID and convert to standard format.
        """
        if not lines or not filename_stem: return lines
        
        new_lines = []
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        raw_pattern = re.compile(r'^(>\s*-\s*\[\s*\])(.*)$')
        id_pattern = re.compile(r'\^[a-z0-9]{6}\s*$')

        def generate_id():
            return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

        for line in lines:
            match = raw_pattern.match(line)
            if match:
                prefix = match.group(1) 
                text_body = match.group(2).strip()
                
                if not id_pattern.search(text_body):
                    new_id = generate_id()
                    formatted_body = f"[[{filename_stem}#^{new_id}|⮐]] [[{today_str}]]"
                    if text_body:
                        formatted_body += f" {text_body}"
                    new_lines.append(f"{prefix} {formatted_body} ^{new_id}")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        return new_lines

    def inject_into_callout(self, file_lines, block_lines, filename_stem=None):
        """
        Rewritten with Deep Trace Logging and Hard Cap Tail Logic.
        """
        # --- 1. Extract YAML & Split Body ---
        yaml_lines = []
        body_lines = []
        if file_lines and file_lines[0].strip() == '---':
            yaml_lines.append(file_lines[0])
            for i in range(1, len(file_lines)):
                yaml_lines.append(file_lines[i])
                if file_lines[i].strip() == '---':
                    body_lines = file_lines[i+1:]
                    break
            else:
                yaml_lines = []
                body_lines = file_lines
        else:
            body_lines = file_lines

        # --- 2. Harvesting Phase ---
        harvested_tasks = []
        clean_body = []
        default_header = "> [!note]- Tasks"
        captured_header = None
        
        # [PATCH] Robust Regex for Header (Supports > [!note], > [!note]-, > [!note]+)
        TASK_HEADER_PATTERN = re.compile(r"^>\s*\[!note\]([-+]?)\s+Tasks", re.IGNORECASE)
        
        i = 0
        while i < len(body_lines):
            line = body_lines[i]
            stripped = line.strip()
            
            # Case A: Existing Callout (Regex Detection)
            match = TASK_HEADER_PATTERN.match(stripped)
            if match:
                if not captured_header:
                     captured_header = line.strip() # Preserve the first found header
                i += 1
                while i < len(body_lines):
                    cl = body_lines[i]
                    if cl.strip().startswith('>'):
                         harvested_tasks.append(cl)
                         i += 1
                    elif cl.strip() == '':
                         # Loose formatting heuristic
                         if i + 1 < len(body_lines) and body_lines[i+1].strip().startswith('>'):
                             harvested_tasks.append(cl)
                             i += 1
                         else:
                             break 
                    else:
                         break 
                continue

            # Case B: Orphan Task
            if re.match(r'^[\s]*-\s*\[.\]', line):
                 has_id = re.search(r'\^[a-zA-Z0-9]{6,}\s*$', line)
                 if has_id:
                     block, consumed = self.capture_block(body_lines, i)
                     harvested_tasks.extend(block)
                     i += consumed
                     continue
            
            # Case C: Normal Text
            clean_body.append(line)
            i += 1

        # LOGGING 1: Harvested
        if block_lines or harvested_tasks:
             Logger.debug(f"DeepTrace: Harvested {len(harvested_tasks)} existing, {len(block_lines)} new.")

        # --- 3. Normalization & Deduplication ---
        candidates = harvested_tasks + block_lines
        processed_candidates = []
        seen_ids = set()
        
        for line in candidates:
            clean_l = re.sub(r'^>\s?', '', line)
            # Normalize empty lines
            if clean_l.strip() == '':
                processed_candidates.append("") 
                continue
            
            if '\t' in clean_l:
                clean_l = clean_l.replace('\t', '    ') 

            id_match = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', clean_l)
            if id_match:
                bid = id_match.group(1)
                if bid in seen_ids:
                    continue 
                seen_ids.add(bid)
            
            # [FIX] Preserve trailing spaces (e.g. "- ") for user cursor
            processed_candidates.append(clean_l.rstrip('\n\r')) 
        
        # LOGGING 2: Processed
        # Logger.debug(f"DeepTrace: {len(processed_candidates)} candidates after norm.")

        # --- 4. Context-Aware Safety Compression ---
        final_task_lines = []
        
        def is_list_item(s):
            if not s: return False
            return re.match(r'^\s*([-\*]|\d+\.)\s', s) is not None

        last_content_line = "HEADER"

        for j, curr in enumerate(processed_candidates):
            if curr == "":
                next_l = processed_candidates[j+1] if j < len(processed_candidates) - 1 else None
                
                # 1. Collapse duplicate blanks
                if next_l == "": continue 

                # 2. Intra-List Gap -> Remove
                prev_is_item = (last_content_line == "HEADER") or is_list_item(last_content_line)
                next_is_item = is_list_item(next_l)
                
                if prev_is_item and next_is_item:
                    continue # SKIP
                
                # 3. Preserve Paragraph Break (WITH SPACE)
                # [FIX] Output "> \n" instead of ">\n" to preserve the "Wait for Input" space.
                # This prevents "Space Separated" issues and Obsidian fighting back.
                final_task_lines.append("> \n")
            else:
                final_task_lines.append(f"> {curr}\n")
                last_content_line = curr

        # --- 5. Aggressive Cleaner (Zero Tail) ---
        # Auto-Registration: Convert raw tasks to standard format
        if filename_stem:
            final_task_lines = self.normalize_raw_tasks(final_task_lines, filename_stem)
            
        # Apply Aggressive Callout Cleaner
        final_task_lines = self.aggressive_callout_clean(final_task_lines)

        # LOGGING 3: Final
        if final_task_lines:
             Logger.debug(f"DeepTrace: Final Block has {len(final_task_lines)} lines.")

        # --- 6. Reconstruction ---
        final_header = captured_header if captured_header else default_header
        
        new_block = []
        if final_task_lines:
            new_block.append(f"{final_header}\n")
            new_block.extend(final_task_lines)
            new_block.append("\n") # Spacer

        return yaml_lines + new_block + clean_body

    def aggressive_callout_clean(self, lines):
        """
        [HOTFIX] Relaxed Callout Cleaner.
        Only removes consecutive empty lines if they exceed 2.
        Preserves special characters like '---' and list markers '-'.
        Logs deletions for debugging.
        """
        if not lines: return []
        
        cleaned_lines = []
        empty_count = 0
        
        # Regex for "Callout Empty Line": > followed by optional whitespace
        # DOES NOT match > - (bullet) or > text
        empty_pattern = re.compile(r'^\s*>\s*$')
        
        for i, line in enumerate(lines):
            is_empty = bool(empty_pattern.fullmatch(line))
            
            # Special Safety: If line contains '---' or '-', treat as content
            # '-' protects typing flow for lists (e.g. "> -")
            if '---' in line or '-' in line:
                is_empty = False
            
            if is_empty:
                empty_count += 1
                if empty_count > 2:
                    # Excess empty line -> Skip/Delete
                    Logger.debug(f"[CLEAN] Removing excess callout line {i+1}: {repr(line)}")
                    continue 
                else:
                    cleaned_lines.append(line)
            else:
                # Content found -> Reset counter
                empty_count = 0
                cleaned_lines.append(line)
        
        return cleaned_lines

    def aggressive_daily_clean(self, lines: list) -> list:
        """
        [HOTFIX] Relaxed Daily Cleaner.
        Only removes consecutive empty lines if they exceed 2 in the body.
        Preserves special characters like '---'.
        Logs deletions for debugging.
        """
        if not lines: return []

        # 1. Identify "Footer" index
        footer_idx = len(lines)
        for i, line in enumerate(lines):
            if line.strip().startswith('# Day planner') or line.strip().startswith('# Journey'):
                footer_idx = i
                break
        
        # 2. Extract content above footer
        body = lines[:footer_idx]
        foot = lines[footer_idx:]
        
        # 3. Clean Body (Internal Vertical Whitespace)
        cleaned_body = []
        empty_count = 0
        empty_pattern = re.compile(r'^\s*$') # Matches pure blank lines
        
        for i, line in enumerate(body):
            is_empty = bool(empty_pattern.fullmatch(line))
            
            # Safety: Protect '---' and other structural markers
            if '---' in line:
                is_empty = False
                
            if is_empty:
                empty_count += 1
                if empty_count > 2:
                    Logger.debug(f"[CLEAN] Removing excess daily line {i+1}: {repr(line)}")
                    continue
                else:
                    cleaned_body.append(line)
            else:
                empty_count = 0
                cleaned_body.append(line)
        
        # 4. Reassemble
        return cleaned_body + foot

    def format_line(self, indent, status, text, dates, fname, bid, is_daily):
        # [FEATURE] Use TAB for indentation
        # Calculate tab count based on indent level (assuming 1 level = 4 spaces or 1 tab)
        # If 'indent' comes in simply as specific width, we might need adjustments.
        # But 'indent' is calculated via get_indent() which counts chars.
        # Simple fix: Treat 'indent' as number of tabs if we change input logic? 
        # No, 'indent' is raw integer. Let's convert: 4 spaces -> 1 tab.
        tab_count = indent // 4 
        indent_str = '\t' * tab_count
        
        if is_daily:
            link = f"[[{fname}#^{bid}|⮐]]"
            time_match = re.match(r'^(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)', text)
            if time_match:
                time_part = time_match.group(1)
                rest_part = text[len(time_part):].strip()
                return f"{indent_str}- [{status}] {time_part} {link} {rest_part} ^{bid}\n"
            else:
                return f"{indent_str}- [{status}] {link} {text} ^{bid}\n"
        else:
            clean_text = re.sub(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', '', text)
            clean_text = re.sub(r'\d{1,2}:\d{2}', '', clean_text)
            clean_text = re.sub(rf'\[\[{re.escape(fname)}(\|.*?)?\]\]', '', clean_text)
            clean_text = clean_text.strip()

            creation_date = None
            # Extract simple date from dates string or complex link
            # dates string comes from scanner
            simple_match = re.search(r'\[\[(\d{4}-\d{2}-\d{2})\]\]', dates)
            if simple_match:
                creation_date = simple_match.group(1)
            else:
                 # Try finding from complex/emoji
                 m = re.search(r'(?:📅|\|📅\]\])\s*(\d{4}-\d{2}-\d{2})', dates)
                 if m: creation_date = m.group(1)
            
            if not creation_date:
                # Last resort fallback if date not found in dates string
                 m = re.search(r'(\d{4}-\d{2}-\d{2})', dates)
                 if m: creation_date = m.group(1)

            processed_dates = []
            done_date_match = re.search(r'✅\s*(\d{4}-\d{2}-\d{2})', dates)
            if done_date_match:
                processed_dates.append(f"✅ {done_date_match.group(1)}")

            meta_str = " ".join(processed_dates)
            
            # Construct Links
            self_link = f"[[{fname}#^{bid}|⮐]]"
            daily_link = f"[[{creation_date}]]" if creation_date else ""
            parts = [self_link]
            if daily_link: parts.append(daily_link)
            parts.append(clean_text)
            if meta_str: parts.append(meta_str)
            parts.append(f"^{bid}")
            
            content_str = " ".join(parts)
            return f"{indent_str}- [{status}] {content_str}\n"

    # [NEW] Helper for Unified Formatting
    def normalize_child_lines(self, raw_lines, parent_indent, as_quoted=False):
        children = []
        child_indent_lvl = (parent_indent // 4) + 1
        child_indent_str = '\t' * child_indent_lvl
        
        for line in raw_lines:
             # Cleaning: Remove > and whitespace
             content = re.sub(r'^[>\s]+', '', line).strip()
             
             # Enforce Bullet Syntax
             if content == '-' or content == '':
                 final_content = "- "
             elif content.startswith('-'):
                 if not content.startswith('- '):
                      final_content = "- " + content[1:].strip()
                 else:
                      final_content = content
             else:
                  final_content = f"- {content}"
             
             # Output Assembly
             if as_quoted:
                 # Source File: Check if empty to avoid trailing space issues?
                 # Standard: "> \t- content"
                 # Special: "> " for empty lines? No, for bullet lines we use syntax.
                 children.append(f"> {child_indent_str}{final_content}\n")
             else:
                 # Daily Note: Plain text
                 children.append(f"{child_indent_str}{final_content}\n")
                 
        return children

    def reconstruct_daily_block(self, sd, target_date):
        fname = sd['fname']
        bid = sd['bid']
        status = sd['status']
        
        # 1. Clean the text: Remove Date links
        text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}\]\]', '', sd['pure']).strip()
        
        # 2. Re-inject Project Link if missing
        link_tag = f"[[{fname}]]"
        if link_tag not in text:
            text = f"{link_tag} {text}"
            
        # 3. Construct Parent Line (Daily Format)
        # Using tabs for parent indent? Usually Daily Notes are top level or indented?
        # Typically top level or whatever format_line produces.
        # But wait, sd['indent'] is Source indent. Daily Note indent should be relative?
        # If Source is indented, Daily Note implies flattened? 
        # No, usually Daily Note aggregates tasks.
        # But let's stick to format_line logic for parent.
        parent_line = self.format_line(sd['indent'], status, text, "", fname, bid, True)
        
        # 4. Enforce Child Formatting (Brute Force)
        children = []
        raw_children = sd['raw'][1:]
        
        # Calculate Child Indentation (Strictly +1 level from parent)
        # Assuming parent is at sd['indent']
        # But wait, parent_line in daily note usually starts at 0 or preserved?
        # If we use sd['indent'] directly for parent, we preserve hierarchy.
        # Then children are at parent + 1 level.
        child_indent_str = '\t' * ((sd['indent'] // 4) + 1)
        
        for line in raw_children:
            # 4.1 Remove Callout Chars
            # Regex: Remove '>' and optional space at start
            child_clean = re.sub(r'^>\s?', '', line)
            
            # 4.2 Analyze Content
            stripped = child_clean.strip()
            
            # 4.3 Content Reconstruction
            if not stripped or stripped == '-':
                # Case: Empty Bullet
                final_content = "- "
            elif stripped.startswith('-'):
                # Check for adhesion e.g. "-Text"
                # If matches "-[anything]"
                if len(stripped) > 1 and stripped[1] != ' ':
                     # Force Space: "-Text" -> "- Text"
                     final_content = f"- {stripped[1:].strip()}"
                elif stripped == '- ':
                     final_content = "- "
                else:
                     # It is "- Text" or "- [ ] Text"
                     # Re-build to be safe
                     # Strip leading "- " and re-add?
                     # stripped[2:] might be empty if it was "- "
                     final_content = f"- {stripped[2:].strip()}"
            else:
                # Case: "Text" (Missing bullet)
                final_content = f"- {stripped}"
                
            # 4.4 Indent Injection
            # [CRITICAL] Ensure space is preserved in "- "
            formatted_line = f"{child_indent_str}{final_content}"
            # Double check trailing space for empty bullet
            if formatted_line.strip() == '-': 
                 # This shouldn't happen due to logic above
                 formatted_line += " "
            elif formatted_line.endswith('-'):
                 formatted_line += " "

            children.append(formatted_line)

        # [Optimized Compaction]
        # Allow max 1 empty bullet at the end
        if children:
            while children and children[-1].strip() == '-':
                children.pop()
            # If we popped everything or want to leave one breathing room?
            # User previously wanted "max 1". 
            # If I pop ALL, then there is 0.
            # Let's add ONE back if the valid list is not empty?
            # Or just leave it compact.
            # "Brute Force" usually implies strictness. 
            # Let's look at previous behavior: "Ensure max 1 empty bullet".
            # I'll append one empty bullet if I removed any? No.
            # Just simply: Remove trailing bullets.
            # If user wants, they can type it.
            # If I add it automatically, it is "Ghost Bullet".
            # Let's clean all trailing empty bullets.
            pass

        return [parent_line] + children

    def cleanup_empty_callouts(self, lines):
        """Removes '> [!note]- Tasks' (or variants) block if it contains no task checkboxes."""
        if lines is None: return [] # Guard Clause
        
        output = []
        # Robust Regex for Header (Supports > [!note], > [!note]-, > [!note]+)
        TASK_HEADER_PATTERN = re.compile(r"^>\s*\[!note\]([-+]?)\s+Tasks", re.IGNORECASE)
        
        in_callout = False
        callout_buffer = []
        has_task = False

        for line in lines:
            if TASK_HEADER_PATTERN.match(line.strip()):
                # Flush previous if needed (shouldn't handle nested)
                if in_callout:
                     if has_task: output.extend(callout_buffer)
                in_callout = True
                callout_buffer = [line]
                has_task = False
            elif in_callout:
                if line.strip().startswith('>') or line.strip() == '':
                    callout_buffer.append(line)
                    if re.search(r'-\s*\[.\]', line):
                        has_task = True
                else:
                    # End of callout
                    if has_task: output.extend(callout_buffer)
                    in_callout = False
                    callout_buffer = []
                    output.append(line)
            else:
                output.append(line)
        
        if in_callout and has_task:
            output.extend(callout_buffer)

        return output

    def ensure_structure(self, lines):
        has_dp = any(l.strip() == "# Day planner" for l in lines)
        j_idx = -1
        try:
            j_idx = next(i for i, l in enumerate(lines) if l.strip() == "# Journey")
        except StopIteration:
            pass

        if not has_dp:
            if j_idx != -1:
                lines.insert(j_idx, "# Day planner\n\n")
            else:
                lines.insert(0, "# Day planner\n\n")
                lines.append("\n# Journey\n")

        if has_dp and j_idx == -1:
            lines.append("\n# Journey\n")

        return lines

    def cleanup_empty_headers(self, lines, date_tag):
        lines = self.ensure_structure(lines)

        try:
            j_idx = next(i for i, l in enumerate(lines) if l.strip() == "# Journey")
        except StopIteration:
            return lines, False

        end_idx = len(lines)
        for i in range(j_idx + 1, len(lines)):
            if lines[i].startswith('# '): end_idx = i; break

        indices_to_delete = []
        i = j_idx + 1
        while i < end_idx:
            line = lines[i]
            if re.match(r'^##\s*\[\[.*?\]\]', line.strip()):
                has_content = False
                j = i + 1
                while j < end_idx:
                    check_line = lines[j].strip()
                    if check_line == "": j += 1; continue
                    if check_line.startswith('#'): break
                    has_content = True;
                    break
                if not has_content:
                    for k in range(i, j): indices_to_delete.append(k)
                    i = j
                else:
                    i += 1
            else:
                i += 1

        if indices_to_delete:
            for idx in sorted(indices_to_delete, reverse=True): del lines[idx]
            Logger.info(f"已清理 {len(set(indices_to_delete))} 行空标题", date_tag)
            return lines, True
        return lines, False

    def scan_projects(self):
        self.project_map = {}
        self.project_path_map = {}
        self.file_path_map = {}
        for root, dirs, files in os.walk(Config.ROOT_DIR):
            dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
            if FileUtils.is_excluded(root): continue
            main_files = []
            for f in files:
                if f.endswith('.md'):
                    path = os.path.join(root, f)
                    f_name = unicodedata.normalize('NFC', os.path.splitext(f)[0])
                    self.file_path_map[f_name] = path
                    if 'main' in self.parse_yaml_tags(FileUtils.read_file(path) or []):
                        main_files.append(f)
            if len(main_files) == 1:
                p_name = unicodedata.normalize('NFC', os.path.splitext(main_files[0])[0])
                self.project_map[root] = p_name
                self.project_path_map[p_name] = os.path.join(root, main_files[0])

    def organize_orphans(self, filepath, date_tag):
        lines = FileUtils.read_file(filepath)
        if not lines: return False

        lines = self.ensure_structure(lines)

        tasks_to_move = []
        ctx = "ROOT"
        i = 0
        while i < len(lines):
            l = lines[i].strip()
            if l.startswith('# '):
                ctx = 'JOURNEY' if l == '# Journey' else ('PLANNER' if l == '# Day planner' else 'OTHER')
                i += 1;
                continue
            if l.startswith('## [[') and l.endswith(']]'): ctx = 'PROJECT'; i += 1; continue

            if re.match(r'^[\s>]*-\s*\[.\]', lines[i]):
                if ctx in ['JOURNEY', 'PLANNER']:
                    target = self.extract_routing_target(lines[i])
                    if target:
                        p_root = os.path.dirname(target)
                        p_name = None
                        curr = p_root
                        while curr.startswith(Config.ROOT_DIR):
                            if curr in self.project_map: p_name = self.project_map[curr]; break
                            parent = os.path.dirname(curr)
                            if parent == curr: break
                            curr = parent
                        if p_name:
                            content, length = self.capture_block(lines, i)
                            tasks_to_move.append({'idx': i, 'len': length, 'proj': p_name, 'raw': content})
                            i += length;
                            continue
            i += 1

        if not tasks_to_move: return False

        tasks_to_move.sort(key=lambda x: x['idx'], reverse=True)
        for t in tasks_to_move: del lines[t['idx']:t['idx'] + t['len']]

        grouped = {}
        for t in tasks_to_move:
            if t['proj'] not in grouped: grouped[t['proj']] = []
            grouped[t['proj']].extend(t['raw'])

        try:
            j_idx = next(i for i, l in enumerate(lines) if l.strip() == "# Journey")
        except:
            j_idx = len(lines)
        ins_pt = len(lines)
        for i in range(j_idx + 1, len(lines)):
            if lines[i].startswith('# '): ins_pt = i; break

        offset = 0
        for proj, blocks in grouped.items():
            header = f"## [[{proj}]]"
            h_idx = -1
            for k in range(j_idx, ins_pt + offset):
                if lines[k].strip() == header: h_idx = k; break

            if blocks and not blocks[-1].endswith('\n'): blocks[-1] += '\n'

            if h_idx != -1:
                sub_ins = ins_pt + offset
                for k in range(h_idx + 1, ins_pt + offset):
                    if lines[k].startswith('#'): sub_ins = k; break
                lines[sub_ins:sub_ins] = blocks
                offset += len(blocks)
            else:
                chunk = [f"\n{header}\n"] + blocks
                lines[ins_pt + offset:ins_pt + offset] = chunk
                offset += len(chunk)

        Logger.info(f"归档 {len(tasks_to_move)} 个流浪任务", date_tag)
        return FileUtils.write_file(filepath, lines)

    def scan_all_source_tasks(self) -> Dict[str, Dict]:
        self.scan_projects()
        source_data_by_date = {}
        today_str = datetime.date.today().strftime('%Y-%m-%d')

        for root, dirs, files in os.walk(Config.ROOT_DIR):
            dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
            if FileUtils.is_excluded(root): continue

            curr_proj = None
            temp = root
            while temp.startswith(Config.ROOT_DIR):
                if temp in self.project_map: curr_proj = self.project_map[temp]; break
                temp = os.path.dirname(temp)
                if temp == os.path.dirname(temp): break
            if not curr_proj: continue

            for f in files:
                if not f.endswith('.md'): continue
                path = os.path.join(root, f)
                lines = FileUtils.read_file(path)
                if not lines: continue

                mod = False
                fname = os.path.splitext(f)[0]
                i = 0
                
                # Helper: Get raw indent ignoring Callout markers
                def get_raw_indent(s):
                    # Remove quote marker first, then strip left to count indent
                    # re.sub(r'^>\s?', '', s) handles '> ' or '>' at start
                    return len(s) - len(re.sub(r'^>\s?', '', s).lstrip())

                while i < len(lines):
                    line = lines[i]
                    # [Core] Detect ANY task marker (Naked or Dated)
                    # Check for - [ ] pattern (allowing > prefix)
                    if not re.match(r'^[\s>]*-\s*\[.\]', line):
                        i += 1
                        continue
                        
                    # --- Task Found ---
                    
                    # 1. Date Detection
                    task_date = None
                    date_match = re.search(r'[📅✅]\s*(\d{4}-\d{2}-\d{2})', line)
                    if date_match:
                        task_date = date_match.group(1)
                    else:
                        # Try New Link Format
                        link_match = re.search(r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\]\])', line)
                        if link_match: task_date = link_match.group(1)
                    
                    # [Auto-Complete] Default to Today if naked (no date found)
                    if not task_date:
                        task_date = today_str
                        mod = True
                        # Logger.info(f"Captured Naked Task in {fname}")
                        
                    # 2. Block ID
                    bid = None
                    # Strict ID Regex: Space + ^ + 6-7 Alphanum + End
                    id_m = re.search(r'(?<=\s)\^([a-zA-Z0-9]{6,7})\s*$', line)
                    if id_m: bid = id_m.group(1)
                    else:
                        # Fallback / Auto-Generate
                        bid = self.generate_block_id().replace('^', '')
                        mod = True
                        
                    # 3. Attributes & Parsing
                    indent = get_raw_indent(line)
                    status_match = re.search(r'-\s*\[(.)\]', line)
                    st = status_match.group(1) if status_match else ' '
                    clean_txt = self.clean_task_text(line, bid, context_name=fname)
                    
                    # Extract dates string (existing logic)
                    dates = " ".join(re.findall(r'([📅✅]\s*\d{4}-\d{2}-\d{2}|\[\[\d{4}-\d{2}-\d{2}#\^[a-zA-Z0-9]+\|📅\]\]|\[\[\d{4}-\d{2}-\d{2}\]\])', line))
                    
                    # [Auto-Complete] Ensure Date Link Exists if we inferred the date
                    # Only append if the date isn't already textually present in some form
                    if task_date not in line: 
                        if not dates: dates = f"[[{task_date}]]"
                        else: dates += f" [[{task_date}]]"
                        mod = True 

                    # 4. Format Line & Check for Updates
                    new_line = self.format_line(indent, st, clean_txt, dates, fname, bid, False)
                    
                    # [FIX] Callout Protection / Guard
                    # If original was quoted, ensure new_line is quoted
                    is_quoted = line.strip().startswith('>')
                    if is_quoted:
                        if not new_line.strip().startswith('>'):
                            # Prepend > and ensure spacing
                            # If new_line is "\t- ...", make it "> \t- ..."
                            # Simple prepend of "> " is standard Obsidian syntax
                            new_line = "> " + new_line
                    
                    if new_line.strip() != line.strip():
                        lines[i] = new_line
                        mod = True
                        
                    # 5. Capture & Hash
                    block, consumed = self.capture_block(lines, i)
                    combined_text = clean_txt + "|||" + self.normalize_block_content(block[1:])
                    content_hash = self.sm.calc_hash(st, combined_text)
                    
                    # 6. Store
                    if task_date not in source_data_by_date: source_data_by_date[task_date] = {}
                    source_data_by_date[task_date][bid] = {
                        'proj': curr_proj, 'bid': bid, 'pure': clean_txt, 'status': st,
                        'path': path, 'fname': fname, 'raw': block, 'hash': content_hash, 'indent': indent,
                        'dates': dates, 'is_quoted': is_quoted
                    }
                    
                    i += consumed
                
                if mod:
                    # Clean up callouts before writing
                    lines = self.inject_into_callout(lines, [])
                    lines = self.cleanup_empty_callouts(lines)
                    FileUtils.write_file(path, lines)

        return source_data_by_date

    def process_date(self, target_date, src_tasks_for_date):
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        is_past = target_date < today_str

        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{target_date}.md")

        if os.path.exists(daily_path):
            self.organize_orphans(daily_path, target_date)

        dn_tasks = {}
        new_dn_tasks = []
        dn_lines = []
        if os.path.exists(daily_path):
            dn_lines = FileUtils.read_file(daily_path) or []
            curr_ctx = None
            i = 0
            while i < len(dn_lines):
                line = dn_lines[i]
                h_m = re.match(r'^##\s*\[\[(.*?)\]\]', line.strip())
                if h_m: curr_ctx = h_m.group(1); i += 1; continue

                tm = re.match(r'^[\s>]*-\s*\[(.)\]', line)
                if tm:
                    lm = re.search(r'\[\[(.*?)\#\^([a-zA-Z0-9]{6,})\|.*?\]\]', line)
                    if lm:
                        ctx_name = lm.group(1)
                        bid = lm.group(2)
                        raw, c = self.capture_block(dn_lines, i)
                        clean = self.clean_task_text(line, bid, context_name=ctx_name)
                        st = tm.group(1)
                        # START FIX: Include sub-tasks in hash
                        combined_text = clean + "|||" + self.normalize_block_content(raw[1:])
                        content_hash = self.sm.calc_hash(st, combined_text)
                        # END FIX
                        dn_tasks[bid] = {
                            'pure': clean, 'status': st, 'idx': i, 'len': c,
                            'raw': raw, 'hash': content_hash
                        }
                        i += c;
                        continue
                    elif curr_ctx and curr_ctx in self.project_path_map:
                        if '^' not in line:
                             # [FIX] Daily Note Indent Calc (remove > even if not visible)
                             # Though Daily rarely has >, but just in case
                            raw_indent = len(line) - len(line.lstrip())
                             
                            raw, c = self.capture_block(dn_lines, i)
                            new_dn_tasks.append({
                                'proj': curr_ctx, 'idx': i, 'len': c, 'raw': raw,
                                'st': tm.group(1), 'indent': raw_indent
                            })
                            i += c;
                            continue
                        else:
                            # Fallback: Check if the line has a direct link to a known project or file
                            link_match = re.search(r'\[\[(.*?)(?:#|\||\]\])', line)
                            if link_match:
                                pot = link_match.group(1).strip()
                                pot = unicodedata.normalize('NFC', pot)
                                # Check Project Map then File Map
                                target_file = None
                                if pot in self.project_path_map: target_file = self.project_path_map[pot]
                                elif pot in self.file_path_map: target_file = self.file_path_map[pot]
                                
                                if target_file:
                                    raw_indent = len(line) - len(line.lstrip())
                                    raw, c = self.capture_block(dn_lines, i)
                                    new_dn_tasks.append({
                                        # Use 'proj' key for project name if available, or just filename
                                        'proj': self.project_map.get(os.path.dirname(target_file), pot), 
                                        'idx': i, 'len': c, 'raw': raw,
                                        'st': tm.group(1), 'indent': raw_indent
                                    })
                                    i += c;
                                    continue
                i += 1

        dn_mod = False
        if new_dn_tasks:
            Logger.info(f"处理新建任务: {len(new_dn_tasks)} 条", target_date)
            for nt in reversed(new_dn_tasks):
                p_name = nt['proj']
                txt = nt['raw'][0]
                clean = self.clean_task_text(txt)
                tgt = self.extract_routing_target(txt) or self.project_path_map.get(p_name)
                if not tgt: continue
                bid = self.generate_block_id().replace('^', '')
                fname = os.path.splitext(os.path.basename(tgt))[0]

                s_l = self.format_line(nt['indent'], nt['st'], clean, f"📅 {target_date}", fname, bid, False)
            
            # [FIX] Source Block: As Quoted
            s_children = self.normalize_child_lines(nt['raw'][1:], nt['indent'], as_quoted=True)
            s_blk = [s_l] + s_children
            
            d_l = self.format_line(nt['indent'], nt['st'], clean, "", fname, bid, True)
            
            # [FIX] Daily Block: Plain
            d_children = self.normalize_child_lines(nt['raw'][1:], nt['indent'], as_quoted=False)
            d_blk = [d_l] + d_children

            dn_lines[nt['idx']:nt['idx'] + nt['len']] = d_blk
            dn_mod = True

            sl = FileUtils.read_file(tgt) or []
            sl = self.inject_into_callout(sl, s_blk)
            
            # Probe 1: Injecting New Task
            Logger.debug_block(f"Injecting New Task into {fname}", s_blk)
            
            FileUtils.write_file(tgt, sl)
            
            # Trigger Delayed Verification
            self.trigger_delayed_verification(tgt)

            # START FIX: Include sub-tasks in hash
            combined_text = clean + "|||" + self.normalize_block_content(nt['raw'][1:])
            h = self.sm.calc_hash(nt['st'], combined_text)
            # END FIX
            self.sm.update_task(bid, h, tgt)

            # TRIGGER PIN-TO-TOP for every new task insertion
            # Although inject_into_callout is called above, calling it with empty list ensures
            # that if the callout wasn't at top (e.g. legacy file), it moves there.
            # But wait, the call above `sl = self.inject_into_callout(sl, s_blk)` ALREADY DOES IT.
            # So no extra call needed here.


        if dn_mod:
            FileUtils.write_file(daily_path, dn_lines)
            self.sm.save()
            return

        src_tasks = src_tasks_for_date
        all_ids = set(src_tasks.keys()) | set(dn_tasks.keys())
        append_to_dn = {}
        src_updates = {}
        src_deletes = {}

        for bid in all_ids:
            in_s = bid in src_tasks
            in_d = bid in dn_tasks
            last_hash = self.sm.get_task_hash(bid)

            if in_s and in_d:
                sd = src_tasks[bid]
                dd = dn_tasks[bid]
                s_changed = (sd['hash'] != last_hash)
                d_changed = (dd['hash'] != last_hash)

                if s_changed and not d_changed:
                    blk = self.reconstruct_daily_block(sd, target_date)
                    
                    # Probe 2: Updating Daily Note from Source
                    Logger.debug_block(f"Updating Daily Note from Source {sd['fname']}", blk)
                    
                    dn_lines[dd['idx']:dd['idx'] + dd['len']] = blk
                    dn_mod = True
                    self.sm.update_task(bid, sd['hash'], sd['path'])

                elif d_changed and not s_changed:
                    n_l = self.format_line(sd['indent'], dd['status'], dd['pure'], f"📅 {target_date}", sd['fname'], bid,
                                           False)
                    was_quoted = sd.get('is_quoted', False)
                    if was_quoted and not n_l.strip().startswith('>'): n_l = f"> {n_l}"

                    blk = [n_l]
                    for child in dd['raw'][1:]:
                        if was_quoted and not child.strip().startswith('>'):
                            blk.append(f"> {child}")
                        else:
                            blk.append(child)

                    if sd['path'] not in src_updates: src_updates[sd['path']] = {}
                    
                    # Probe 3: Preparing Source Update (Logged when batch is processed, but log content here too?)
                    # White-box: show what we queuing.
                    Logger.debug_block(f"Queueing Update for Source {sd['fname']}", blk)
                    
                    src_updates[sd['path']][bid] = blk
                    self.sm.update_task(bid, dd['hash'], sd['path'])

                elif s_changed and d_changed:
                    if sd['hash'] != dd['hash']:
                        Logger.info(f"冲突检测 {bid}: 优先保留 Daily 修改", target_date)
                        n_l = self.format_line(sd['indent'], dd['status'], dd['pure'], f"📅 {target_date}", sd['fname'],
                                               bid, False)
                        was_quoted = sd.get('is_quoted', False)
                        if was_quoted and not n_l.strip().startswith('>'): n_l = f"> {n_l}"

                        blk = [n_l]
                        for child in dd['raw'][1:]:
                            if was_quoted and not child.strip().startswith('>'):
                                blk.append(f"> {child}")
                            else:
                                blk.append(child)

                        if sd['path'] not in src_updates: src_updates[sd['path']] = {}
                        src_updates[sd['path']][bid] = blk
                        self.sm.update_task(bid, dd['hash'], sd['path'])
                else:
                    if last_hash is None: self.sm.update_task(bid, sd['hash'], sd['path'])

            elif in_s and not in_d:
                sd = src_tasks[bid]
                
                # Check 1: History Protection (Past Date) -> FORCE RESTORE
                if is_past:
                    Logger.info(f"历史保护: 检测到旧日记({target_date})缺失任务 {bid}，强制回写", target_date)
                    if sd['proj'] not in append_to_dn: append_to_dn[sd['proj']] = []
                    append_to_dn[sd['proj']].append(sd)
                    self.sm.update_task(bid, sd['hash'], sd['path'])

                # Check 2: Normal Deletion (Today or Future) -> Allow Deletion
                elif last_hash:
                    Logger.info(f"离线同步: 检测到 Daily 删除 {bid}，移除 Source", target_date)
                    if sd['path'] not in src_deletes: src_deletes[sd['path']] = {}
                    src_deletes[sd['path']][bid] = sd['path']
                    self.sm.remove_task(bid)

                # Check 3: New Task in Source -> Add to Daily
                else:
                    if sd['proj'] not in append_to_dn: append_to_dn[sd['proj']] = []
                    append_to_dn[sd['proj']].append(sd)
                    self.sm.update_task(bid, sd['hash'], sd['path'])

            elif in_d and not in_s:
                dd = dn_tasks[bid]
                if last_hash:
                    Logger.info(f"离线同步: 检测到 Source 删除 {bid}，移除 Daily", target_date)
                    for k in range(dd['idx'], dd['idx'] + dd['len']): dn_lines[k] = "__DEL__\n"
                    dn_mod = True
                    self.sm.remove_task(bid)
                else:
                    self.sm.update_task(bid, dd['hash'], "UNKNOWN")

        if dn_mod: dn_lines = [x for x in dn_lines if x != "__DEL__\n"]

        for path, bids in src_deletes.items():
            sl = FileUtils.read_file(path)
            if not sl: continue
            out, i, chg = [], 0, False
            deleted_bids = list(bids.keys())
            while i < len(sl):
                im = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', sl[i])
                if not im: im = re.search(r'\(connect::.*?\^([a-zA-Z0-9]{6,})\)', sl[i])
                if im and im.group(1) in deleted_bids:
                    _, c = self.capture_block(sl, i);
                    i += c;
                    chg = True
                else:
                    out.append(sl[i]); i += 1
            if chg:
                # Force Pin-to-Top even on deletion (to move remaining tasks)
                stem = os.path.splitext(os.path.basename(path))[0]
                out = self.inject_into_callout(out, [], stem)
                out = self.cleanup_empty_callouts(out)
                
                # [FIX 1] Sanitize List
                out = [l for l in out if l is not None]
                
                FileUtils.write_file(path, out)

        for path, ups in src_updates.items():
            sl = FileUtils.read_file(path)
            if not sl: continue
            out, i, chg = [], 0, False
            while i < len(sl):
                im = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', sl[i])
                if not im: im = re.search(r'\(connect::.*?\^([a-zA-Z0-9]{6,})\)', sl[i])
                if im and im.group(1) in ups:
                    _, c = self.capture_block(sl, i)
                    out.extend(ups[im.group(1)])
                    i += c;
                    chg = True
                else:
                    out.append(sl[i]); i += 1
            if chg:
                # Force Pin-to-Top (re-inject empty) then Cleanup
                stem = os.path.splitext(os.path.basename(path))[0]
                out = self.inject_into_callout(out, [], stem)
                out = self.cleanup_empty_callouts(out)
                
                # Probe 4: Batch Source Update
                Logger.debug_block(f"Batch Updating Source {os.path.basename(path)}", out)
                
                # [FIX 1] Sanitize List: Remove None values to prevent crash
                out = [l for l in out if l is not None]
                
                FileUtils.write_file(path, out)
                self.trigger_delayed_verification(path)
                Logger.info(f"源内容同步: {os.path.basename(path)}", target_date)

        if append_to_dn:
            try:
                j_idx = next(i for i, l in enumerate(dn_lines) if l.strip() == "# Journey")
            except:
                j_idx = 0
            end_pt = len(dn_lines)
            for i in range(j_idx + 1, len(dn_lines)):
                if dn_lines[i].startswith('# '): end_pt = i; break

            offset = 0
            for proj, tasks in append_to_dn.items():
                header = f"## [[{proj}]]"
                h_idx = -1
                curr_search_end = end_pt + offset
                for k in range(j_idx, curr_search_end):
                    if dn_lines[k].strip() == header: h_idx = k; break

                txt_blk = []
                for t in tasks:
                    l1 = self.format_line(t['indent'], t['status'], t['pure'], "", t['fname'], t['bid'], True)
                    txt_blk.extend([l1] + t['raw'][1:])
                    if not txt_blk[-1].endswith('\n'): txt_blk[-1] += '\n'

                if h_idx != -1:
                    ins = curr_search_end
                    for k in range(h_idx + 1, curr_search_end):
                        if dn_lines[k].startswith('#'): ins = k; break
                    dn_lines[ins:ins] = txt_blk
                    offset += len(txt_blk)
                else:
                    chunk = [f"\n{header}\n"] + txt_blk
                    dn_lines[end_pt + offset:end_pt + offset] = chunk
                    offset += len(chunk)

            if offset > 0: dn_mod = True

        dn_lines, cleaned = self.cleanup_empty_headers(dn_lines, target_date)
        if cleaned: dn_mod = True
        
        # --- [FIX START] Prevent Ping-Pong Loop ---
        # Forcefully clean the tail of the Daily Note
        original_len = len(dn_lines)
        dn_lines = self.aggressive_daily_clean(dn_lines)
        if len(dn_lines) != original_len:
            dn_mod = True # Ensure we save if we cleaned something
        # --- [FIX END] ---

        if dn_mod:
            # [FIX 1] Sanitize Daily Note lines too, just in case
            dn_lines = [l for l in dn_lines if l is not None]

            FileUtils.write_file(daily_path, dn_lines)
            Logger.info("Daily Note 更新完成", target_date)

        self.sm.save()

