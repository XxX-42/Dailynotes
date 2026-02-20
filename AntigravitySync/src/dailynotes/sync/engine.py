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
from ..utils import Logger, FileUtils
from .discovery import scan_projects
from .task_registry import get_registry, TaskRegistry
from .parsing import (
    clean_task_text, 
    normalize_block_content, 
    extract_routing_target,
    extract_routing_info,
    capture_block, 
    get_indent_depth
)
from .rendering import (
    reconstruct_daily_block, 
    format_line, 
    normalize_child_lines, 
    ensure_structure, 
    cleanup_empty_headers, 
    inject_into_task_section
)

class SyncCore:
    def __init__(self, state_manager):
        self.sm = state_manager
        self.project_map = {}
        self.project_path_map = {}
        self.file_path_map = {}
        
        # [P1 FIX] Anti-infinite-loop: track sync frequency per task
        self._sync_counter = {}  # {bid: count}
        self._sync_counter_reset_time = time.time()
        self._SYNC_THRESHOLD = 5  # Max syncs per task per reset period
        self._RESET_INTERVAL = 60  # Reset counters every 60 seconds
        
        # [v1.8] TaskRegistry for incremental sync
        self._task_registry: TaskRegistry = get_registry()
        self._registry_initialized = False

    def trigger_delayed_verification(self, filepath, delay=10):
        def _job():
            time.sleep(delay)
            content = FileUtils.read_file(filepath) or []
            Logger.debug_block(f"VERIFICATION (T+{delay}s) Snapshot: {os.path.basename(filepath)}", content)

        t = threading.Thread(target=_job, daemon=True)
        t.start()

    def _check_sync_loop(self, bid: str) -> bool:
        """
        [P1 FIX] Check if a task is being synced too frequently (possible infinite loop).
        Returns True if sync should proceed, False if it should be skipped.
        """
        now = time.time()
        
        # Reset counters periodically
        if now - self._sync_counter_reset_time > self._RESET_INTERVAL:
            self._sync_counter.clear()
            self._sync_counter_reset_time = now
        
        # Increment counter
        self._sync_counter[bid] = self._sync_counter.get(bid, 0) + 1
        
        if self._sync_counter[bid] > self._SYNC_THRESHOLD:
            Logger.error_once(f"loop_detect_{bid}", 
                f"⚠️ [LOOP DETECT] 任务 {bid} 同步次数过多 ({self._sync_counter[bid]}x/分钟)，已暂停同步")
            return False
        return True

    def generate_block_id(self):
        return '^' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    def scan_projects(self):
        # Delegate to discovery module
        self.project_map, self.project_path_map, self.file_path_map = scan_projects()

    def scan_all_source_tasks(self) -> Dict[str, Dict]:
        """
        [v1.8 REFACTORED] Now uses TaskRegistry for cached lookups.
        Only performs full scan if registry is not initialized.
        """
        self.scan_projects()
        
        # Initialize registry if needed (first run)
        if not self._registry_initialized:
            self.initialize_registry()
        
        # Return cached data from registry
        return self._task_registry.get_all_tasks_by_date()
    
    def initialize_registry(self) -> None:
        """
        [v1.8] Initialize the TaskRegistry with a full scan.
        This is called ONCE at startup.
        """
        if self._registry_initialized:
            Logger.debug("[SyncCore] Registry already initialized, skipping")
            return
        
        Logger.info("🚀 [SyncCore] 初始化 TaskRegistry (一次性全量扫描)...")
        self.scan_projects()  # Ensure project map is current
        self._task_registry.initialize(self.project_map, self.sm)
        self._registry_initialized = True
        Logger.info("✅ [SyncCore] TaskRegistry 初始化完成")
    
    def process_file_event(self, filepath: str) -> Set[str]:
        """
        [v1.8] Process a file change event incrementally.
        
        This is the NEW entry point for watchdog events, replacing the
        full scan_all_source_tasks() call in the runtime loop.
        
        Args:
            filepath: Absolute path to the changed file
            
        Returns:
            Set of date strings that were affected by this file change
        """
        # Ensure registry is initialized
        if not self._registry_initialized:
            self.initialize_registry()
        
        # Update project map if needed (for new files in new directories)
        self.scan_projects()
        self._task_registry.refresh_project_map(self.project_map)
        
        # Incremental update: only rescan this ONE file
        affected_dates = self._task_registry.update_file(filepath, self.sm)
        
        Logger.debug(f"[SyncCore] 增量更新: {os.path.basename(filepath)} -> 影响日期: {affected_dates}")
        
        return affected_dates
    
    def get_tasks_for_date(self, date_str: str) -> Dict[str, Dict]:
        """
        [v1.8] Get tasks for a specific date from the registry.
        Fast O(1) lookup.
        
        Args:
            date_str: Date in YYYY-MM-DD format
            
        Returns:
            Dictionary of { bid: task_dict }
        """
        if not self._registry_initialized:
            self.initialize_registry()
        
        return self._task_registry.get_tasks_by_date(date_str)

    def complete_task_by_title(self, title: str, date_str: str) -> bool:
        """
        [v3.8] Mark a task as completed by title matching.
        Searches in tasks associated with the given date.
        """
        tasks = self.get_tasks_for_date(date_str)
        matched = False
        
        for bid, task in tasks.items():
            # Loose matching: strip whitespace
            if task.get('pure', '').strip() == title.strip():
                if task.get('status') == 'x':
                    return True # Already done
                
                # Perform Update
                file_path = task['path']
                if self._update_task_status_in_file(file_path, bid, 'x'):
                    matched = True
                    Logger.info(f"   ✅ [SyncCore] Marking task completed: {title}")
                    # Refresh registry for this file immediately
                    self.process_file_event(file_path)
                break
        
        return matched

    def _update_task_status_in_file(self, filepath, bid, new_status):
        """
        Helper to safely update status in a file given a block ID.
        """
        if not os.path.exists(filepath):
            return False
            
        lines = FileUtils.read_file(filepath)
        if not lines: return False
        
        modified = False
        for i, line in enumerate(lines):
            if bid in line:
                # Regex replace status
                # Pattern: - [char]
                # Careful not to destroy formatting
                if re.search(r'^\s*-\s*\[.\]', line):
                    new_line = re.sub(r'(-\s*\[).(\])', fr'\g<1>{new_status}\g<2>', line, 1)
                    if new_line != line:
                        lines[i] = new_line
                        modified = True
                    break
        
        if modified:
            Logger.debug(f"   💾 [UPDATE] Status Change ({new_status}) -> {os.path.basename(filepath)}")
            return FileUtils.write_file(filepath, lines)
        return False
        
    def calculate_nearest_project(self, routing_path):
        """
        Traverses up from the routing path to find the nearest ancestor project.
        Also explicitly matches if the routing_path itself IS a main project.
        """
        if not routing_path: return None
        
        # 1. Exact direct match (Is the routing path precisely a `main` project?)
        import unicodedata
        norm_routing = unicodedata.normalize('NFC', routing_path)
        for p_name, p_path in self.project_path_map.items():
            if unicodedata.normalize('NFC', p_path) == norm_routing:
                return p_name
        
        # [FIX] Start searching from the directory of the file itself
        # so same-level main projects are correctly discovered.
        curr_search = os.path.dirname(routing_path)
        
        # Traverse upwards
        while curr_search.startswith(Config.ROOT_DIR):
            if curr_search in self.project_map:
                return self.project_map[curr_search]
            
            parent = os.path.dirname(curr_search)
            if parent == curr_search: break 
            curr_search = parent
        return None

    def dispatch_project_tasks(self, filepath, date_tag):
        """
        [Replaces organize_orphans]
        Responsible for moving tasks from Daily Note to their respective Project files.
        Implements:
        1. Nearest Ancestor Resolution (Nested Projects).
        2. Robust Matching for Headers.
        3. Dynamic Stale Link Removal (only for generated links).
        4. Correction Move: Moves tasks even if they are already under a project header, if that header is wrong.
        5. Link Preservation: If a task has an existing link, it is moved AS-IS.
        """
        lines = FileUtils.read_file(filepath)
        if not lines: return set()
        lines = ensure_structure(lines)
        tasks_to_move = []
        processed_bids = set()
        
        current_header_project = None
        ctx = "ROOT"
        
        i = 0
        while i < len(lines):
            l = lines[i].strip()
            
            # Context Detection
            m_header = re.match(r'^##\s*\[\[(.*?)\]\]', l)
            if m_header:
                current_header_project = m_header.group(1).split('|')[0]
                ctx = 'PROJECT'
                i += 1
                continue
            
            if l.startswith('# '):
                current_header_project = None 
                if l == '# Journey': ctx = 'JOURNEY'
                elif l == '# Day planner': ctx = 'PLANNER'
                else: ctx = 'OTHER'
                i += 1; continue
            
            # Capture Tasks
            if re.match(r'^[\s>]*-\s*\[.\]', lines[i]):
                is_task_candidate = False
                if ctx in ['JOURNEY', 'PLANNER']: is_task_candidate = True
                if ctx == 'PROJECT': is_task_candidate = True
                
                if is_task_candidate:
                    # 1. Routing Info
                    routing_path, raw_link_text = extract_routing_info(lines[i], self.file_path_map)
                    
                    # 2. Calculate Correct Target
                    target_p_name = self.calculate_nearest_project(routing_path)
                    
                    # [RESTORE] ORIGINAL WANDERER LOGIC
                    # Users want tasks with `#A, #B, #C, #D` to be archived to Orphans if they
                    # don't strictly belong to an explicitly matching known project.
                    should_move = False
                    
                    st_m = re.search(r'-\s*\[(.)\]', lines[i])
                    status = st_m.group(1) if st_m else ' '
                    has_sync_tag = bool(re.search(r'#[A-D]\b', lines[i]))
                    
                    if not target_p_name:
                        # [BUG] 这里原本如果目标不存在就直接跳过（导致流浪者完全被无视）
                        # 今天原本是要修这个 BUG 的，按照您的要求，先完全退回到没修之前的旧代码
                        should_move = False
                    elif ctx in ['JOURNEY', 'PLANNER']:
                        should_move = True
                    elif ctx == 'PROJECT' and current_header_project:
                        if current_header_project != target_p_name:
                            Logger.info(f"   ⚖️ 纠偏移动 ({date_tag}): {current_header_project} -> {target_p_name}")
                            should_move = True
                            
                    if should_move:
                        content, length = capture_block(lines, i)
                        raw_first = content[0]
                        
                        # [NEW] Link Preservation Check
                        has_existing_link = ('[[' in raw_first) and (']]' in raw_first)
                        
                        final_head_line = raw_first
                        current_bid = None

                        # === UNIFIED STRATEGY: Always format properly ===
                        # Extract or generate block ID
                        bid_m = re.search(r'(?:\^([a-zA-Z0-9]{6,})\s*$|<span id="([a-zA-Z0-9]{6,})"(?: data-timestamps="([^"]*)")?></span>)', raw_first)
                        bid = (bid_m.group(1) or bid_m.group(2)) if bid_m else self.generate_block_id().replace('^', '')
                        data_ts = bid_m.group(3) if bid_m and len(bid_m.groups()) >= 3 else None
                        current_bid = bid

                        # Extract indentation
                        indent_len = len(raw_first) - len(raw_first.lstrip())
                        indent_str = raw_first[:indent_len]

                        # Extract status
                        st_m = re.search(r'-\s*\[(.)\]', raw_first)
                        status = st_m.group(1) if st_m else ' '

                        # [FIX] Extract time (critical for preserving Day Planner times)
                        time_part = ""
                        body_only = re.sub(r'^\s*-\s*\[.\]\s?', '', raw_first)
                        tm = re.match(r'^(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)', body_only)
                        if tm: 
                            time_part = tm.group(1) 

                        # Extract sync tag for formatting
                        sync_tag_m = re.search(r'(#[A-D]\b)', raw_first)
                        sync_tag = sync_tag_m.group(1) if sync_tag_m else ''

                        if has_existing_link:
                            # === STRATEGY A: Link Preservation with proper formatting ===
                            # Keep existing links but inject return link and ID
                            
                            # Clean the text but preserve existing links
                            # Remove: status, indent, time (will re-add), ID (will re-add)
                            clean_pure = re.sub(r'^[\s>]*-\s*\[.\]\s?', '', raw_first)
                            clean_pure = re.sub(r'^\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?\s*', '', clean_pure)
                            clean_pure = re.sub(r'\^[a-zA-Z0-9]{6,}\s*$', '', clean_pure)
                            clean_pure = re.sub(r'<span id="[a-zA-Z0-9]{6,}"(?: data-timestamps="[^"]*")?></span>', '', clean_pure)

                            # [FIX] Remove existing return links to prevent duplication
                            clean_pure = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', clean_pure)

                            # [FIX] Remove routing markers like "## [[ProjectName]]" - they're only for specifying target
                            clean_pure = re.sub(r'##\s*\[\[[^\]]+\]\]', '', clean_pure)

                            if sync_tag:
                                clean_pure = clean_pure.replace(sync_tag, '').strip()
                            clean_pure = re.sub(r'\s+', ' ', clean_pure).strip()
                            
                            # [FIX] Return link target logic
                            ret_target = target_p_name
                            # Extract potential file links from the cleaned content
                            m_links = re.findall(r'\[\[(.*?)(?:[\|#].*)?\]\]', clean_pure)
                            if m_links:
                                ret_target = m_links[0]
                            
                            # Build return link with span ID prefix
                            span_id = f'<span id="{bid}" data-timestamps="{data_ts}"></span>' if data_ts else f'<span id="{bid}"></span>'
                            ret_link = f"[[{ret_target}#^{bid}|⮐]]"
                            
                            # Format final line: time + span_id + sync_tag + return link + preserved content
                            time_str = f"{time_part} " if time_part else ""
                            sync_str = f"{sync_tag} " if sync_tag else ""
                            final_head_line = f"{indent_str}- [{status}] {time_str}{span_id} {sync_str}{ret_link} {clean_pure}\n"
                            
                            Logger.info(f"   🚚 搬运任务 (保留原链接+时间): {bid}")
                            
                        else:
                            # === STRATEGY B: Clean & Generate === (Original Logic)
                            # Clean Text (removes time, which is already extracted)
                            clean_pure = clean_task_text(raw_first, bid, target_p_name)
                            
                            # Dynamic Stale Link Removal
                            if raw_link_text:
                                m = re.match(r'\[\[(.*?)(?:[\|#].*)?\]\]', raw_link_text)
                                if m:
                                    link_core = m.group(1)
                                    if link_core != target_p_name:
                                        clean_pure = clean_pure.replace(raw_link_text, "").strip()

                            # Standard Cleaning
                            known_projects = set(self.project_path_map.keys())
                            existing_links = re.findall(r'\[\[(.*?)\]\]', clean_pure)
                            for link in existing_links:
                                link_clean = link.split('|')[0].split('#')[0] 
                                if link_clean in known_projects and link_clean != target_p_name:
                                    clean_pure = re.sub(rf'\[\[{re.escape(link)}.*?\]\]', '', clean_pure).strip()

                            # [FIX] Return link should point to the original file if possible, not the project main file
                            ret_target = target_p_name
                            if raw_link_text:
                                m = re.match(r'\[\[(.*?)(?:[\|#].*)?\]\]', raw_link_text)
                                if m:
                                    ret_target = m.group(1)

                            ret_link = f"[[{ret_target}#^{bid}|⮐]]"

                            target_tag = f"[[{target_p_name}]]"
                            if target_tag in clean_pure:
                                file_tag = "" 
                            else:
                                file_tag = f" {target_tag}"
                            
                            if sync_tag:
                                clean_pure = clean_pure.replace(sync_tag, '').strip()
                            clean_pure = re.sub(r'\s+', ' ', clean_pure).strip()
                            
                            # [FIX] Use span_id prefix instead of trailing ^bid
                            span_id = f'<span id="{bid}" data-timestamps="{data_ts}"></span>' if data_ts else f'<span id="{bid}"></span>'
                            
                            time_str = f"{time_part} " if time_part else ""
                            sync_str = f"{sync_tag} " if sync_tag else ""
                            final_head_line = f"{indent_str}- [{status}] {time_str}{span_id} {sync_str}{ret_link}{file_tag} {clean_pure}\n"

                        content[0] = final_head_line
                        tasks_to_move.append({'idx': i, 'len': length, 'proj': target_p_name, 'raw': content})
                        if current_bid: processed_bids.add(current_bid)
                        i += length
                        continue
            i += 1
        
        if not tasks_to_move: return set()
        
        # Remove moved tasks check
        tasks_to_move.sort(key=lambda x: x['idx'], reverse=True)
        for t in tasks_to_move: del lines[t['idx']:t['idx'] + t['len']]
        
        # Group
        grouped = {}
        for t in tasks_to_move:
            if t['proj'] not in grouped: grouped[t['proj']] = []
            grouped[t['proj']].extend(t['raw'])
            
        # === Logic 4: Safe Insertion ===
        j_idx = -1
        for idx, line in enumerate(lines):
            if line.strip() == "# Journey":
                j_idx = idx
                break
        
        if j_idx == -1: j_idx = len(lines)
        
        ins_pt = len(lines)
        for i in range(j_idx + 1, len(lines)):
            if lines[i].startswith('# '): 
                ins_pt = i
                break
                
        offset = 0
        for proj, blocks in grouped.items():
            target_header_clean = f"## [[{proj}]]".replace(" ", "")
            h_idx = -1
            for k in range(j_idx, ins_pt + offset):
                current_line_clean = lines[k].strip().replace(" ", "")
                if current_line_clean == target_header_clean:
                    h_idx = k
                    break
            
            if blocks and not blocks[-1].endswith('\n'): blocks[-1] += '\n'
            
            if h_idx != -1:
                sub_ins = ins_pt + offset
                for k in range(h_idx + 1, ins_pt + offset):
                    if lines[k].startswith('#'): 
                        sub_ins = k
                        break
                lines[sub_ins:sub_ins] = blocks
                offset += len(blocks)
            else:
                chunk = [f"\n## [[{proj}]]\n"] + blocks
                lines[ins_pt + offset:ins_pt + offset] = chunk
                offset += len(chunk)
                
        Logger.info(f"归档 {len(tasks_to_move)} 个流浪/纠偏任务", date_tag)
        Logger.info(f"   💾 [WRITE] 更新归档文件: {os.path.basename(filepath)}")
        if FileUtils.write_file(filepath, lines): return processed_bids
        return set()

    def process_date(self, target_date, src_tasks_for_date):
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{target_date}.md")

        # [NEW] 模版初始化
        if not os.path.exists(daily_path) and src_tasks_for_date:
            if os.path.exists(Config.TEMPLATE_FILE):
                try:
                    tmpl_lines = FileUtils.read_file(Config.TEMPLATE_FILE)
                    if tmpl_lines:
                        Logger.info(f"   📄 [TEMPLATE] 检测到未来/缺失日记，正在从模版创建: {target_date}.md")
                        FileUtils.write_file(daily_path, tmpl_lines)
                        time.sleep(0.1)
                except Exception as e:
                    Logger.error_once(f"tmpl_fail_{target_date}", f"模版创建失败: {e}")
            else:
                Logger.info(f"   ⚠️ 未找到模版文件 ({Config.REL_TEMPLATE_FILE})，创建基础骨架: {target_date}.md")
                base_scaffold = ["# Day planner\n", "\n", "# Journey\n", "\n"]
                FileUtils.write_file(daily_path, base_scaffold)

        organized_bids = set()
        if os.path.exists(daily_path): 
            # Use new dispatch method with Correction logic & Link Preservation
            organized_bids = self.dispatch_project_tasks(daily_path, target_date)
            
        dn_tasks = {}
        new_dn_tasks = []
        dn_lines = []
        if os.path.exists(daily_path):
            dn_lines = FileUtils.read_file(daily_path) or []
            curr_ctx = None;
            current_section = None;
            i = 0
            while i < len(dn_lines):
                line = dn_lines[i]
                if line.startswith('# '): current_section = line.strip()
                h_m = re.match(r'^##\s*\[\[(.*?)\]\]', line.strip())
                if h_m: curr_ctx = h_m.group(1); i += 1; continue
                tm = re.match(r'^[\s>]*-\s*\[(.)\]', line)
                if tm:
                    is_allowed_section = False
                    if current_section in Config.DAILY_NOTE_SECTIONS: is_allowed_section = True
                    if not is_allowed_section: i += 1; continue
                    lm = re.search(r'\[\[(.*?)\#\^([a-zA-Z0-9]{6,})\|.*?\]\]', line)
                    if lm:
                        ctx_name = lm.group(1);
                        bid = lm.group(2)
                        raw, c = capture_block(dn_lines, i)
                        clean = clean_task_text(line, bid, context_name=ctx_name)
                        st = tm.group(1)
                        combined_text = clean + "|||" + normalize_block_content(raw[1:])
                        content_hash = self.sm.calc_hash(st, combined_text)

                        # [MODIFIED] Store indent for reconstruction
                        indent_val = get_indent_depth(line)
                        dn_tasks[bid] = {'pure': clean, 'status': st, 'idx': i, 'len': c, 'raw': raw,
                                         'hash': content_hash, 'proj': curr_ctx, 'indent': indent_val}
                        i += c;
                        continue
                    elif curr_ctx and curr_ctx in self.project_path_map:
                        if '^' not in line:
                            raw_indent = get_indent_depth(line)  # [MODIFIED]
                            raw, c = capture_block(dn_lines, i)
                            new_dn_tasks.append({'proj': curr_ctx, 'idx': i, 'len': c, 'raw': raw, 'st': tm.group(1),
                                                 'indent': raw_indent})
                            i += c;
                            continue
                        else:
                            link_match = re.search(r'\[\[(.*?)(?:#|\||\]\])', line)
                            if link_match:
                                pot = link_match.group(1).strip()
                                pot = unicodedata.normalize('NFC', pot)
                                target_file = None
                                if pot in self.project_path_map:
                                    target_file = self.project_path_map[pot]
                                elif pot in self.file_path_map:
                                    target_file = self.file_path_map[pot]
                                if target_file:
                                    raw_indent = get_indent_depth(line)  # [MODIFIED]
                                    raw, c = capture_block(dn_lines, i)
                                    new_dn_tasks.append(
                                        {'proj': self.project_map.get(os.path.dirname(target_file), pot), 'idx': i,
                                         'len': c, 'raw': raw, 'st': tm.group(1), 'indent': raw_indent})
                                    i += c;
                                    continue
                i += 1

        dn_mod = False
        if new_dn_tasks:
            Logger.info(f"   [NEW] 发现 {len(new_dn_tasks)} 个待注册任务")
            for nt in reversed(new_dn_tasks):
                p_name = nt['proj'];
                txt = nt['raw'][0];
                clean = clean_task_text(txt)
                tgt = extract_routing_target(txt, self.file_path_map) or self.project_path_map.get(p_name)
                if not tgt: continue
                bid = self.generate_block_id().replace('^', '')
                fname = os.path.splitext(os.path.basename(tgt))[0]
                Logger.info(f"   ➕ 注册任务 {bid}:")
                s_l = format_line(nt['indent'], nt['st'], clean, target_date, fname, bid, False)
                # [MODIFIED] Pass source_parent_indent
                s_blk = [s_l] + normalize_child_lines(nt['raw'][1:], nt['indent'],
                                                           source_parent_indent=nt['indent'], as_quoted=True)
                d_l = format_line(nt['indent'], nt['st'], clean, "", fname, bid, True)
                d_blk = [d_l] + normalize_child_lines(nt['raw'][1:], nt['indent'],
                                                           source_parent_indent=nt['indent'], as_quoted=False)

                dn_lines[nt['idx']:nt['idx'] + nt['len']] = d_blk
                dn_mod = True
                sl = FileUtils.read_file(tgt) or []
                sl = inject_into_task_section(sl, s_blk)
                # [FIX] 显式比对，防止 None 导致丢包
                orig_sl = FileUtils.read_file(tgt) or []
                if "".join(sl) != "".join(orig_sl):
                    # === 🎯 第一次日志修改 (New Task) ===
                    Logger.info(f"   💾 [WRITE] 写入源文件 (New Task) (from {target_date}): {os.path.basename(tgt)}")
                    FileUtils.write_file(tgt, sl)
                self.trigger_delayed_verification(tgt)
                combined_text = clean + "|||" + normalize_block_content(nt['raw'][1:])
                h = self.sm.calc_hash(nt['st'], combined_text)
                self.sm.update_task(bid, h, tgt, target_date)
        if dn_mod:
            Logger.info(f"   💾 [WRITE] 更新日记文件 (Sync Pre-Save): {os.path.basename(daily_path)}")
            FileUtils.write_file(daily_path, dn_lines)
            self.sm.save()

        src_tasks = src_tasks_for_date
        all_ids = set(src_tasks.keys()) | set(dn_tasks.keys())
        append_to_dn = {}
        src_updates = {}
        src_deletes = {}

        for bid in all_ids:
            # [v1.3 FIX] 激活死循环拦截器，阻断同步震荡
            if not self._check_sync_loop(bid):
                continue
                
            in_s = bid in src_tasks
            in_d = bid in dn_tasks
            last_hash = self.sm.get_task_hash(bid);
            last_date = self.sm.get_task_date(bid)
            if in_s:
                sd = src_tasks[bid]
                if in_d:
                    dd = dn_tasks[bid]
                    s_changed = (sd['hash'] != last_hash);
                    d_changed = (dd['hash'] != last_hash)
                    if s_changed and not d_changed:
                        Logger.info(f"   🔄 S->D 同步 ({bid}):")
                        # [FIX] 提取当前日记行中的时间，防止被源文件覆盖
                        old_daily_line = dd['raw'][0]
                        time_match = re.search(r'(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)', old_daily_line)
                        preserved_time = time_match.group(1) if time_match else None
                        blk = reconstruct_daily_block(sd, target_date, preserved_time=preserved_time)
                        dn_lines[dd['idx']:dd['idx'] + dd['len']] = blk
                        dn_mod = True
                        self.sm.update_task(bid, sd['hash'], sd['path'], target_date)
                    elif d_changed and not s_changed:
                        Logger.info(f"   🔄 D->S 同步 ({bid}):")
                        n_l = format_line(sd['indent'], dd['status'], dd['pure'], target_date, sd['fname'], bid,
                                               False)
                        # [MODIFIED] Pass source_parent_indent (using daily indent)
                        blk = [n_l] + normalize_child_lines(dd['raw'][1:], sd['indent'],
                                                                 source_parent_indent=dd['indent'], as_quoted=False)
                        if sd['path'] not in src_updates: src_updates[sd['path']] = {}
                        src_updates[sd['path']][bid] = blk
                        self.sm.update_task(bid, dd['hash'], sd['path'], target_date)
                    elif s_changed and d_changed:
                        if sd['hash'] != dd['hash']:
                            # [FIX] 冲突仲裁：基于 mtime 的最后修改优先
                            target_mtime = 0
                            daily_mtime = 0
                            try:
                                if os.path.exists(sd['path']): target_mtime = os.path.getmtime(sd['path'])
                                if os.path.exists(daily_path): daily_mtime = os.path.getmtime(daily_path)
                            except Exception as e:
                                Logger.error(f"   ⚠️ 无法获取文件时间: {e}")

                            # 容差 1秒
                            if target_mtime > daily_mtime + 1.0:
                                # Source Wins
                                Logger.info(f"   ⚔️ 冲突 ({bid}): Source 覆盖 Daily (Source is newer, Δ={target_mtime - daily_mtime:.1f}s)")
                                # S->D Logic
                                old_daily_line = dd['raw'][0]
                                time_match = re.search(r'(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)', old_daily_line)
                                preserved_time = time_match.group(1) if time_match else None
                                blk = reconstruct_daily_block(sd, target_date, preserved_time=preserved_time)
                                dn_lines[dd['idx']:dd['idx'] + dd['len']] = blk
                                dn_mod = True
                                self.sm.update_task(bid, sd['hash'], sd['path'], target_date)
                            else:
                                # Daily Wins (Default if close or Daily newer)
                                reason = "Daily is newer" if daily_mtime > target_mtime else "Default Policy"
                                Logger.info(f"   ⚔️ 冲突 ({bid}): Daily 覆盖 Source ({reason})")
                                n_l = format_line(sd['indent'], dd['status'], dd['pure'], target_date, sd['fname'],
                                                       bid, False)
                                # [MODIFIED] Conflict resolution using Daily structure
                                blk = [n_l] + normalize_child_lines(dd['raw'][1:], sd['indent'],
                                                                         source_parent_indent=dd['indent'], as_quoted=False)
                                if sd['path'] not in src_updates: src_updates[sd['path']] = {}
                                src_updates[sd['path']][bid] = blk
                                self.sm.update_task(bid, dd['hash'], sd['path'], target_date)

                        else:
                            # [Fixed] 状态稳定时仅更新心跳，不触发文件写入
                            # if sd['path'] not in src_updates: src_updates[sd['path']] = {}
                            # src_updates[sd['path']][bid] = sd['raw']
                            self.sm.update_task(bid, sd['hash'], sd['path'], target_date)
                else:
                    # ======================================================
                    # [BRANCH B] 源文件有，但日记无
                    # 场景判断：是用户在源文件新加了任务（应追加日记），
                    # 还是用户在日记删除了任务（应删源文件）？
                    # ======================================================
                    
                    # 获取历史状态
                    has_history = bid in self.sm.state
                    
                    if has_history and last_date == target_date:
                        # ============================
                        # 情况 1：历史存在且日期匹配
                        # 需要用 mtime 仲裁
                        # ============================
                        daily_mtime = FileUtils.get_mtime(daily_path) if os.path.exists(daily_path) else 0
                        source_mtime = FileUtils.get_mtime(sd['path']) if os.path.exists(sd['path']) else 0
                        
                        # 容差判定：如果时间差 <= 1秒，倾向于保活
                        time_delta = daily_mtime - source_mtime
                        
                        if time_delta > 1:
                            # 日记更新更近，但任务消失了 -> 用户在日记删除了任务
                            Logger.info(f"   🗑️ 删除 Source ({bid}): 日记较新且已移除 (Daily Deletion, Δ={int(time_delta)}s)")
                            if sd['path'] not in src_deletes: src_deletes[sd['path']] = {}
                            src_deletes[sd['path']][bid] = sd['path']
                            self.sm.remove_task(bid)
                        elif time_delta < -1:
                            # 源文件更新更近 -> 用户在源文件恢复/新增了任务 (Ctrl+Z)
                            Logger.info(f"   ➕ 追加 Daily ({bid}): 源文件 Ctrl+Z 恢复 (Source Restore, Δ={int(-time_delta)}s)")
                            if sd['proj'] not in append_to_dn: append_to_dn[sd['proj']] = []
                            append_to_dn[sd['proj']].append(sd)
                            self.sm.update_task(bid, sd['hash'], sd['path'], target_date)
                        else:
                            # 时间极其接近，倾向于删除（因为历史存在说明之前同步过）
                            Logger.info(f"   🗑️ 删除 Source ({bid}): 因 Daily 移除 (时间接近，按历史判定)")
                            if sd['path'] not in src_deletes: src_deletes[sd['path']] = {}
                            src_deletes[sd['path']][bid] = sd['path']
                            self.sm.remove_task(bid)
                    elif has_history and last_date != target_date:
                        # ============================
                        # 情况 2：历史存在但日期不匹配
                        # 可能是跨日期的归档任务，需要谨慎处理
                        # ============================
                        task_dates_str = sd.get('dates', '')
                        linked_dates = re.findall(r'(\d{4}-\d{2}-\d{2})', task_dates_str)
                        is_misjudged = False
                        if linked_dates and target_date not in linked_dates: is_misjudged = True
                        if is_misjudged:
                            Logger.info(f"   🛡️ 拦截追加 ({bid}): 归属 {linked_dates} != 当前 {target_date}")
                            continue
                        Logger.info(f"   ➕ 追加 Daily ({bid}): 来自 {sd['fname']} (跨日期)")
                        if sd['proj'] not in append_to_dn: append_to_dn[sd['proj']] = []
                        append_to_dn[sd['proj']].append(sd)
                        self.sm.update_task(bid, sd['hash'], sd['path'], target_date)
                    else:
                        # ============================
                        # 情况 3：无历史记录 (全新任务)
                        # 无论如何都追加到日记
                        # ============================
                        task_dates_str = sd.get('dates', '')
                        linked_dates = re.findall(r'(\d{4}-\d{2}-\d{2})', task_dates_str)
                        is_misjudged = False
                        if linked_dates and target_date not in linked_dates: is_misjudged = True
                        if is_misjudged:
                            Logger.info(f"   🛡️ 拦截追加 ({bid}): 归属 {linked_dates} != 当前 {target_date}")
                            continue
                        Logger.info(f"   ➕ 追加 Daily ({bid}): 新任务来自 {sd['fname']}")
                        if sd['proj'] not in append_to_dn: append_to_dn[sd['proj']] = []
                        append_to_dn[sd['proj']].append(sd)
                        self.sm.update_task(bid, sd['hash'], sd['path'], target_date)

            # --- 分支：日记里有，但源文件缓存中没找到 (潜在删除风险区) ---
            elif in_d and not in_s:
                dd = dn_tasks[bid]
                raw_first = dd['raw'][0]
                db_data = self.sm.state.get(bid, {})
                
                # 确定该任务"理应"存在的源文件路径
                last_path = db_data.get('source_path', '')
                target_file_direct = extract_routing_target(raw_first, self.file_path_map)
                p_name = dd.get('proj')
                implied_target = self.project_path_map.get(p_name) if p_name else None
                
                # 最终确认校验目标
                potential_source = target_file_direct or implied_target or last_path

                # [CRITICAL RESCUE] 临终磁盘校验逻辑
                # 解决组件通信时差：如果缓存说没了，但在删除前，我们强制去磁盘读一次该任务的"老家"
                if potential_source and os.path.exists(potential_source):
                    # 只有当 potential_source 不是 Daily Note 本身时才重扫
                    if Config.DAILY_NOTE_DIR not in potential_source:
                        # 强迫 TaskRegistry 立即更新这个特定文件的缓存，不等待 Watchdog
                        self._task_registry.update_file(potential_source, self.sm)
                        
                        # 重新尝试从更新后的注册表中获取任务
                        refreshed_src_tasks = self._task_registry.get_tasks_by_date(target_date)
                        if bid in refreshed_src_tasks:
                            Logger.debug(f"    🛡️ [Rescue] 发现任务 {bid} 仍在磁盘，拦截误删并修正缓存")
                            # 既然找到了，我们手动修正本轮循环的状态，将其从"删除"转为"同步"
                            sd = refreshed_src_tasks[bid]
                            # 补偿执行：既然判定为存在，执行原本属于 in_s & in_d 的同步检查
                            last_hash = self.sm.get_task_hash(bid)
                            if sd['hash'] != last_hash:
                                Logger.info(f"    🔄 S->D 补差同步 ({bid}): 来自磁盘校验")
                                # [FIX] 提取当前日记行中的时间，防止被源文件覆盖
                                old_daily_line = dd['raw'][0]
                                time_match = re.search(r'(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)', old_daily_line)
                                preserved_time = time_match.group(1) if time_match else None
                                blk = reconstruct_daily_block(sd, target_date, preserved_time=preserved_time)
                                dn_lines[dd['idx']:dd['idx'] + dd['len']] = blk
                                dn_mod = True
                                self.sm.update_task(bid, sd['hash'], sd['path'], target_date)
                            # 救活后，直接跳过后面的删除判定代码
                            continue 

                # --- 以下为原有的删除/推送逻辑保护 (仅在校验失败后执行) ---
                is_daily_native = (not last_path) or (Config.DAILY_NOTE_DIR in last_path)
                
                is_deleted_from_source = False
                if target_file_direct and last_path:
                    p1 = os.path.normcase(os.path.abspath(target_file_direct))
                    p2 = os.path.normcase(os.path.abspath(last_path))
                    if p1 == p2: is_deleted_from_source = True

                # 增加 Header Context 救命稻草：如果任务在有效的 ## [[项目]] 标题下，也视为有效
                has_valid_header_context = (implied_target and os.path.exists(implied_target))

                # ======================================================
                # [NEW] 基于文件修改时间的仲裁机制 (Last Writer Wins)
                # 解决"幽灵复活"问题：当源文件删除任务后，日记不应强制恢复
                # ======================================================
                
                # 确定用于比对的目标文件路径
                arbitration_target = target_file_direct or implied_target or last_path
                
                # 默认行为：如果有历史记录，倾向于删除；如果是全新任务，倾向于 Push
                should_push = False
                deletion_reason = "确认 Source 已移除"
                
                if not db_data:
                    # 情况 3：新任务 (无历史记录)，默认 Push
                    should_push = True
                    Logger.debug(f"    [ARBITRATE] {bid}: 新任务，无历史记录 -> Push")
                elif bid in organized_bids:
                    # 刚刚被 dispatch_project_tasks 归档的任务，必须 Push
                    should_push = True
                    Logger.debug(f"    [ARBITRATE] {bid}: 刚归档的任务 -> Push")
                elif is_daily_native:
                    # 日记原生任务，不应删除
                    should_push = True
                    Logger.debug(f"    [ARBITRATE] {bid}: 日记原生任务 -> Push")
                elif arbitration_target and os.path.exists(arbitration_target):
                    # 核心仲裁：比较文件修改时间
                    daily_mtime = FileUtils.get_mtime(daily_path)
                    target_mtime = FileUtils.get_mtime(arbitration_target)
                    
                    # 容差判定：时间差 > 1秒才认为有明确先后
                    time_delta = target_mtime - daily_mtime
                    
                    if time_delta > 1:
                        # 情况 1：源文件更新 (Source Deletion)
                        # 用户在源文件中删除了任务，源文件比日记新
                        should_push = False
                        deletion_reason = f"源文件较新且已移除该任务 (Source Deletion, Δ={int(time_delta)}s)"
                        Logger.debug(f"    [ARBITRATE] {bid}: target_mtime({target_mtime:.0f}) > daily_mtime({daily_mtime:.0f}) -> Delete")
                    elif time_delta < -1:
                        # 情况 2：日记更新 (Daily Restore / New)
                        # 用户在日记中恢复或新增了任务 (Ctrl+Z 或粘贴)
                        if has_valid_header_context:
                            should_push = True
                            Logger.debug(f"    [ARBITRATE] {bid}: daily_mtime({daily_mtime:.0f}) > target_mtime({target_mtime:.0f}) + valid_context -> Push/Resurrect")
                        else:
                            # 没有有效上下文，无法确定目标，不推送
                            should_push = False
                            deletion_reason = "日记较新但无有效项目上下文"
                            Logger.debug(f"    [ARBITRATE] {bid}: daily newer but no valid context -> Delete")
                    else:
                        # 时间接近 (|Δ| <= 1s)，倾向于保活
                        if has_valid_header_context:
                            should_push = True
                            Logger.debug(f"    [ARBITRATE] {bid}: 时间接近，有上下文 -> Push (保活)")
                        else:
                            should_push = False
                            deletion_reason = "时间接近且无有效上下文"
                            Logger.debug(f"    [ARBITRATE] {bid}: 时间接近，无上下文 -> Delete")
                elif target_file_direct and os.path.exists(target_file_direct) and not is_deleted_from_source:
                    # 有直接路由且目标存在
                    should_push = True
                else:
                    # 其他情况：无法确定，执行删除
                    should_push = False
                    deletion_reason = "无法确定目标文件"

                if should_push:
                    target_file = None
                    if target_file_direct:
                        target_file = target_file_direct
                    else:
                        target_file = self.project_path_map.get(p_name)
                    if target_file and os.path.exists(target_file):
                        # [FIX] 区分复活请求与晋升：如果任务曾存在于源文件但现在不在了，是复活
                        is_resurrection = has_valid_header_context and not target_file_direct and not (bid in organized_bids)
                        if is_resurrection:
                            Logger.info(f"   🔄 [RESURRECT] 检测到复活请求 ({bid}) -> {os.path.basename(target_file)}")
                        else:
                            Logger.info(f"   🚀 [GRADUATE] 归档任务晋升上行 ({bid}) -> {os.path.basename(target_file)}")
                        fname = os.path.splitext(os.path.basename(target_file))[0]
                        clean = dd['pure']
                        raw_no_quote = re.sub(r'^>\s?', '', raw_first)

                        # [MODIFIED] Use visual depth
                        raw_indent = get_indent_depth(raw_no_quote)

                        n_l = format_line(raw_indent, dd['status'], clean, target_date, fname, bid, False)

                        # [MODIFIED] Pass source_parent_indent using dd['indent']
                        blk = [n_l] + normalize_child_lines(dd['raw'][1:], raw_indent,
                                                                 source_parent_indent=dd['indent'], as_quoted=False)

                        if target_file not in src_updates: src_updates[target_file] = {}
                        src_updates[target_file][bid] = blk
                        self.sm.update_task(bid, dd['hash'], target_file, target_date)
                    else:
                        Logger.info(f"   ⚠️ [ORPHAN] 无法同步，找不到目标文件")
                else:
                    # 执行删除
                    Logger.info(f"   🗑️ 删除 Daily ({bid}): {deletion_reason}")
                    for k in range(dd['idx'], dd['idx'] + dd['len']): dn_lines[k] = None
                    dn_mod = True
                    self.sm.remove_task(bid)  # [NEW] 清理状态记录

        # ======================================================
        # [FIX] 处理 append_to_dn - 将源文件任务追加到日记
        # ======================================================
        if append_to_dn:
            # 找到 Journey 区域中对应项目的 header 位置
            j_idx = -1
            for idx, line in enumerate(dn_lines):
                if line and line.strip() == "# Journey":
                    j_idx = idx
                    break
            
            if j_idx == -1:
                # 如果没有 Journey 区域，在末尾添加
                dn_lines.append("\n# Journey\n")
                j_idx = len(dn_lines) - 1
            
            for proj_name, tasks in append_to_dn.items():
                # 找到该项目的 header
                target_header = f"## [[{proj_name}]]"
                h_idx = -1
                for idx in range(j_idx, len(dn_lines)):
                    if dn_lines[idx] and dn_lines[idx].strip().startswith("## [[") and proj_name in dn_lines[idx]:
                        h_idx = idx
                        break
                
                if h_idx == -1:
                    # 没有找到，创建新的 header
                    insert_pos = len(dn_lines)
                    for idx in range(j_idx + 1, len(dn_lines)):
                        if dn_lines[idx] and dn_lines[idx].startswith("# "):
                            insert_pos = idx
                            break
                    dn_lines.insert(insert_pos, f"\n{target_header}\n\n")
                    h_idx = insert_pos
                
                # 在 header 后面插入任务
                insert_pos = h_idx + 1
                for idx in range(h_idx + 1, len(dn_lines)):
                    if dn_lines[idx] and (dn_lines[idx].startswith("#") or dn_lines[idx].strip().startswith("## [[")):
                        insert_pos = idx
                        break
                    insert_pos = idx + 1
                
                for sd in tasks:
                    blk = reconstruct_daily_block(sd, target_date)
                    for line in reversed(blk):
                        dn_lines.insert(insert_pos, line)
                    dn_mod = True

        if dn_mod:
            # [CRITICAL FIX] 写入日记文件前的幂等性检查
            final_dn_lines = [l for l in dn_lines if l is not None]
            original_dn_content = FileUtils.read_content(daily_path) or ""
            new_dn_content = "".join(final_dn_lines)

            if original_dn_content != new_dn_content:
                FileUtils.write_file(daily_path, final_dn_lines)
                Logger.info(f"   ✅ 日记文件已回写: {os.path.basename(daily_path)}")

        if src_deletes:
            for path, bids in src_deletes.items():
                sl = FileUtils.read_file(path)
                if not sl: continue
                out, i, chg = [], 0, False
                deleted_bids = list(bids.keys())
                while i < len(sl):
                    im = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', sl[i])
                    if not im: im = re.search(r'\(connect::.*?\^([a-zA-Z0-9]{6,})\)', sl[i])
                    if im and im.group(1) in deleted_bids:
                        _, c = capture_block(sl, i);
                        i += c;
                        chg = True
                    else:
                        out.append(sl[i]);
                        i += 1
                if chg:
                    stem = os.path.splitext(os.path.basename(path))[0]
                    out = inject_into_task_section(out, [], stem)

                    # [FIX] 显式比对
                    orig_content = "".join(sl)
                    new_content = "".join(out)
                    if orig_content != new_content:
                        Logger.info(f"   💾 [WRITE] 写入源文件 (Delete) (from {target_date}): {os.path.basename(path)}")
                        if FileUtils.write_file(path, out):
                            # [关键修复]：写入成功后，立即强制更新注册表缓存
                            self._task_registry.update_file(path, self.sm)

        if src_updates:
            for path, ups in src_updates.items():
                sl = FileUtils.read_file(path)
                if not sl: sl = []
                out, i, chg = [], 0, False
                handled_bids = set()
                while i < len(sl):
                    im = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', sl[i])
                    if not im: im = re.search(r'\(connect::.*?\^([a-zA-Z0-9]{6,})\)', sl[i])
                    if im and im.group(1) in ups:
                        bid = im.group(1)
                        _, c = capture_block(sl, i)
                        out.extend(ups[bid])
                        handled_bids.add(bid)
                        i += c;
                        chg = True
                    else:
                        out.append(sl[i]);
                        i += 1
                pending_inserts = []
                for bid, blk in ups.items():
                    if bid not in handled_bids: pending_inserts.extend(blk); chg = True

                if chg:
                    stem = os.path.splitext(os.path.basename(path))[0]
                    out = inject_into_task_section(out, pending_inserts, stem)

                    # [FIX] 显式比对，防止死循环
                    orig_content = "".join(sl)
                    new_content = "".join(out)

                    if orig_content != new_content:
                        Logger.info(
                            f"   💾 [WRITE] 写入源文件 (Update/Insert) (from {target_date}): {os.path.basename(path)}")
                        if FileUtils.write_file(path, out):
                            # [关键修复]：写入成功后，立即强制更新注册表缓存
                            # 不等 Watchdog，现在就更新"大脑"，消除"执行"与"感知"之间的时差
                            self._task_registry.update_file(path, self.sm)
                        self.trigger_delayed_verification(path)

        self.sm.save()
