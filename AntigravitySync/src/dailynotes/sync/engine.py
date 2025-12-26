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
from .ingestion import scan_all_source_tasks
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

    def trigger_delayed_verification(self, filepath, delay=10):
        def _job():
            time.sleep(delay)
            content = FileUtils.read_file(filepath) or []
            Logger.debug_block(f"VERIFICATION (T+{delay}s) Snapshot: {os.path.basename(filepath)}", content)

        t = threading.Thread(target=_job, daemon=True)
        t.start()

    def generate_block_id(self):
        return '^' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    def scan_projects(self):
        # Delegate to discovery module
        self.project_map, self.project_path_map, self.file_path_map = scan_projects()

    def scan_all_source_tasks(self) -> Dict[str, Dict]:
        # Delegate to ingestion module
        self.scan_projects()
        return scan_all_source_tasks(self.project_map, self.sm)
        
    def calculate_nearest_project(self, routing_path):
        """
        Traverses up from the routing path to find the nearest ancestor project.
        """
        if not routing_path: return None
        search_start = os.path.dirname(routing_path)
        
        # Traverse upwards
        curr_search = search_start
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
                    
                    should_move = False
                    
                    if not target_p_name:
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
                        bid_m = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', raw_first)
                        bid = bid_m.group(1) if bid_m else self.generate_block_id().replace('^', '')
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
                            time_part = tm.group(1) + " "

                        if has_existing_link:
                            # === STRATEGY A: Link Preservation with proper formatting ===
                            # Keep existing links but inject return link and ID
                            
                            # Clean the text but preserve existing links
                            # Remove: status, indent, time (will re-add), ID (will re-add)
                            clean_pure = re.sub(r'^[\s>]*-\s*\[.\]\s?', '', raw_first)
                            clean_pure = re.sub(r'^\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?\s*', '', clean_pure)
                            clean_pure = re.sub(r'\^[a-zA-Z0-9]{6,}\s*$', '', clean_pure)
                            clean_pure = re.sub(r'\s+', ' ', clean_pure).strip()
                            
                            # Build return link
                            ret_link = f"[[{target_p_name}#^{bid}|⮐]]"
                            
                            # Format final line: time + return link + preserved content + ID
                            final_head_line = f"{indent_str}- [{status}] {time_part}{ret_link} {clean_pure} ^{bid}\n"
                            
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

                            ret_link = f"[[{target_p_name}#^{bid}|⮐]]"

                            target_tag = f"[[{target_p_name}]]"
                            if target_tag in clean_pure:
                                file_tag = "" 
                            else:
                                file_tag = f" {target_tag}"
                            
                            clean_pure = re.sub(r'\s+', ' ', clean_pure).strip()
                            final_head_line = f"{indent_str}- [{status}] {time_part}{ret_link}{file_tag} {clean_pure} ^{bid}\n"

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
        Logger.info(f"   💾 [WRITE] 更新归档文件 (Orphans): {os.path.basename(filepath)}")
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
            in_s = bid in src_tasks;
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
                        blk = reconstruct_daily_block(sd, target_date)
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
                            Logger.info(f"   ⚔️ 冲突 ({bid}): Daily 覆盖 Source")
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
                    if last_date == target_date:
                        Logger.info(f"   🗑️ 删除 Source ({bid}): 因 Daily 移除")
                        if sd['path'] not in src_deletes: src_deletes[sd['path']] = {}
                        src_deletes[sd['path']][bid] = sd['path']
                        self.sm.remove_task(bid)
                    else:
                        task_dates_str = sd.get('dates', '')
                        linked_dates = re.findall(r'(\d{4}-\d{2}-\d{2})', task_dates_str)
                        is_misjudged = False
                        if linked_dates and target_date not in linked_dates: is_misjudged = True
                        if is_misjudged:
                            Logger.info(f"   🛡️ 拦截追加 ({bid}): 归属 {linked_dates} != 当前 {target_date}")
                            continue
                        Logger.info(f"   ➕ 追加 Daily ({bid}): 来自 {sd['fname']}")
                        if sd['proj'] not in append_to_dn: append_to_dn[sd['proj']] = []
                        append_to_dn[sd['proj']].append(sd)
                        self.sm.update_task(bid, sd['hash'], sd['path'], target_date)

            elif in_d and not in_s:
                dd = dn_tasks[bid];
                raw_first = dd['raw'][0]
                db_data = self.sm.state.get(bid, {})
                last_path = db_data.get('source_path', '')
                is_daily_native = (not last_path) or (Config.DAILY_NOTE_DIR in last_path)
                target_file_direct = extract_routing_target(raw_first, self.file_path_map)
                is_deleted_from_source = False
                if target_file_direct and last_path:
                    p1 = os.path.normcase(os.path.abspath(target_file_direct))
                    p2 = os.path.normcase(os.path.abspath(last_path))
                    if p1 == p2: is_deleted_from_source = True
                should_push = (bid in organized_bids) or is_daily_native or (
                        target_file_direct and os.path.exists(target_file_direct) and not is_deleted_from_source)
                if should_push:
                    target_file = None
                    if target_file_direct:
                        target_file = target_file_direct
                    else:
                        p_name = dd.get('proj')
                        target_file = self.project_path_map.get(p_name)
                    if target_file and os.path.exists(target_file):
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
                    Logger.info(f"   🗑️ 删除 Daily ({bid}): 因 Source 移除")
                    for k in range(dd['idx'], dd['idx'] + dd['len']): dn_lines[k] = None
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
                        # === 🎯 第二次日志修改 (Delete) ===
                        Logger.info(f"   💾 [WRITE] 写入源文件 (Delete) (from {target_date}): {os.path.basename(path)}")
                        FileUtils.write_file(path, out)

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
                        # === 🎯 第三次日志修改 (Update/Insert) - 你的主要需求 ===
                        Logger.info(
                            f"   💾 [WRITE] 写入源文件 (Update/Insert) (from {target_date}): {os.path.basename(path)}")
                        FileUtils.write_file(path, out)
                        self.trigger_delayed_verification(path)

        self.sm.save()
