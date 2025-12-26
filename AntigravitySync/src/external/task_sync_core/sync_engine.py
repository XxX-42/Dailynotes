"""
Bidirectional Sync Engine - Adapted for unified config.
Core synchronization logic between Obsidian and Apple Calendar.
"""
import os
from datetime import datetime, timedelta
from config import Config
from .utils import calculate_duration_minutes
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

    # Batch executor
    batch = BatchExecutor(target_dt)

    file_dirty = False
    lines_to_modify = {}
    lines_to_delete_indices = []
    lines_to_append = []

    handled_obs_keys = set()
    handled_cal_keys = set()

    # Phase 0: Drift Detection
    obs_name_map = {}
    for key, val in current_obs.items():
        if val['name'] not in obs_name_map:
            obs_name_map[val['name']] = []
        obs_name_map[val['name']].append(key)

    for c_key, c_data in current_cal.items():
        if c_key not in current_obs and c_key not in last_cal:
            possible_obs_keys = obs_name_map.get(c_data['name'], [])
            for old_o_key in possible_obs_keys:
                if old_o_key not in current_cal:
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
                    status_char = current_obs[old_o_key]['status']
                    new_line = f"- [{status_char}] {c_data['start_time']}{end_time_str} {tag_part}{c_data['name']}\n"
                    lines_to_modify[line_idx] = new_line
                    file_dirty = True
                    handled_obs_keys.add(old_o_key)
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
                print(f"🕵️ [Rename C->O] 日历改名: {last_cal[found_old_key]['name']} -> {c_data['name']}")
                if found_old_key in current_obs:
                    line_idx = current_obs[found_old_key]['line_index']
                    old_o_data = current_obs[found_old_key]
                    tag_suffix = CAL_TO_TAG.get(c_data['current_calendar'], "")
                    if tag_suffix == "#D":
                        tag_suffix = ""
                    tag_part = f"{tag_suffix} " if tag_suffix else ""
                    end_time_str = ""
                    if old_o_data['end_time']:
                        end_time_str = f" - {old_o_data['end_time']}"
                    status_char = old_o_data['status']
                    new_line = f"- [{status_char}] {old_o_data['start_time']}{end_time_str} {tag_part}{c_data['name']}\n"
                    lines_to_modify[line_idx] = new_line
                    file_dirty = True
                    handled_obs_keys.add(found_old_key)
                    handled_cal_keys.add(c_key)

    last_obs_time_map = {}
    for k, v in last_obs.items():
        if v['start_time'] not in last_obs_time_map:
            last_obs_time_map[v['start_time']] = []
        last_obs_time_map[v['start_time']].append(k)

    for o_key, o_data in current_obs.items():
        if o_key in handled_obs_keys:
            continue
        if o_key not in last_obs:
            candidates = last_obs_time_map.get(o_data['start_time'], [])
            for old_key in candidates:
                if old_key not in current_obs:
                    if old_key in current_cal:
                        c_data = current_cal[old_key]
                        print(f"🕵️ [Rename O->C] 笔记改名: {last_obs[old_key]['name']} -> {o_data['name']}")
                        o_is_completed = (o_data['status'] == 'x')
                        batch.add_update(c_data['id'], c_data['current_calendar'], o_data['name'], o_data['start_time'],
                                         c_data['duration'], o_is_completed)
                        handled_obs_keys.add(o_key)      # Current key (prevent duplicate create)
                        handled_obs_keys.add(old_key)    # Old key (prevent delete)
                        handled_cal_keys.add(old_key)
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
                is_modified = True

        if is_new or is_modified:
            o_is_completed = (o_data['status'] == 'x')
            dur = calculate_duration_minutes(o_data['start_time'], o_data['end_time'])
            if key in current_cal:
                c_data = current_cal[key]
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

    for key in last_obs:
        if key not in current_obs and key not in handled_obs_keys:
            if key in current_cal:
                c_data = current_cal[key]
                batch.add_delete(c_data['id'], c_data['current_calendar'])

    # Phase B: C -> O
    for key, c_data in current_cal.items():
        if key in handled_cal_keys:
            continue
        if key not in last_cal and key not in current_obs:
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
        elif key in last_cal and key in current_obs:
            last_c_data = last_cal[key]
            is_cal_modified = False
            if c_data['current_calendar'] != last_c_data['current_calendar']:
                is_cal_modified = True
            if abs(c_data['duration'] - last_c_data.get('duration', 30)) > 2:
                is_cal_modified = True
            if c_data['is_completed'] != last_c_data.get('is_completed', False):
                is_cal_modified = True

            if is_cal_modified:
                print(f"🔄 [C->O] 日历属性变更: {c_data['name']}")
                line_idx = current_obs[key]['line_index']
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
                lines_to_modify[line_idx] = new_line
                file_dirty = True

    for key in last_cal:
        if key not in current_cal and key not in handled_obs_keys:
            if key in current_obs:
                line_idx = current_obs[key]['line_index']
                print(f"✂️ [C->O] 日历删除: {current_obs[key]['name']}")
                lines_to_delete_indices.append(line_idx)
                file_dirty = True

    # 4. Execute AppleScript batch
    batch.execute()

    # Phase C: Atomic Write
    if file_dirty or len(lines_to_append) > 0 or len(lines_to_delete_indices) > 0:
        if os.path.exists(obs_path):
            current_mtime_now = os.path.getmtime(obs_path)
            if current_mtime_now != initial_mtime:
                print(f"⚠️ [Concurrency] 放弃写入 {date_str}：文件在计算期间已被修改")
                return

            if insert_idx == len(file_lines):
                has_header = False
                for line in file_lines:
                    if "#dayplanner" in line.lower().replace(" ", ""):
                        has_header = True
                        break
                if not has_header:
                    if file_lines and not file_lines[-1].endswith("\n"):
                        file_lines[-1] += "\n"
                    file_lines.append("\n# Day planner\n")
                    insert_idx = len(file_lines)

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

            temp_path = obs_path + ".tmp"
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.writelines(file_lines)
                os.replace(temp_path, obs_path)
                print(f"💾 Obsidian 文件已更新: {date_str}")
            except Exception as e:
                print(f"❌ 文件写入失败: {e}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return

    state_manager.update_snapshot(date_str, current_obs, current_cal)
    
    apple_ops_count = len(batch.creates) + len(batch.updates) + len(batch.deletes)
    return file_dirty, apple_ops_count > 0
