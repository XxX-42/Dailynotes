"""
Bidirectional Sync Engine - Adapted for unified config.
Core synchronization logic between Obsidian and Apple Calendar.
"""
import os
from datetime import datetime, timedelta
from config import Config
from .utils import calculate_duration_minutes
from dailynotes.utils import FileUtils
from .calendar_service import get_all_calendars_state, BatchExecutor
from .obsidian_service import get_obsidian_state

# Use config values
CAL_TO_TAG = Config.CAL_TO_TAG


def perform_bidirectional_sync(date_str, obs_path, state_manager, target_dt):
    """
    Perform bidirectional sync between Obsidian and Apple Calendar.
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        obs_path: Path to the Obsidian daily note
        state_manager: AppleStateManager instance
        target_dt: datetime object for target date
    """
    # 1. Optimistic lock baseline
    initial_mtime = 0
    if os.path.exists(obs_path):
        initial_mtime = os.path.getmtime(obs_path)

    current_obs, file_lines, _, insert_idx = get_obsidian_state(obs_path)
    current_cal = get_all_calendars_state(target_dt)
    last_obs, last_cal = state_manager.get_snapshot(date_str)

    # [v2.0.1] 构建 semantic_key -> [calendar_keys] 的映射
    # 用于处理 Obsidian (Name+Time) 与 Calendar (Name+Time+ID) 的模糊匹配
    cal_semantic_map = {}  # {semantic_key: [cal_key1, cal_key2, ...]}
    cal_id_map = {}        # {event_id: cal_key}
    for c_key, c_data in current_cal.items():
        sem_key = c_data.get('semantic_key', c_key)  # 兼容旧格式
        if sem_key not in cal_semantic_map:
            cal_semantic_map[sem_key] = []
        cal_semantic_map[sem_key].append(c_key)
        cal_id_map[c_data['id']] = c_key

    # Batch executor
    batch = BatchExecutor(target_dt)

    file_dirty = False
    lines_to_modify = {}
    lines_to_delete_indices = []
    lines_to_append = []

    handled_obs_keys = set()
    handled_cal_keys = set()

    # Phase 0: Drift Detection
    # [v2.0.1] 使用 semantic_key 进行匹配，因为 Obsidian key 不包含 ID
    obs_name_map = {}
    for key, val in current_obs.items():
        if val['name'] not in obs_name_map:
            obs_name_map[val['name']] = []
        obs_name_map[val['name']].append(key)

    for c_key, c_data in current_cal.items():
        sem_key = c_data.get('semantic_key', c_key)
        # [v2.0.1] 检查 semantic_key 是否在 Obsidian 中，而不是 c_key
        if sem_key not in current_obs and c_key not in last_cal:
            possible_obs_keys = obs_name_map.get(c_data['name'], [])
            for old_o_key in possible_obs_keys:
                # [v2.0.1] 检查 old_o_key 是否映射到任何当前日历事件
                if old_o_key not in cal_semantic_map:
                    print(f"🕵️ [Drift] 时间修改: {c_data['name']} ({current_obs[old_o_key]['start_time']} -> {c_data['start_time']})")
                    line_idx = current_obs[old_o_key]['line_index']
                    tag_suffix = CAL_TO_TAG.get(c_data['current_calendar'], "")
                    if tag_suffix == "#D":
                        tag_suffix = ""
                    end_time_str = ""
                    if c_data['duration'] != 30:
                        end_t = datetime.strptime(c_data['start_time'], "%H:%M") + timedelta(minutes=c_data['duration'])
                        end_time_str = f" - {end_t.strftime('%H:%M')}"
                    tag_part = f"{tag_suffix} " if tag_suffix else ""
                    # [外科手术级回写] 保留所有原始隐藏格式（ID、双链），仅替换时间块
                    orig_line = file_lines[line_idx]
                    new_line = re.sub(r'\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?', f"{c_data['start_time']}{end_time_str}", orig_line, count=1)
                    
                    lines_to_modify[line_idx] = new_line
                    file_dirty = True
                    
                    # [NEW FIX] 必须同步更新内存中的 `current_obs` 字典，以确保后续快照被正确刷新
                    new_obs_key = f"{c_data['name']}_{c_data['start_time']}"
                    new_o_data = current_obs[old_o_key].copy()
                    new_o_data['start_time'] = c_data['start_time']
                    del current_obs[old_o_key]
                    current_obs[new_obs_key] = new_o_data
                    
                    handled_obs_keys.add(old_o_key)
                    handled_obs_keys.add(new_obs_key)
                    handled_cal_keys.add(c_key)
                    break

    # Phase 0.5: Rename Detection
    for c_key, c_data in current_cal.items():
        if c_key in handled_cal_keys:
            continue
        if c_key not in last_cal:
            found_old_key = None
            for old_k, old_v in last_cal.items():
                if old_v['id'] == c_data['id']:
                    found_old_key = old_k
                    break
            if found_old_key:
                print(f"🕵️ [Move/Rename C->O] 捕捉变动: {last_cal[found_old_key]['name']}@{last_cal[found_old_key]['start_time']} -> {c_data['name']}@{c_data['start_time']}")
                rename_success = False
                
                # [NEW FIX] found_old_key 是带 ID 尾巴的日历格式键，不能直接去查无 ID 的 current_obs，必须转为对应的语义键
                old_sem_key = last_cal[found_old_key].get('semantic_key', found_old_key)
                
                if old_sem_key in current_obs:
                    line_idx = current_obs[old_sem_key]['line_index']
                    tag_suffix = CAL_TO_TAG.get(c_data['current_calendar'], "")
                    if tag_suffix == "#D":
                        tag_suffix = ""
                    tag_part = f"{tag_suffix} " if tag_suffix else ""
                    
                    # Calculate new end time based on duration
                    end_time_str = ""
                    if c_data['duration'] != 30:
                        end_t = datetime.strptime(c_data['start_time'], "%H:%M") + timedelta(minutes=c_data['duration'])
                        end_time_str = f" - {end_t.strftime('%H:%M')}"
                    
                    
                    # [外科手术级回写] 替换时间和名字，保护外层嵌套结构
                    orig_line = file_lines[line_idx]
                    old_display_name = current_obs[old_sem_key]['name']
                    
                    new_line = re.sub(r'\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?', f"{c_data['start_time']}{end_time_str}", orig_line, count=1)
                    if old_display_name in new_line:
                        new_line = new_line.replace(old_display_name, c_data['name'])
                        
                    lines_to_modify[line_idx] = new_line
                    file_dirty = True
                    
                    # [v1.7.2/v1.7.4] Critical State Update (Name AND Time):
                    new_obs_key = f"{c_data['name']}_{c_data['start_time']}"
                    new_o_data = current_obs[old_sem_key].copy()
                    new_o_data['name'] = c_data['name']
                    new_o_data['start_time'] = c_data['start_time']
                    new_o_data['end_time'] = end_t.strftime('%H:%M') if c_data['duration'] != 30 else None
                    
                    del current_obs[old_sem_key]
                    current_obs[new_obs_key] = new_o_data
                    
                    handled_obs_keys.add(old_sem_key)
                    handled_obs_keys.add(new_obs_key)
                    rename_success = True
                # [v1.7.1] Fix: Always mark as handled if rename detected to prevent duplicate append
                handled_cal_keys.add(c_key)
                if not rename_success:
                    print(f"⚠️ [Rename] Obsidian 中未找到旧任务 {found_old_key}，跳过本地重命名，但阻止重复写入")

    last_obs_time_map = {}
    last_obs_name_map = {}
    for k, v in last_obs.items():
        # Map by time
        if v['start_time'] not in last_obs_time_map:
            last_obs_time_map[v['start_time']] = []
        last_obs_time_map[v['start_time']].append(k)
        # Map by name
        if v['name'] not in last_obs_name_map:
            last_obs_name_map[v['name']] = []
        last_obs_name_map[v['name']].append(k)

    for o_key, o_data in current_obs.items():
        if o_key in handled_obs_keys:
            continue
        if o_key not in last_obs:
            # [Detection] Rename? (Same time, different name)
            candidates_time = last_obs_time_map.get(o_data['start_time'], [])
            found_move = False
            for old_key in candidates_time:
                if old_key not in current_obs and old_key in current_cal:
                    c_data = current_cal[old_key]
                    print(f"🕵️ [Rename O->C] 笔记改名: {last_obs[old_key]['name']} -> {o_data['name']}")
                    o_is_completed = (o_data['status'] == 'x')
                    dur = calculate_duration_minutes(o_data['start_time'], o_data['end_time'])
                    
                    if o_data['target_calendar'] != c_data['current_calendar']:
                        batch.add_delete(c_data['id'], c_data['current_calendar'])
                        batch.add_create(o_data['name'], o_data['start_time'], dur, o_data['target_calendar'], o_is_completed)
                    else:
                        batch.add_update(c_data['id'], c_data['current_calendar'], o_data['name'], o_data['start_time'],
                                         dur, o_is_completed)
                    
                    handled_obs_keys.add(o_key)
                    handled_obs_keys.add(old_key)
                    handled_cal_keys.add(old_key)
                    found_move = True
                    break
            
            if not found_move:
                # [Detection] Move? (Same name, different time)
                candidates_name = last_obs_name_map.get(o_data['name'], [])
                for old_key in candidates_name:
                    if old_key not in current_obs and old_key in current_cal:
                        c_data = current_cal[old_key]
                        print(f"🕵️ [Move O->C] 笔记移动: {last_obs[old_key]['start_time']} -> {o_data['start_time']} ({o_data['name']})")
                        o_is_completed = (o_data['status'] == 'x')
                        dur = calculate_duration_minutes(o_data['start_time'], o_data['end_time'])
                        
                        if o_data['target_calendar'] != c_data['current_calendar']:
                            batch.add_delete(c_data['id'], c_data['current_calendar'])
                            batch.add_create(o_data['name'], o_data['start_time'], dur, o_data['target_calendar'], o_is_completed)
                        else:
                            batch.add_update(c_data['id'], c_data['current_calendar'], o_data['name'], o_data['start_time'],
                                             dur, o_is_completed)
                        
                        handled_obs_keys.add(o_key)
                        handled_obs_keys.add(old_key)
                        handled_cal_keys.add(old_key)
                        found_move = True
                        break

    # Phase A: O -> C
    for key, o_data in current_obs.items():
        if key in handled_obs_keys:
            continue
        is_new = key not in last_obs
        is_modified = False
        if not is_new:
            last_data = last_obs[key]
            o_dur = calculate_duration_minutes(o_data['start_time'], o_data['end_time'])
            l_dur = calculate_duration_minutes(last_data['start_time'], last_data['end_time'])
            if (o_data['target_calendar'] != last_data['target_calendar'] or
                    abs(o_dur - l_dur) > 2 or
                    o_data['status'] != last_data.get('status', ' ')):
                
                print(f"🐛 [Debug] is_modified=True for {key}:")
                print(f"    Cal: {o_data['target_calendar']} vs {last_data['target_calendar']}")
                print(f"    Dur: {o_dur} vs {l_dur}")
                print(f"    Sts: '{o_data['status']}' vs '{last_data.get('status', ' ')}'")
                is_modified = True

        if is_new or is_modified:
            o_is_completed = (o_data['status'] == 'x')
            dur = calculate_duration_minutes(o_data['start_time'], o_data['end_time'])
            # [v2.0.1] 使用 semantic_map 查找日历事件
            cal_keys = cal_semantic_map.get(key, [])
            if cal_keys:
                # 有匹配的日历事件，取第一个进行更新
                c_key = cal_keys[0]
                c_data = current_cal[c_key]
                if is_modified:
                    if o_data['target_calendar'] != c_data['current_calendar']:
                        # Cross-calendar: delete old + create new
                        batch.add_delete(c_data['id'], c_data['current_calendar'])
                        batch.add_create(o_data['name'], o_data['start_time'], dur, o_data['target_calendar'],
                                         o_is_completed)
                    else:
                        # In-place update
                        batch.add_update(c_data['id'], c_data['current_calendar'], o_data['name'], o_data['start_time'],
                                         dur, o_is_completed)
            else:
                # Create new
                batch.add_create(o_data['name'], o_data['start_time'], dur, o_data['target_calendar'], o_is_completed)

    # [v2.0.1] 删除检测：使用 semantic_map
    for key in last_obs:
        if key not in current_obs and key not in handled_obs_keys:
            cal_keys = cal_semantic_map.get(key, [])
            if cal_keys:
                c_key = cal_keys[0]
                c_data = current_cal[c_key]
                print(f"🗑️ [O->C] 触发日历删除: {key}")
                batch.add_delete(c_data['id'], c_data['current_calendar'])
                handled_cal_keys.add(c_key)

    # Phase B: C -> O
    for c_key, c_data in current_cal.items():
        if c_key in handled_cal_keys:
            continue
        sem_key = c_data.get('semantic_key', c_key)
        # [v2.0.1] 使用 semantic_key 判断是否已存在于 Obsidian
        if c_key not in last_cal and sem_key not in current_obs:
            print(f"📝 [C->O] 写入笔记: {c_data['name']}")
            tag_suffix = CAL_TO_TAG.get(c_data['current_calendar'], "")
            if tag_suffix == "#D":
                tag_suffix = ""
            end_time_str = ""
            if c_data['duration'] != 30:
                end_t = datetime.strptime(c_data['start_time'], "%H:%M") + timedelta(minutes=c_data['duration'])
                end_time_str = f" - {end_t.strftime('%H:%M')}"
            tag_part = f"{tag_suffix} " if tag_suffix else ""
            status_char = 'x' if c_data['is_completed'] else ' '
            new_line = f"- [{status_char}] {c_data['start_time']}{end_time_str} {tag_part}{c_data['name']}\n"
            lines_to_append.append(new_line)
            file_dirty = True
            
            # [v2.0.1] Snapshot Consistency: 使用 semantic_key 作为 Obsidian 端的 key
            current_obs[sem_key] = {
                'name': c_data['name'],
                'start_time': c_data['start_time'],
                'end_time': end_t.strftime('%H:%M') if c_data['duration'] != 30 else None,
                'target_calendar': c_data['current_calendar'],
                'tag': tag_suffix,
                'span_tag': None,
                'status': status_char,
                'line_index': -1 # Placeholder, won't be used next run (re-parsed)
            }

        elif c_key in last_cal and sem_key in current_obs:
            last_c_data = last_cal[c_key]
            is_cal_modified = False
            if c_data['current_calendar'] != last_c_data['current_calendar']:
                is_cal_modified = True
            if abs(c_data['duration'] - last_c_data.get('duration', 30)) > 2:
                is_cal_modified = True
            if c_data['is_completed'] != last_c_data.get('is_completed', False):
                is_cal_modified = True

            if is_cal_modified:
                print(f"🔄 [C->O] 日历属性变更: {c_data['name']}")
                line_idx = current_obs[sem_key]['line_index']
                tag_suffix = CAL_TO_TAG.get(c_data['current_calendar'], "")
                if tag_suffix == "#D":
                    tag_suffix = ""
                end_time_str = ""
                if c_data['duration'] != 30:
                    end_t = datetime.strptime(c_data['start_time'], "%H:%M") + timedelta(minutes=c_data['duration'])
                    end_time_str = f" - {end_t.strftime('%H:%M')}"
                status_char = 'x' if c_data['is_completed'] else ' '
                orig_line = file_lines[line_idx]
                
                # [外科手术级回写] 状态和时间的精准替换
                new_line = re.sub(r'\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?', f"{c_data['start_time']}{end_time_str}", orig_line, count=1)
                new_line = re.sub(r'- \[[ xX]\]', f"- [{status_char}]", new_line, count=1)
                
                # 安全更新标签（如果不一致）
                old_tag = current_obs[sem_key].get('tag', '')
                if old_tag and tag_suffix and old_tag != tag_suffix:
                    new_line = new_line.replace(old_tag, tag_suffix)
                elif old_tag and not tag_suffix:
                    new_line = new_line.replace(f" {old_tag}", "").replace(old_tag, "")
                    
                lines_to_modify[line_idx] = new_line
                file_dirty = True
                
                # [v2.0.1] Snapshot Consistency: Update current_obs
                current_obs[sem_key]['target_calendar'] = c_data['current_calendar']
                current_obs[sem_key]['tag'] = tag_suffix
                current_obs[sem_key]['status'] = status_char
                current_obs[sem_key]['end_time'] = end_t.strftime('%H:%M') if c_data['duration'] != 30 else None

    # [v2.0.1] 日历端删除检测：last_cal 的 key 格式可能是新的带 ID 格式
    for old_c_key in last_cal:
        # 检查是否仍存在于当前日历
        old_c_data = last_cal[old_c_key]
        old_id = old_c_data.get('id', '')
        still_exists = old_id in cal_id_map
        
        if not still_exists and old_c_key not in handled_obs_keys:
            # 从 last_cal 获取 semantic_key
            old_sem_key = old_c_data.get('semantic_key', old_c_key)
            if old_sem_key in current_obs:
                line_idx = current_obs[old_sem_key]['line_index']
                print(f"✂️ [C->O] 检测到日历端删除 (同步删除本地): {current_obs[old_sem_key]['name']}")
                lines_to_delete_indices.append(line_idx)
                file_dirty = True
                
                # [v2.0.1] Snapshot Consistency: Remove from current_obs
                del current_obs[old_sem_key]

    # 4. Execute AppleScript batch
    batch.execute()

    # [v1.7.3] State Stabilization:
    # If any creations occurred, re-fetch calendar state immediately to capture IDs.
    # This prevents duplication if a renamed/modified version appears in the next run.
    if len(batch.creates) > 0:
        current_cal = get_all_calendars_state(target_dt)

    # Phase C: Atomic Write
    if file_dirty or len(lines_to_append) > 0 or len(lines_to_delete_indices) > 0:
        if os.path.exists(obs_path):
            current_mtime_now = os.path.getmtime(obs_path)
            if current_mtime_now != initial_mtime:
                print(f"⚠️ [Concurrency] 放弃写入 {date_str}：文件在计算期间已被修改")
                return False, False

            if insert_idx == len(file_lines):
                # [v4.0] 不再插入旧的 # Day planner 标题
                # 新架构使用 # Deployment > ## Archive/Single
                pass

            for idx, new_content in lines_to_modify.items():
                if 0 <= idx < len(file_lines):
                    file_lines[idx] = new_content

            unique_delete_indices = sorted(list(set(lines_to_delete_indices)), reverse=True)
            for idx in unique_delete_indices:
                if 0 <= idx < len(file_lines):
                    del file_lines[idx]
                    if idx < insert_idx:
                        insert_idx -= 1

            if insert_idx > len(file_lines):
                insert_idx = len(file_lines)
            for line in lines_to_append:
                file_lines.insert(insert_idx, line)
                insert_idx += 1

            # [v1.7] Atomic Write with Hash Registration
            # Use FileUtils to write file and register its hash so manager.py ignores this event
            try:
                if FileUtils.write_file(obs_path, file_lines):
                    print(f"💾 Obsidian 文件已更新 (C->O): {date_str}")
                else:
                    print(f"⚠️ Obsidian 文件写入被跳过 (无变动?): {date_str}")
            except Exception as e:
                print(f"❌ 文件写入失败: {e}")
                return False, False

    state_manager.update_snapshot(date_str, current_obs, current_cal)
    
    apple_ops_count = len(batch.creates) + len(batch.updates) + len(batch.deletes)
    return file_dirty, apple_ops_count > 0
