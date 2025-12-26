# Project Architecture: AntigravitySync

## Directory Tree
```text
AntigravitySync/
├── aggregate.py
├── config.py
├── main.py
└── src
    ├── dailynotes
    │   ├── __init__.py
    │   ├── format_core.py
    │   ├── manager.py
    │   ├── state_manager.py
    │   ├── sync
    │   │   ├── __init__.py
    │   │   ├── discovery.py
    │   │   ├── engine.py
    │   │   ├── engine.py.baiduyun.uploading.cfg
    │   │   ├── ingestion.py
    │   │   ├── parsing.py
    │   │   └── rendering.py
    │   └── utils.py
    └── external
        ├── __init__.py
        ├── apple_sync_adapter.py
        └── task_sync_core
            ├── __init__.py
            ├── apple_state_manager.py
            ├── calendar_service.py
            ├── obsidian_service.py
            ├── sync_engine.py
            └── utils.py
```

---

## File: config.py
```py
import os


class Config:
    # ==========================
    # 1. 基础路径配置 (来自 Dailynotes)
    # ==========================
    VAULT_ROOT = r'/Users/user999/Documents/【Liang_project】/远程仓库1'
    REL_ATTACHMENT_DIR = r'【ATTACHMENT】'
    REL_TEMPLATE_FILE = r'DayPlanTemplate.md'

    # 自动拼接
    DAILY_NOTE_DIR = os.path.join(VAULT_ROOT, REL_ATTACHMENT_DIR, r'【DAILYNOTE】')
    TEMPLATE_FILE = os.path.join(VAULT_ROOT, REL_TEMPLATE_FILE)

    # 排除项
    EXCLUDE_DIRS = [
        os.path.join(VAULT_ROOT, REL_ATTACHMENT_DIR),
        os.path.join(VAULT_ROOT, r'.trash'),
    ]
    SYNC_IGNORE_DIRS = [
        os.path.join(VAULT_ROOT, r'「」InfoBox/「InfoManage」Updating OBlifeos/【Templates】')
    ]
    FORCED_AGGREGATION_DIRS = SYNC_IGNORE_DIRS

    # 兼容性别名
    ROOT_DIR = VAULT_ROOT
    STATE_FILE = os.path.join(DAILY_NOTE_DIR, ".sync_state.json")
    LOCK_FILE = os.path.join(DAILY_NOTE_DIR, ".fusion_sync_lock")

    # 运行参数
    SYNC_START_DATE = "2025-12-08"
    TICK_INTERVAL = 2
    TYPING_COOLDOWN_SECONDS = 6
    IMAGE_PARAM_SUFFIX = "|L|200"
    DEBUG_MODE = True
    
    # [NEW] Tick-based scheduling parameters
    DAY_START = -1  # -1 = 昨天
    DAY_END = 6     # 6 = 未来6天
    COMPLETE_TASKS_SYNC_INTERVAL = 5  # 每5个tick执行一次全量扫描


    # 范围限制
    DAILY_NOTE_SECTIONS = ['# Day planner', '# Journey']
    SOURCE_FILE_CALLOUTS = ['> [!note] Tasks', '> [!note]- Tasks', '> [!note]+ Tasks']

    # ==========================
    # 2. Apple Sync 配置 (来自 TaskSynctoreminder)
    # ==========================
    APPLE_SYNC_STATE_FILE = os.path.join(DAILY_NOTE_DIR, ".apple_sync_state.json")

    # 默认日历
    REMINDERS_LIST_NAME = "不重要不紧急"

    # 标签映射
    TAG_MAPPINGS = [
        {"tag": "#A", "calendar": "重要紧急"},
        {"tag": "#B", "calendar": "重要不紧急"},
        {"tag": "#C", "calendar": "紧急不重要"},
        {"tag": "#D", "calendar": "不重要不紧急"}
    ]

    # 警报规则
    ALARM_RULES = {
        "重要紧急": -30,
        "重要不紧急": -5,
        "紧急不重要": 0,
        "不重要不紧急": 0,
        REMINDERS_LIST_NAME: 0
    }

    # 派生常量 (来自 TaskSynctoreminder/constants.py)
    CAL_TO_TAG = {m["calendar"]: m["tag"] for m in TAG_MAPPINGS}
    ALL_MANAGED_CALENDARS = [m["calendar"] for m in TAG_MAPPINGS]
    if REMINDERS_LIST_NAME not in ALL_MANAGED_CALENDARS:
        ALL_MANAGED_CALENDARS.append(REMINDERS_LIST_NAME)

    # 安全分隔符
    DELIMITER_FIELD = "|#|"
    DELIMITER_ROW = "^@^"

```

---
## File: main.py
```py
import time
import signal
import os
import sys

# Add src to sys.path to allow importing dailynotes package
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from dailynotes.manager import FusionManager
from config import Config
from dailynotes.utils import ProcessLock, Logger

if __name__ == "__main__":
    app = FusionManager()

    Logger.info(f"=== Antigravity Sync v1.0 (反重力架构) ===")
    Logger.info(f"路径: {Config.ROOT_DIR}")
    Logger.info(f"模式: Obsidian 优先 + Apple Calendar 下游同步")
    Logger.info(f"频率: 内部 {Config.TICK_INTERVAL}s | 外部 10s 最小间隔")
    Logger.info("=" * 50)

    # 第一次尝试获取锁
    if not ProcessLock.acquire():
        Logger.info(f"⚠️  检测到锁文件 ({Config.LOCK_FILE})")
        old_pid = ProcessLock.read_pid()

        wait_seconds = 3
        Logger.info(f"⏳ 等待原进程 ({old_pid if old_pid else 'Unknown'}) 执行完当前周期 ({wait_seconds}s)...")
        time.sleep(wait_seconds)

        if old_pid:
            Logger.info(f"🛑 发送终止信号 (SIGTERM) 给 PID: {old_pid}...")
            try:
                os.kill(old_pid, signal.SIGTERM)

                # [优雅关闭] 给它 3 秒时间保存状态并退出
                for _ in range(30):  # 30 * 0.1s = 3s
                    time.sleep(0.1)
                    try:
                        os.kill(old_pid, 0)  # 检查是否存活
                    except OSError:
                        Logger.info("   原进程已优雅退出。")
                        break
                else:
                    Logger.info(f"💀 原进程未响应，强制关闭 (SIGKILL) PID: {old_pid}...")
                    os.kill(old_pid, signal.SIGKILL)
            except ProcessLookupError:
                Logger.info("   原进程已不存在。")
            except Exception as e:
                Logger.error_once("shutdown_fail", f"   关闭失败: {e}")
        else:
            Logger.info("⚠️  无法读取旧进程PID（可能是旧版代码遗留），尝试直接清理锁文件...")

        Logger.info("🔄 正在重启服务...")
        time.sleep(1)

        # 第二次尝试获取锁
        if not ProcessLock.acquire():
            Logger.error_once("lock_fail", "❌ 无法获取锁，强制接管失败。请手动检查。")
            exit(1)
        else:
            Logger.info("✅ 成功接管锁，服务已启动。")

    try:
        app.run()
    except KeyboardInterrupt:
        Logger.info("\n停止服务...")
    finally:
        ProcessLock.release()

```

---
## File: src\dailynotes\__init__.py
```py
import sys
import os

# Ensure config can be imported from root if not already
# This is a fallback in case sys.path is messed up, but main.py should handle it.

```

---
## File: src\dailynotes\format_core.py
```py
import re
import os
import hashlib
import difflib
import unicodedata  # [NEW] 引入 unicode 支持
from config import Config
from .utils import FileUtils, Logger


class FormatCore:
    @staticmethod
    def _enforce_hyphen_space(line: str, context: str = "", filename: str = "") -> str:
        return line

    @staticmethod
    def normalize_indentation(content: str) -> str:
        return re.sub(r'(?m)^( +)', lambda m: m.group(1).replace('    ', '\t'), content)

    @staticmethod
    def auto_format_links(content: str) -> str:
        # [FIX] Escape brackets properly to avoid "nested set" warning
        pattern = r'(?<![\[\(\<])(https?://([^/\s\n]+)(?:/[^\s\n]*)?)'

        def _replacer(match): return f"[{match.group(2)}]({match.group(1)})"

        return re.sub(pattern, _replacer, content)

    @staticmethod
    def format_image_links(content: str) -> str:
        ext_pattern = re.compile(r'\.(png|jpe?g|gif|bmp|svg|pdf)$', re.IGNORECASE)

        def _replacer(match):
            inner = match.group(1)
            base = inner.split('|')[0]
            if ext_pattern.search(base): return f"![[{base}{Config.IMAGE_PARAM_SUFFIX}]]"
            return match.group(0)

        return re.sub(r'!\[\[([^\]]+)\]\]', _replacer, content)

    @staticmethod
    def sanitize_markdown_links(content: str) -> str:
        invalid_chars = r'[\\:]'

        def _clean_wiki(m): return f"[[{re.sub(invalid_chars, '', m.group(1)).strip()}]]"

        content = re.sub(r'\[\[(.*?)\]\]', _clean_wiki, content)

        def _clean_std(m): return f"[{re.sub(invalid_chars, '', m.group(1)).strip()}]({m.group(2)})"

        return re.sub(r'\[([^\]]+?)\]\(([^)]+?)\)', _clean_std, content)

    @staticmethod
    def get_header_sorting_key(title_line: str) -> str:
        """
        [FIX] 修复中文标题被过滤为空字符串导致排序混乱的问题
        """
        # 1. 移除 Markdown 标记 (#, [[, ]])
        clean_title = re.sub(r'[#\[\]]', '', title_line).strip().lower()
        # 2. 如果清理后不为空，直接使用；否则（纯符号标题）使用原字符串
        # 这样确保 "测试" 和 "调试" 有不同的 Key
        return clean_title if clean_title else title_line.strip()

    @staticmethod
    def _extract_sort_key(block_lines: list) -> tuple:
        """
        [SyncCore 一致性保证]
        严格对齐 SyncCore 的 _calculate_sort_key 逻辑
        返回: (has_time_bool, time_val, block_id)
        """
        if not block_lines: return (1, "99:99", "zzzzzz")
        first_line = block_lines[0].strip()

        # 1. Block ID
        id_match = re.search(r'\^([a-zA-Z0-9]{6,})\s*$', first_line)
        bid = id_match.group(1) if id_match else "zzzzzz"

        # 2. Time
        time_match = re.search(r'(\d{1,2}:\d{2})', first_line)
        if time_match:
            has_time = 0  # 有时间排前面
            time_val = time_match.group(1).zfill(5)
        else:
            has_time = 1  # 无时间排后面
            time_val = "99:99"

        return (has_time, time_val, bid)

    @classmethod
    def sort_day_planner_content(cls, content: str) -> str:
        if not content.strip(): return ""
        lines = content.split('\n')
        preamble = []
        blocks = []
        current_block = []
        in_task_block = False

        # [FIX] 仅匹配行首顶格的任务作为块的起点 (移除 ^[\t\s]*)
        # 这样缩进的子任务、图片会作为"内容"留在当前块中，不会被拆分
        task_start_pattern = re.compile(r'^-\s+\[[xX\s]\]')

        for line in lines:
            is_task_start = bool(task_start_pattern.match(line))
            if is_task_start:
                if current_block: blocks.append(current_block)
                current_block = [line]
                in_task_block = True
            elif in_task_block:
                # 遇到空行或分隔符才结束当前块
                if line.strip() == "" or line.strip().startswith('---'):
                    if current_block: blocks.append(current_block)
                    current_block = []
                    in_task_block = False
                    if line.strip(): preamble.append(line)
                else:
                    current_block.append(line)
            else:
                preamble.append(line)

        if current_block: blocks.append(current_block)

        # 排序 (使用更新后的 Key)
        sorted_blocks = sorted(blocks, key=cls._extract_sort_key)

        output = []
        p_text = "\n".join(preamble).strip()
        if p_text: output.append(p_text)

        for blk in sorted_blocks:
            # 块内部使用单换行拼接，保持紧凑
            blk_text = "\n".join(blk).rstrip()
            output.append(blk_text)

        # 块之间使用双换行拼接 (顶层任务之间留空)
        return "\n\n".join(output).strip()

    @classmethod
    def sort_markdown_sections(cls, text: str, filename: str = "") -> str:
        if not text.strip(): return text

        sections = re.split(r'^(#\s.*)$', text.strip(), flags=re.MULTILINE)
        output = []

        start_idx = 0
        if sections and not sections[0].startswith('#'):
            output.append(sections[0].strip())
            start_idx = 1

        i = start_idx
        while i < len(sections):
            title = sections[i].strip() if i < len(sections) else ""
            content = sections[i + 1] if i + 1 < len(sections) else ""

            l1_key = cls.get_header_sorting_key(title)
            is_target_section = "dayplanner" in l1_key or "journey" in l1_key

            # [FIX] 使用 unicodedata.normalize 确保内容处理的一致性
            sub_blocks = re.split(r'^(##\s.*)$', content, flags=re.MULTILINE)

            processed_sub_sections = []

            pre_l2 = sub_blocks[0].strip()
            if pre_l2:
                if is_target_section:
                    processed_sub_sections.append(cls.sort_day_planner_content(pre_l2))
                else:
                    processed_sub_sections.append(pre_l2)

            j = 1
            while j < len(sub_blocks):
                l2_title = sub_blocks[j].strip()
                l2_content = sub_blocks[j + 1].strip() if j + 1 < len(sub_blocks) else ""

                final_l2_content = ""
                if l2_content:
                    if is_target_section:
                        final_l2_content = cls.sort_day_planner_content(l2_content)
                    else:
                        final_l2_content = l2_content

                if final_l2_content:
                    processed_sub_sections.append(f"{l2_title}\n\n{final_l2_content}")
                else:
                    processed_sub_sections.append(l2_title)

                j += 2

            full_section_content = "\n\n".join(processed_sub_sections).strip()

            if full_section_content:
                output.append(f"{title}\n\n{full_section_content}")
            else:
                output.append(title)

            i += 2

        return "\n\n".join(output).strip()

    @staticmethod
    def _log_diff(step_name: str, old_content: str, new_content: str):
        if old_content == new_content: return
        if Config.DEBUG_MODE:
            d = difflib.Differ()
            diff = list(d.compare(old_content.splitlines(), new_content.splitlines()))
            changed_lines = [line.strip() for line in diff if line.startswith('+ ') or line.startswith('- ')]
            if len(changed_lines) > 0:
                Logger.debug(f"=== [{step_name}] Format Changes ===")
                for l in changed_lines[:5]: Logger.debug(l)

    @classmethod
    def execute(cls, filepath: str) -> bool:
        if not os.path.exists(filepath): return False
        content = FileUtils.read_content(filepath)
        if not content: return False

        # [CRITICAL] 1. 立即强制 NFC 标准化
        # 这一步是为了消除 macOS NFD 文件名和 Python 字符串之间的隐形差异
        content = unicodedata.normalize('NFC', content)

        orig_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

        # Step 2: 标准化处理
        c = cls.normalize_indentation(content)
        c = cls.auto_format_links(c)
        c = cls.sanitize_markdown_links(c)
        c = cls.format_image_links(c)

        # Step 3: 排序与排版
        fname = os.path.basename(filepath)
        prev_text = c
        c = cls.sort_markdown_sections(c, filename=fname)

        cls._log_diff("FormatCore", prev_text, c)

        c = c.strip() + "\n"
        new_hash = hashlib.md5(c.encode('utf-8')).hexdigest()

        if orig_hash != new_hash:
            Logger.info(f"✨ [Format] 优化日记排版与间距: {fname}")
            return FileUtils.write_file(filepath, c)
        return False

    @staticmethod
    def fix_broken_tab_bullets_global():
        if not os.path.exists(Config.DAILY_NOTE_DIR): return
        pattern = re.compile(r'(?m)^(\t+)-(?![ \t])')
        for filename in os.listdir(Config.DAILY_NOTE_DIR):
            if not filename.endswith('.md'): continue
            filepath = os.path.join(Config.DAILY_NOTE_DIR, filename)
            try:
                content = FileUtils.read_content(filepath)
                if not content: continue
                new_content = pattern.sub(r'\1- ', content)
                if new_content != content:
                    FileUtils.write_file(filepath, new_content)
                    Logger.info(f"🔧 [Fix] 修复列表缩进格式: {filename}")
            except Exception as e:
                Logger.debug(f"Global Fix Error {filename}: {e}")

```

---
## File: src\dailynotes\manager.py
```py
"""
Fusion Manager - Antigravity Architecture
Unified single-threaded pipeline with priority-based execution.

Priority Order:
1. Internal (Dailynotes): Obsidian formatting, task sync - HIGH PRIORITY
2. External (Apple Sync): Apple Calendar sync - LOW PRIORITY, only when stable

Key Features:
- Dirty Flag Blocking: If internal modified file, skip external sync for this tick
- Tick-Based Scheduling: Fast for today, slow for historical/future dates
- [REFACTORED] Content-Hash Self-Awareness: Uses content identity instead of mtime
"""
import os
import sys
import time
import datetime
import signal
from config import Config
from .utils import Logger, FileUtils
from .format_core import FormatCore
from .state_manager import StateManager
from .sync import SyncCore
from external.apple_sync_adapter import AppleSyncAdapter


class FusionManager:
    """
    Unified sync manager implementing Antigravity Architecture.
    
    Core Logic:
    - 主权在内 (Sovereignty Inside): Dailynotes runs first
    - 脏标志阻断 (Dirty Flag): If internal modified, skip external
    - Tick分频调度 (Tick-Based Frequency): Today fast, others slow
    """
    
    def __init__(self):
        self.sm = StateManager()
        self.sync_core = SyncCore(self.sm)
        
        # [NEW] Initialize Apple Sync adapter (lazy, platform-safe)
        self.apple_sync = AppleSyncAdapter()
        
        # State tracking
        self.last_active_time = time.time()
        
        # [NEW] Tick-based scheduling for full date range scan
        self.tick_counter = 0  # Counts ticks since last full scan
        self.today_last_hash = None  # Track today's diary hash for change detection

    def check_debounce(self, filepath):
        """
        Check if file is stable for processing.
        [REFACTORED] Uses content-hash to distinguish system writes from user edits.
        """
        if not os.path.exists(filepath):
            return False
        
        # Read current content and calculate its hash
        content = FileUtils.read_content(filepath)
        if content is None:
            return False
        
        content_hash = FileUtils.calculate_hash(content)
        
        # If hash matches a system write, file is "self-owned" -> stable
        # Note: is_system_write() consumes the hash (one-time use)
        if FileUtils.is_system_write(content_hash):
            return True
        
        # Otherwise, check mtime-based cooldown (user is typing)
        mtime = FileUtils.get_mtime(filepath)
        idle = time.time() - mtime
        return idle >= Config.TYPING_COOLDOWN_SECONDS

    def is_user_active(self):
        """
        [Activity Detection] Check for "hot" files.
        If user is editing today's diary or recently modified any file, consider active.
        [REFACTORED] Uses content-hash to ignore system edits.
        """
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{today_str}.md")

        if os.path.exists(daily_path):
            # Check if this is a system write (don't consume the hash)
            content = FileUtils.read_content(daily_path)
            if content:
                content_hash = FileUtils.calculate_hash(content)
                if FileUtils.check_system_write(content_hash):
                    return False  # System edit, not user activity

            # If file was modified by USER in the last 60 seconds, user is in "flow" state
            mtime = FileUtils.get_mtime(daily_path)
            if time.time() - mtime < 60:
                return True

        return False

    def check_today_changed(self) -> bool:
        """
        Check if today's diary content has changed since last check.
        Used to reset the tick counter for full date range scans.
        """
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{today_str}.md")
        
        if not os.path.exists(daily_path):
            return False
        
        content = FileUtils.read_content(daily_path)
        if content is None:
            return False
        
        current_hash = FileUtils.calculate_hash(content)
        
        if self.today_last_hash is None:
            # First check, initialize
            self.today_last_hash = current_hash
            return False
        
        if current_hash != self.today_last_hash:
            self.today_last_hash = current_hash
            return True
        
        return False

    def get_date_range(self) -> list:
        """
        Generate date strings from DAY_START to DAY_END relative to today.
        DAY_START = -1 means yesterday
        DAY_END = 6 means 6 days in the future
        """
        today = datetime.date.today()
        dates = []
        for delta in range(Config.DAY_START, Config.DAY_END + 1):
            target_date = today + datetime.timedelta(days=delta)
            date_str = target_date.strftime('%Y-%m-%d')
            # Skip dates before sync start date
            if date_str >= Config.SYNC_START_DATE:
                dates.append(date_str)
        return dates

    def process_single_date(self, date_str):
        """
        Process a single date: internal sync + formatting + Apple sync.
        Returns detailed result dict.
        """
        results = {
            "internal_mod": False,       # SyncCore/FormatCore logic changed Obsidian file
            "apple_to_obsidian": False,  # Apple sync changed Obsidian file (C->O)
            "obsidian_to_apple": False,  # Obsidian sync changed Apple Calendar (O->C)
            "skipped": False
        }

        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{date_str}.md")
        
        # Debounce check
        if os.path.exists(daily_path):
            content = FileUtils.read_content(daily_path)
            is_system_edit = False
            if content:
                content_hash = FileUtils.calculate_hash(content)
                is_system_edit = FileUtils.check_system_write(content_hash)
            
            if not is_system_edit:
                idle_duration = time.time() - FileUtils.get_mtime(daily_path)
                if idle_duration < Config.TYPING_COOLDOWN_SECONDS:
                    # User is typing, skip
                    results["skipped"] = True
                    return results

        # --- [PRIORITY 1] Obsidian Internal Processing ---
        if self.check_debounce(daily_path) or not os.path.exists(daily_path):
            try:
                # A. Task Flow (Projects <-> Daily)
                source_data_by_date = self.sync_core.scan_all_source_tasks()
                tasks_for_date = source_data_by_date.get(date_str, {})
                # Note: SyncCore.process_date currently doesn't return boolean, assuming it might modify tasks
                # but currently task movement logic is mainly in dispatch_project_tasks which is not called here directly?
                # Wait, SyncCore.process_date might invoke task movement if implemented.
                # Assuming scan_all_source_tasks + process_date covers internal logic.
                self.sync_core.process_date(date_str, tasks_for_date)

                # B. Formatting (FormatCore)
                if os.path.exists(daily_path):
                    if FormatCore.execute(daily_path):
                        results["internal_mod"] = True
                        Logger.info(f"   ✨ [Internal] 格式化完成: {date_str}")

            except Exception as e:
                Logger.error_once(f"sync_fail_{date_str}", f"内部同步异常 [{date_str}]: {e}")

        # --- [PRIORITY 2] Apple Calendar Sync ---
        should_sync_apple = False
        
        if results["internal_mod"]:
            should_sync_apple = True
            Logger.info(f"   ⚡ [Trigger] 内部修改触发立即同步: {date_str}")
        elif os.path.exists(daily_path) and self.check_debounce(daily_path):
            should_sync_apple = True

        if should_sync_apple:
            try:
                obs_mod, apple_mod = self.apple_sync.sync_day(date_str)
                results["apple_to_obsidian"] = obs_mod
                results["obsidian_to_apple"] = apple_mod
                
                if obs_mod or apple_mod:
                    Logger.info(f"   🍏 [Apple] {date_str} 同步成功")
                else:
                    Logger.info(f"   🍏 [Apple] {date_str} 未检测到任何改动")
            except Exception as e:
                Logger.error_once(f"apple_exec_fail_{date_str}", f"外部同步异常: {e}")

        return results

    def run(self):
        """
        Main event loop with tick-based scheduling.
        """
        def _term_handler(signum, frame):
            raise SystemExit("Received SIGTERM")

        signal.signal(signal.SIGTERM, _term_handler)

        TICK_INTERVAL = Config.TICK_INTERVAL
        FULL_SCAN_MULTIPLIER = Config.COMPLETE_TASKS_SYNC_INTERVAL

        Logger.info(f"🚀 融合引擎启动: Obsidian (Priority High) + Apple Calendar (Priority Low)")
        Logger.info(f"   Tick间隔: {TICK_INTERVAL}s | 全量扫描倍率: {FULL_SCAN_MULTIPLIER}x")
        Logger.info(f"   日期范围: DAY_START={Config.DAY_START} ~ DAY_END={Config.DAY_END}")

        try:
            while True:
                self.tick_counter += 1
                today_str = datetime.date.today().strftime('%Y-%m-%d')

                # --- [EVERY TICK] Fix global formatting issues ---
                FormatCore.fix_broken_tab_bullets_global()

                # --- [EVERY TICK] Process today's diary ---
                res = self.process_single_date(today_str)

                # --- [CHECK] Change Detection & Reset ---
                reset_needed = False
                reset_reasons = []

                if res["internal_mod"]: reset_reasons.append("Obsidian 内部整理")
                if res["apple_to_obsidian"]: reset_reasons.append("Apple 日历变更")
                if res["obsidian_to_apple"]: reset_reasons.append("Obsidian 推送变更")

                if len(reset_reasons) > 0:
                    reset_needed = True
                    # Update local tracker to match the new state immediately, 
                    # preventing check_today_changed from flagging system writes as manual edits.
                    today_path = os.path.join(Config.DAILY_NOTE_DIR, f"{today_str}.md")
                    if os.path.exists(today_path):
                        content = FileUtils.read_content(today_path)
                        if content:
                            self.today_last_hash = FileUtils.calculate_hash(content)

                # Check for manual edits (User typed something)
                # check_today_changed will return True if hash is different from self.today_last_hash
                if self.check_today_changed():
                    if not reset_needed:
                        # Only report if it wasn't already covered by system actions
                        reset_needed = True
                        reset_reasons.append("今日日记变更(手动)")

                if reset_needed:
                    reason_str = " + ".join(reset_reasons)
                    Logger.info(f"   🔄 [Reset] {reason_str}，重置全量扫描倒计时")
                    self.tick_counter = 0

                # --- [FULL SCAN] Every FULL_SCAN_MULTIPLIER ticks ---
                if self.tick_counter >= FULL_SCAN_MULTIPLIER:
                    self.tick_counter = 0
                    Logger.info(f"   📅 [Full Scan] 执行全量日期范围扫描...")
                    
                    date_range = self.get_date_range()
                    for date_str in date_range:
                        if date_str == today_str:
                            continue  # Already processed
                        self.process_single_date(date_str)

                # --- [LIVE COUNTDOWN] ---
                for i in range(TICK_INTERVAL, 0, -1):
                    msg = f"\r[Wait] 下次检测倒计时: {i}s   "
                    sys.stdout.write(msg)
                    sys.stdout.flush()
                    time.sleep(1)
                
                sys.stdout.write("\r" + " " * 40 + "\r")
                sys.stdout.flush()

        except KeyboardInterrupt:
            raise
        finally:
            self.sm.save()

```

---
## File: src\dailynotes\state_manager.py
```py
import os
import json
import time
import hashlib
import re
import shutil
import unicodedata
from config import Config
from .utils import Logger


class StateManager:
    def __init__(self):
        self.state = {}
        self.load()

    def load(self):
        backup_file = Config.STATE_FILE + ".bak"

        # 1. 尝试主文件
        if os.path.exists(Config.STATE_FILE):
            try:
                with open(Config.STATE_FILE, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
                return
            except Exception:
                Logger.error_once("state_load_main", "主状态文件损坏，尝试读取备份...")

        # 2. 尝试备份文件
        if os.path.exists(backup_file):
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
                Logger.info("[StateManager.py] 成功从备份文件恢复状态。")
                return
            except Exception:
                Logger.error_once("state_load_bak", "备份文件也损坏！")

        # 3. 完全失败 -> 重置
        if os.path.exists(Config.STATE_FILE) or os.path.exists(backup_file):
            Logger.info("\033[91m[CRITICAL] 状态文件严重损坏，且无法恢复！已重置为空状态。\033[0m")

        self.state = {}

    def save(self):
        try:
            # 1. 先创建备份（安全保障）
            if os.path.exists(Config.STATE_FILE):
                try:
                    shutil.copy2(Config.STATE_FILE, Config.STATE_FILE + ".bak")
                except OSError:
                    pass

            # 2. 写入新状态
            with open(Config.STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            Logger.error_once("state_save", f"状态保存失败: {e}")

    def _norm_path(self, path):
        """核心修复：路径标准化 helper"""
        try:
            return os.path.normcase(os.path.abspath(path))
        except:
            return path

    def get_task_hash(self, bid):
        return self.state.get(bid, {}).get('hash')

    def find_id_by_hash(self, source_path, content_hash):
        """通过"标准化的文件路径 + 内容指纹"反查 Block ID。"""
        norm_source = self._norm_path(source_path)

        for bid, data in self.state.items():
            if data.get('source_path') == norm_source and data.get('hash') == content_hash:
                return bid
        return None

    def get_task_date(self, bid):
        return self.state.get(bid, {}).get('date')

    def update_task(self, bid, content_hash, source_path, date_str=None):
        entry = {
            'hash': content_hash,
            'source_path': self._norm_path(source_path),
            'last_seen': time.time()
        }
        if date_str:
            entry['date'] = date_str
        elif bid in self.state and 'date' in self.state[bid]:
            entry['date'] = self.state[bid]['date']

        self.state[bid] = entry

    def remove_task(self, bid):
        if bid in self.state: del self.state[bid]

    def normalize_text(self, text):
        """
        [v13.4 Final Stability] 为指纹识别标准化文本。
        策略：剥离所有可能导致双向差异的格式符号。
        """
        if not text: return ""
        text = unicodedata.normalize('NFKC', text)

        # 1. 忽略 Markdown 链接格式: [text](url) -> url (解决 FormatCore 自动转换导致的差异)
        #    注意：这里保留 url，因为 url 是核心内容
        text = re.sub(r'\[([^\]]+?)\]\(([^)]+?)\)', r'\2', text)

        # 2. [关键修复] 移除所有 [[WikiLink]] 格式
        #    日记里有 [[文件名]]，原文件里没有。为了让哈希一致，必须把它们都视为"透明"。
        #    这同时也移除了 [[日期]]，这是符合预期的，因为日期属于元数据。
        text = re.sub(r'\[\[.*?\]\]', '', text)

        # 3. 移除时间段 (Day Planner 格式)
        text = re.sub(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', '', text)
        text = re.sub(r'\d{1,2}:\d{2}', '', text)

        # 4. 移除 ID (^xxxxxx)
        text = re.sub(r'(?<=\s)\^[a-zA-Z0-9]{6,7}\s*$', '', text)

        # 5. 压缩空白
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def calc_hash(self, status, content_text):
        norm_content = self.normalize_text(content_text)
        norm_status = status.strip()
        # 只要内容对得上，状态对得上，指纹就一致，不再受 [[Tag]] 或 [Link]() 干扰
        raw_fingerprint = f"{norm_status}|{norm_content}"
        return hashlib.md5(raw_fingerprint.encode('utf-8')).hexdigest()

```

---
## File: src\dailynotes\utils.py
```py
import os
import datetime
import time
import tempfile
import inspect
import hashlib
from typing import List, Union
from config import Config

# 尝试导入 fcntl (仅限 Unix/macOS)
try:
    import fcntl
except ImportError:
    fcntl = None


class Logger:
    _shown_errors = set()

    @staticmethod
    def _get_caller_info():
        # Stack: 0=here, 1=caller(info/debug), 2=actual caller
        try:
            stack = inspect.stack()
            # Find the first frame outside of utils.py/Logger
            for frame in stack[1:]:
                fn = os.path.basename(frame.filename)
                if fn != 'utils.py':
                    func = frame.function
                    if func == '<module>': func = 'Main'
                    return f"[{fn}:{func}]"
            return "[Unknown:Unknown]"
        except Exception:
            return "[Unknown:Unknown]"

    @staticmethod
    def error_once(key, message):
        if key not in Logger._shown_errors:
            caller = Logger._get_caller_info()
            print(f"\033[91m[ERROR] {caller} {message}\033[0m")
            Logger._shown_errors.add(key)

    @staticmethod
    def info(message, date_tag=None):
        # [特性] 聚焦日志：仅显示今天的日志（当前文件）
        t = datetime.datetime.now().strftime('%H:%M:%S')
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        
        if date_tag and date_tag != today_str:
            return # 跳过历史日志以减少干扰
            
        prefix = f"[{date_tag}] " if date_tag else ""
        caller = Logger._get_caller_info()
        print(f"\033[92m[{t} INFO] {caller} {prefix}{message}\033[0m")

    @staticmethod
    def debug(message):
        if Config.DEBUG_MODE:
            caller = Logger._get_caller_info()
            print(f"\033[90m[DEBUG] {caller} {message}\033[0m")

    @staticmethod
    def debug_block(title, lines):
        if Config.DEBUG_MODE:
            caller = Logger._get_caller_info()
            print(f"\033[96m--- [DEBUG] {caller} {title} ---\033[0m")
            for line in lines:
                print(f"  | {line.rstrip()}")
            print(f"\033[96m-----------------------\033[0m")


class FileUtils:
    # [REFACTORED] Content-hash based self-awareness
    # Replaces fragile mtime comparison with deterministic content identity
    _system_write_hashes = set()
    _MAX_HASH_CACHE = 50  # Prevent memory leak

    @staticmethod
    def calculate_hash(content: str) -> str:
        """Fast MD5 hash for content identity."""
        if content is None:
            content = ""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    @classmethod
    def is_system_write(cls, content_hash: str) -> bool:
        """
        Check if hash matches a system write.
        If match found, removes it from set (one-time use).
        """
        if content_hash in cls._system_write_hashes:
            cls._system_write_hashes.discard(content_hash)
            return True
        return False

    @classmethod
    def check_system_write(cls, content_hash: str) -> bool:
        """
        Check if hash matches a system write WITHOUT removing it.
        Used for activity detection where we don't want to consume the hash.
        """
        return content_hash in cls._system_write_hashes

    @staticmethod
    def read_file(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.readlines()
        except Exception:
            return None

    @staticmethod
    def read_content(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception:
            return None

    @staticmethod
    def write_file(filepath, lines_or_content):
        # [原子性] 使用 tempfile + os.replace 以确保原子写入
        dir_name = os.path.dirname(filepath) or '.'
        temp_name = None
        
        # Normalize content to string for hashing
        if lines_or_content is None:
            final_content = ""
        elif isinstance(lines_or_content, list):
            final_content = "".join([str(l) for l in lines_or_content if l is not None])
        else:
            final_content = str(lines_or_content)
        
        # [CRITICAL] Calculate hash BEFORE write and register
        content_hash = FileUtils.calculate_hash(final_content)
        
        # Manage cache size to prevent memory leak
        if len(FileUtils._system_write_hashes) >= FileUtils._MAX_HASH_CACHE:
            FileUtils._system_write_hashes.clear()
        FileUtils._system_write_hashes.add(content_hash)
        
        try:
            # 在同一目录中创建临时文件（原子重命名所需）
            with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, encoding='utf-8') as tf:
                temp_name = tf.name
                tf.write(final_content)
                
                # 刷新并 fsync 以确保数据物理写入
                tf.flush()
                os.fsync(tf.fileno())
            
            # 原子交换
            os.replace(temp_name, filepath)
            return True
            
        except Exception as e:
            Logger.error_once(f"write_{filepath}", f"写入失败 {filepath}: {e}")
            # Remove hash on failure (write didn't happen)
            FileUtils._system_write_hashes.discard(content_hash)
            # 如果临时文件存在，则清理
            if temp_name and os.path.exists(temp_name):
                try:
                    os.remove(temp_name)
                except OSError:
                    pass
            return False

    @staticmethod
    def get_mtime(filepath):
        try:
            return os.path.getmtime(filepath)
        except OSError:
            return 0

    @staticmethod
    def is_excluded(path):
        path = os.path.normpath(path)
        for exclude in Config.EXCLUDE_DIRS:
            exclude = os.path.normpath(exclude)
            if path == exclude or path.startswith(exclude + os.sep):
                return True
        if '/.trash/' in path or path.endswith('/.trash') or '\\.trash\\' in path:
            return True
        return False


class ProcessLock:
    _lock_fd = None

    @classmethod
    def acquire(cls):
        if not fcntl: return True
        try:
            if not os.path.exists(Config.DAILY_NOTE_DIR): return False
            # 打开文件，准备读写
            cls._lock_fd = os.open(Config.LOCK_FILE, os.O_CREAT | os.O_RDWR)
            
            # 尝试获取排他锁（非阻塞）
            fcntl.flock(cls._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # [新增] 获取锁成功，清空文件并写入当前 PID
            os.ftruncate(cls._lock_fd, 0)
            os.write(cls._lock_fd, str(os.getpid()).encode())
            
            return True
        except (BlockingIOError, OSError):
            # 获取失败，关闭文件描述符
            if cls._lock_fd is not None:
                try:
                    os.close(cls._lock_fd)
                except OSError:
                    pass
                cls._lock_fd = None
            return False

    @staticmethod
    def read_pid():
        """尝试从锁文件中读取持有者的 PID"""
        try:
            if os.path.exists(Config.LOCK_FILE):
                with open(Config.LOCK_FILE, 'r') as f:
                    content = f.read().strip()
                    if content:
                        return int(content)
        except Exception:
            return None
        return None

    @classmethod
    def release(cls):
        if cls._lock_fd is not None:
            fcntl.flock(cls._lock_fd, fcntl.LOCK_UN)
            os.close(cls._lock_fd)
            cls._lock_fd = None
        try:
            if os.path.exists(Config.LOCK_FILE):
                os.remove(Config.LOCK_FILE)
        except OSError:
            pass

```

---
## File: src\dailynotes\sync\__init__.py
```py
from .engine import SyncCore

```

---
## File: src\dailynotes\sync\discovery.py
```py
import os
import unicodedata
from config import Config
from ..utils import FileUtils
from .parsing import parse_yaml_tags

def scan_projects():
    project_map = {}
    project_path_map = {}
    file_path_map = {}
    
    # 1. 强制全量递归扫描
    for root, dirs, files in os.walk(Config.ROOT_DIR):
        # 排除常规忽略目录
        dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
        if FileUtils.is_excluded(root): continue

        main_files = []
        for f in files:
            if f.endswith('.md'):
                path = os.path.join(root, f)
                stem = unicodedata.normalize('NFC', os.path.splitext(f)[0])
                file_path_map[stem] = path # 记录所有文件路径
                
                # 检查 main 标签 (需要读取文件)
                if 'main' in parse_yaml_tags(FileUtils.read_file(path) or []):
                    main_files.append(f)

        # 只要当前目录有 main 文件，就注册为项目（不管父级是否也是项目）
        if len(main_files) >= 1:
            # Sort by mtime DESC, then filename ASC
            # We want the LATEST modified.
            def get_sort_key(fname):
                fpath = os.path.join(root, fname)
                mtime = os.path.getmtime(fpath)
                return (-mtime, fname)
            
            main_files.sort(key=get_sort_key)
            selected_main = main_files[0]
            
            p_name = unicodedata.normalize('NFC', os.path.splitext(selected_main)[0])
            project_map[root] = p_name
            project_path_map[p_name] = os.path.join(root, selected_main)
            
    return project_map, project_path_map, file_path_map

```

---
## File: src\dailynotes\sync\engine.py
```py
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

                            # [FIX] Remove existing return links to prevent duplication
                            clean_pure = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', clean_pure)

                            clean_pure = re.sub(r'\s+', ' ', clean_pure).strip()
                            
                            # [FIX] Return link target logic
                            ret_target = target_p_name
                            # Extract potential file links from the cleaned content
                            m_links = re.findall(r'\[\[(.*?)(?:[\|#].*)?\]\]', clean_pure)
                            if m_links:
                                ret_target = m_links[0]
                            
                            # Build return link
                            ret_link = f"[[{ret_target}#^{bid}|⮐]]"
                            
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

```

---
## File: src\dailynotes\sync\ingestion.py
```py
import os
import re
import datetime
import random
import string
from typing import Dict
from config import Config
from ..utils import Logger, FileUtils
from .parsing import capture_block, clean_task_text, normalize_block_content, get_indent_depth
from .rendering import format_line, inject_into_task_section

def generate_block_id():
    return '^' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

def scan_all_source_tasks(project_map, sm) -> Dict[str, Dict]:
    # Need to run scan_projects before this? No, project_map is passed in.
    # self.scan_projects() # Caller handles this.
    
    source_data_by_date = {}
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    for root, dirs, files in os.walk(Config.ROOT_DIR):
        dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
        if FileUtils.is_excluded(root): continue
        curr_proj = None
        temp = root
        while temp.startswith(Config.ROOT_DIR):
            if temp in project_map: curr_proj = project_map[temp]; break
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

            in_task_section = False
            current_section_date = None
            seen_section_dates = set()
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                if stripped == '# Tasks':
                    in_task_section = True;
                    current_section_date = None;
                    seen_section_dates.clear();
                    i += 1;
                    continue
                if stripped == '----------':
                    in_task_section = False;
                    current_section_date = None;
                    i += 1;
                    continue
                if not in_task_section: i += 1; continue
                header_match = re.match(r'^#+\s*\[\[\s*(\d{4}-\d{2}-\d{2})\s*\]\]', stripped)
                if header_match:
                    date_str = header_match.group(1)
                    if date_str in seen_section_dates:
                        Logger.info(f"   🔍 发现重复标题 {date_str}，将触发重组...");
                        mod = True
                    else:
                        seen_section_dates.add(date_str)
                    current_section_date = date_str;
                    i += 1;
                    continue
                if stripped.startswith('#'): current_section_date = None; i += 1; continue
                if not re.match(r'^\s*-\s*\[.\]', line): i += 1; continue
                task_date = None
                if current_section_date:
                    task_date = current_section_date
                else:
                    date_match = re.search(r'[📅✅]\s*(\d{4}-\d{2}-\d{2})', line)
                    if date_match:
                        task_date = date_match.group(1)
                    else:
                        link_match = re.search(r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\||\]\])', line)
                        if link_match: task_date = link_match.group(1)
                is_in_inbox_area = (current_section_date is None)
                if is_in_inbox_area and not task_date: i += 1; continue
                if not task_date: task_date = today_str; mod = True

                # [MODIFIED] Use visual depth
                indent = get_indent_depth(line)

                status_match = re.search(r'-\s*\[(.)\]', line)
                st = status_match.group(1) if status_match else ' '
                id_m = re.search(r'\^([a-zA-Z0-9]{6,7})\s*$', line)
                bid = id_m.group(1) if id_m else None
                if not bid:
                    raw_block, _ = capture_block(lines, i)
                    temp_clean = clean_task_text(line, None, fname)
                    temp_clean = re.sub(r'\s+\^?[a-zA-Z0-9]*$', '', temp_clean).strip()
                    combined_body = normalize_block_content(raw_block[1:])
                    temp_combined_text = temp_clean + "|||" + combined_body
                    recovery_hash = sm.calc_hash(st, temp_combined_text)
                    found_id = sm.find_id_by_hash(path, recovery_hash)
                    if found_id:
                        Logger.info(f"   🚑 [RESCUE] 指纹匹配成功! '{temp_clean[:10]}...' -> 复活 ID: {found_id}")
                        bid = found_id;
                        mod = True
                    else:
                        bid = generate_block_id().replace('^', '');
                        mod = True
                clean_txt = clean_task_text(line, bid, context_name=fname)
                dates_pattern = r'([📅✅]\s*\d{4}-\d{2}-\d{2}|\[\[\d{4}-\d{2}-\d{2}(?:#\^[a-zA-Z0-9]+)?(?:\|[📅⮐])?\]\])'
                dates = " ".join(re.findall(dates_pattern, line))
                if current_section_date and current_section_date not in dates: dates = f"[[{task_date}]]"; mod = True
                if task_date not in line and not dates: dates = f"[[{task_date}]]"; mod = True
                new_line = format_line(indent, st, clean_txt, dates, fname, bid, False)
                if new_line.strip() != line.strip(): lines[i] = new_line; mod = True

                # [TIME GATE]
                if task_date < Config.SYNC_START_DATE:
                    _, consumed = capture_block(lines, i)
                    i += consumed
                    continue

                block, consumed = capture_block(lines, i)
                combined_text = clean_txt + "|||" + normalize_block_content(block[1:])
                content_hash = sm.calc_hash(st, combined_text)
                if task_date not in source_data_by_date: source_data_by_date[task_date] = {}
                source_data_by_date[task_date][bid] = {
                    'proj': curr_proj, 'bid': bid, 'pure': clean_txt, 'status': st,
                    'path': path, 'fname': fname, 'raw': block, 'hash': content_hash, 'indent': indent,
                    'dates': dates, 'is_quoted': False
                }
                i += consumed
            if mod:
                lines = inject_into_task_section(lines, [])
                # [CHECK] 比对磁盘文件，防止死循环
                orig = FileUtils.read_file(path)
                new_c = "".join(lines)
                old_c = "".join(orig) if orig else ""
                if new_c != old_c:
                    Logger.info(f"   💾 [WRITE] 自动格式化源文件 (Scan): {os.path.basename(path)}")
                    FileUtils.write_file(path, lines)
    for delta in range(3):
        target_d = datetime.date.today() - datetime.timedelta(days=delta)
        target_s = target_d.strftime('%Y-%m-%d')
        if target_s not in source_data_by_date: source_data_by_date[target_s] = {}
    return source_data_by_date

```

---
## File: src\dailynotes\sync\parsing.py
```py
import re
import unicodedata

def _get_indent_depth(line):
    no_quote = re.sub(r'^>\s?', '', line)
    expanded = no_quote.expandtabs(4)
    return len(expanded) - len(expanded.lstrip())

# Alias for external use
get_indent_depth = _get_indent_depth

def parse_yaml_tags(lines):
    tags = []
    if not lines or lines[0].strip() != '---': return []
    in_yaml = False
    for i, line in enumerate(lines):
        if i == 0: in_yaml = True; continue
        if line.strip() == '---': break
        if in_yaml and ('tags:' in line or 'main' in line):
            if re.search(r'\bmain\b', line): tags.append('main')
    return tags

def clean_task_text(line, block_id=None, context_name=None):
    # 1. remove status and indent
    clean_text = re.sub(r'^[\s>]*-\s*\[.\]', '', line)
    
    # 2. remove time (00:00 - 00:00)
    clean_text = re.sub(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', '', clean_text)
    clean_text = re.sub(r'\d{1,2}:\d{2}', '', clean_text)
    
    # 3. remove ID
    if block_id:
        clean_text = re.sub(r'\^' + re.escape(block_id) + r'\s*$', '', clean_text)
    else:
        clean_text = re.sub(r'\^[a-zA-Z0-9]{6,}\s*$', '', clean_text)
        
    # 4. remove return links
    clean_text = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', clean_text)
    
    # 5. remove date links
    clean_text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}]]', '', clean_text)
    # remove emoji date
    clean_text = re.sub(r'📅\s?\[\[\d{4}-\d{2}-\d{2}]]', '', clean_text)

    # 6. [NEW] Remove self-referencing project links if context is known
    # If we are syncing to "ProjectA.md", remove "[[ProjectA]]" from the text
    if context_name:
        # Normalize context name to handle NFC/NFD potential mismatch
        c_name = unicodedata.normalize('NFC', context_name)
        # Regex to match [[ContextName]] or [[ContextName|Alias]]
        # We use re.escape to handle filenames with special regex chars
        pattern = rf'\[\[{re.escape(c_name)}(?:\|.*?)?\]\]'
        clean_text = re.sub(pattern, '', clean_text)

    # 7. Final cleanup of extra spaces
    return re.sub(r'\s+', ' ', clean_text).strip()

def normalize_block_content(block_lines):
    normalized = []
    for line in block_lines:
        clean = re.sub(r'^[\s>]+', '', line).strip()
        if not clean or clean in ['-', '- ']: continue
        normalized.append(clean)
    return "\n".join(normalized) + "\n"

def capture_block(lines, start_idx):
    parent_indent = _get_indent_depth(lines[start_idx])
    block = [lines[start_idx]]
    consumed = 1
    
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        if not line.strip(): # Empty line, include it but...
             block.append(line)
             consumed += 1
             continue
             
        curr_indent = _get_indent_depth(line)
        if curr_indent > parent_indent:
            block.append(line)
            consumed += 1
        else:
            break
            
    return block, consumed

def extract_routing_info(line, file_path_map):
    """
    Extracts routing target from a line.
    Returns: (absolute_path_to_file, raw_link_text)
    """
    # Remove return links first to avoid false positives
    clean = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', line)
    
    matches = re.finditer(r'\[\[(.*?)\]\]', clean)
    for m in matches:
        raw_text = m.group(0) # [[WikiLink]]
        inner = m.group(1)
        pot = inner.split('|')[0].split('#')[0]
        pot = unicodedata.normalize('NFC', pot)
        
        if pot in file_path_map:
            return file_path_map[pot], raw_text
            
    return None, None

def extract_routing_target(line, file_path_map):
    """
    Compatibility wrapper for extract_routing_info.
    Returns just the path.
    """
    path, _ = extract_routing_info(line, file_path_map)
    return path

```

---
## File: src\dailynotes\sync\rendering.py
```py
import re
import random
import string
import datetime
import unicodedata
from ..utils import Logger
from .parsing import clean_task_text, get_indent_depth

def normalize_raw_tasks(lines, filename_stem):
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

def maintain_section_integrity(lines):
    cleaned = []
    empty_count = 0
    for line in lines:
        if not line.strip():
            empty_count += 1
            if empty_count <= 1:
                cleaned.append(line)
        else:
            empty_count = 0
            cleaned.append(line)
    return cleaned

def _calculate_sort_key(block_data):
    """
    [v12.2 Absolute Hybrid Sort]
    绝对排序规则：
    1. 第一梯队：有时间限制的任务 (Time-Blocked) -> 按时间先后 (08:00 < 09:00)
    2. 第二梯队：无时间限制的任务 -> 按 Block ID 字典序 (^aaaa < ^zzzz)
    """
    first_line = block_data['lines'][0].strip()
    block_id = block_data['id']

    # --- 1. 时间提取 ---
    time_match = re.search(r'(\d{1,2}:\d{2})', first_line)

    if time_match:
        has_time = 0
        time_val = time_match.group(1).zfill(5)
    else:
        has_time = 1
        time_val = "99:99"

    return (has_time, time_val, block_id)

def inject_into_task_section(file_lines, block_lines, filename_stem=None):
    """
    [v14.5 Indent-Aware Injection]
    修复 inject 逻辑误将缩进的子任务 (- [ ]) 识别为新 Block 导致的截断问题。
    现在只有【顶层任务】(缩进 < 2 空格) 才会触发分块。
    """
    # --- 1. 定位锚点 ---
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(file_lines):
        if line.strip() == '# Tasks': start_idx = i; break

    if start_idx != -1:
        for i in range(start_idx + 1, len(file_lines)):
            curr_line = file_lines[i].strip()
            if curr_line == '----------': end_idx = i; break
        if end_idx <= start_idx: end_idx = -1

    # --- 2. 自愈结构 ---
    need_scaffold = False
    if start_idx == -1:
        need_scaffold = True
        file_lines = [l for l in file_lines if l.strip() not in ('# Tasks', '----------')]
    elif end_idx == -1:
        file_lines.append("\n----------\n")
        end_idx = len(file_lines) - 1
    elif end_idx < start_idx:
        need_scaffold = True
        file_lines = [l for l in file_lines if l.strip() not in ('# Tasks', '----------')]

    if need_scaffold:
        insert_pos = 0
        if file_lines and file_lines[0].strip() == '---':
            for i in range(1, len(file_lines)):
                if file_lines[i].strip() == '---': insert_pos = i + 1; break
        scaffold = ["\n", "# Tasks\n", "\n", "----------\n"]
        file_lines[insert_pos:insert_pos] = scaffold
        start_idx = insert_pos + 1
        end_idx = insert_pos + 3

    # --- 3. 提取现有内容 ---
    existing_content = file_lines[start_idx + 1: end_idx]
    existing_structure_map = {}
    current_header_date = None
    header_pattern = re.compile(r'^#+\s*\[\[\s*(\d{4}-\d{2}-\d{2})\s*\]\]')
    id_pattern = re.compile(r'\^([a-zA-Z0-9]{6,})\s*$')

    for line in existing_content:
        stripped = line.strip()
        h_m = header_pattern.match(stripped)
        if h_m: current_header_date = h_m.group(1); continue
        if stripped.startswith('- ['):
            bid_m = id_pattern.search(stripped)
            if bid_m and current_header_date:
                existing_structure_map[bid_m.group(1)] = current_header_date

    # --- 4. 合并与分组 ---
    candidates = existing_content + block_lines
    blocks = []
    current_block = []
    date_pattern = re.compile(r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\||\]\])')

    def flush_block(blk_lines):
        if not blk_lines: return
        head = blk_lines[0]
        bid_m = id_pattern.search(head)
        if bid_m:
            bid = bid_m.group(1)
            final_date = "0000-00-00"
            if bid in existing_structure_map:
                final_date = existing_structure_map[bid]
            else:
                date_m = date_pattern.search(head)
                if date_m: final_date = date_m.group(1)
            blocks.append({'id': bid, 'date': final_date, 'lines': blk_lines})

    for line in candidates:
        s_line = line.strip()
        if not s_line: continue
        if s_line == '-----': continue
        if s_line == '----------': continue

        # 处理标题行：强制分块
        if s_line.startswith('#'):
            flush_block(current_block);
            current_block = [];
            continue

        # 处理任务行：增加缩进检测
        if s_line.startswith('- ['):
            # [关键修复] 计算原始缩进深度
            # 不使用 .strip() 后的 s_line，而是使用原始 line
            # 只有缩进非常浅 (小于2个空格或半个Tab) 的才视为新 Block
            # 这样可以保护缩进的子任务 (		- [ ]) 不被拆分

            # 简单计算前导空白长度 (Tab算1个字符，但在startswith逻辑下足够区分顶层)
            raw_indent_len = len(line) - len(line.lstrip())

            # 如果是顶层任务 (Indent 0 or 1 space/tab usually 0)
            # 使用更宽松的阈值：比如 < 2。
            # 注意：如果您的顶层任务也有缩进，这里需要调整。通常顶层任务是贴边的。
            is_toplevel = (raw_indent_len < 2)

            if is_toplevel:
                flush_block(current_block)
                current_block = [line]
            else:
                # 是子任务，加入当前块
                if current_block:
                    current_block.append(line)
                # 如果没有 current_block (即孤儿缩进任务)，暂且作为新块（虽然不合规范）
                else:
                    current_block = [line]
        else:
            # 纯文本或其他内容，归属当前块
            if current_block: current_block.append(line)

    flush_block(current_block)

    # --- 5. 分组与排序 ---
    unique_map = {}
    for b in blocks: unique_map[b['id']] = b
    date_groups = {}
    for b in unique_map.values():
        d = b['date']
        if d not in date_groups: date_groups[d] = []
        date_groups[d].append(b)

    # [SORTING] 执行绝对排序
    for date_key, group_blocks in date_groups.items():
        group_blocks.sort(key=_calculate_sort_key)

    # --- 6. 构建输出 ---
    output_lines = []
    sorted_dates = sorted(date_groups.keys(), reverse=True)
    for d in sorted_dates:
        group_blocks = date_groups[d]
        if d and d != "0000-00-00":
            if output_lines: output_lines.append("\n")
            output_lines.append(f"## [[{d}]]\n")
            output_lines.append("\n")
        elif output_lines:
            output_lines.append("\n")
        for b in group_blocks:
            output_lines.extend(b['lines'])
            if output_lines and not output_lines[-1].endswith('\n'):
                output_lines[-1] += '\n'

    section_body = ["\n"] + output_lines + ["\n"]

    # --- [FIX] 移除内部判断，总是应用变更到 list ---
    file_lines[start_idx + 1: end_idx] = section_body
    return file_lines

def aggressive_daily_clean(lines: list) -> list:
    if not lines: return []

    footer_idx = len(lines)
    for i, line in enumerate(lines):
        if line.strip().startswith('# Day planner') or line.strip().startswith('# Journey'):
            footer_idx = i
            break

    body = lines[:footer_idx]
    foot = lines[footer_idx:]

    cleaned_body = []
    empty_count = 0
    empty_pattern = re.compile(r'^\s*$')

    for i, line in enumerate(body):
        is_empty = bool(empty_pattern.fullmatch(line))
        if '---' in line: is_empty = False

        if is_empty:
            empty_count += 1
            if empty_count > 2:
                Logger.debug(f"[CLEAN] Removing excess daily line {i + 1}: {repr(line)}")
                continue
            else:
                cleaned_body.append(line)
        else:
            empty_count = 0
            cleaned_body.append(line)

    return cleaned_body + foot

def format_line(indent, status, text, dates, fname, bid, is_daily):
    # indent now represents visual depth (spaces)
    # We can simply output spaces, or convert to tabs if preferred.
    # Assuming we stick to spaces or mix based on indent // 4.
    # For robustness, we will just use indent spaces.
    # But original logic was: tab_count = indent // 4; indent_str = '\t' * tab_count
    # To maintain compatibility with visual depth:
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
        clean_text = clean_task_text(text, bid, fname)
        creation_date = None
        if dates and re.match(r'^\d{4}-\d{2}-\d{2}$', str(dates).strip()):
            creation_date = str(dates).strip()
        if not creation_date:
            patterns = [
                r'\[\[(\d{4}-\d{2}-\d{2})\]\]',
                r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\|)',
                r'(?:📅|\|📅\]\])\s*(\d{4}-\d{2}-\d{2})'
            ]
            for p in patterns:
                m = re.search(p, str(dates)) or re.search(p, text)
                if m: creation_date = m.group(1); break
        if not creation_date:
            today = datetime.date.today().strftime('%Y-%m-%d')
            if dates:
                Logger.info(f"⚠️ [FORMAT WARNING] 日期解析失败！输入: '{dates}' -> 兜底: '{today}'")
            creation_date = today

        date_link = f"[[{creation_date}#^{bid}|⮐]]"
        processed_dates = []
        done_date_match = re.search(r'✅\s*(\d{4}-\d{2}-\d{2})', str(dates))
        if done_date_match: processed_dates.append(f"✅ {done_date_match.group(1)}")
        meta_str = " ".join(processed_dates)

        parts = [date_link]
        if clean_text: parts.append(clean_text)
        if meta_str: parts.append(meta_str)
        parts.append(f"^{bid}")

        return f"{indent_str}- [{status}] {' '.join(parts)}\n"

def normalize_child_lines(raw_lines, target_parent_indent, source_parent_indent=None, as_quoted=False):
    """
    [v14.0 Relative Anchor Normalization]
    使用相对偏移量重构子行，完美保留复杂列表结构（图片、引用、多级列表）。

    Args:
        raw_lines: 子行列表 (不包含父行)
        target_parent_indent: 父行在目标文件中的缩进 (int, visual depth)
        source_parent_indent: 父行在源文件中的原始缩进 (int, visual depth)
    """
    if not raw_lines: return []

    # 如果未提供源缩进，尝试从第一行反推（兜底策略）
    if source_parent_indent is None:
        if raw_lines:
            source_parent_indent = max(0, get_indent_depth(raw_lines[0]) - 4)
        else:
            source_parent_indent = 0

    children = []
    for line in raw_lines:
        content_cleaned = re.sub(r'^[>\s]+', '', line).strip()
        if not content_cleaned:
            children.append(("> \n" if as_quoted else "\n"))
            continue

        # 1. 计算当前行相对于“原父级”的偏移量
        current_depth = get_indent_depth(line)
        delta = max(0, current_depth - source_parent_indent)

        # 2. 计算目标缩进
        target_depth = target_parent_indent + delta

        # 3. 转换为缩进字符串 (使用空格更安全，或按需转 Tab)
        # 这里统一使用 Space 确保层级准确，后续 format_line 若用 Tab 可能需要转换，
        # 但通常子内容可以保持 Space。如果必须 Tab，可以用 '\t' * (target_depth // 4)
        indent_str = ' ' * target_depth

        final = f"{indent_str}{content_cleaned}"
        if as_quoted: final = f"> {final}"
        children.append(final + "\n")

    return children

def reconstruct_daily_block(sd, target_date):
    fname = sd['fname']
    bid = sd['bid']
    status = sd['status']
    text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}\]\]', '', sd['pure']).strip()
    link_tag = f"[[{fname}]]"
    if link_tag not in text: text = f"{link_tag} {text}"

    # 传递 sd['indent'] 作为 source_parent_indent
    parent_line = format_line(sd['indent'], status, text, "", fname, bid, True)
    children = normalize_child_lines(
        sd['raw'][1:],
        target_parent_indent=sd['indent'],
        source_parent_indent=sd['indent'],
        as_quoted=False
    )
    return [parent_line] + children

def ensure_structure(lines):
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
            lines.insert(0, "# Day planner\n\n");
            lines.append("\n# Journey\n")
    if has_dp and j_idx == -1: lines.append("\n# Journey\n")
    return lines

def cleanup_empty_headers(lines, date_tag):
    lines = ensure_structure(lines)
    cleaned_lines = []
    i = 0
    modified = False
    current_section = None
    target_sections = ['# Day planner', '# Journey']
    while i < len(lines):
        line = lines[i]
        s_line = line.strip()
        if s_line.startswith('# '):
            current_section = s_line;
            cleaned_lines.append(line);
            i += 1;
            continue
        if current_section not in target_sections:
            cleaned_lines.append(line);
            i += 1;
            continue
        if s_line.startswith('## '):
            has_content = False
            j = i + 1
            while j < len(lines):
                next_s = lines[j].strip()
                if next_s.startswith('# ') or next_s.startswith('## ') or next_s == '----------': break
                if next_s: has_content = True; break
                j += 1
            if not has_content:
                modified = True;
                i = j
            else:
                cleaned_lines.append(line);
                i += 1
        else:
            cleaned_lines.append(line);
            i += 1
    return cleaned_lines, modified

```

---
## File: src\external\__init__.py
```py
# External sync modules

```

---
## File: src\external\apple_sync_adapter.py
```py
"""
Apple Sync Adapter for Antigravity Architecture.

This module wraps the TaskSynctoreminder logic as a downstream plugin for Dailynotes.
Apple Calendar sync only triggers when files are clean and stable.
"""
import os
import sys
import datetime

# Ensure paths are set up correctly
sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from dailynotes.utils import Logger


class AppleSyncAdapter:
    """
    Adapter that wraps Apple Calendar sync functionality.
    
    Features:
    - Lazy initialization (only loads AppleScript dependencies on first use)
    - Graceful degradation on non-macOS systems
    - Platform-safe imports
    """
    
    def __init__(self):
        self.enabled = False
        self._initialized = False
        self.sm = None
        
        # Defer initialization until first use (lazy loading)
        self._try_initialize()
    
    def _try_initialize(self):
        """
        Attempt to initialize Apple Calendar sync.
        This will gracefully fail on non-macOS systems.
        """
        if self._initialized:
            return
        
        self._initialized = True
        
        # Check if we're on macOS
        if sys.platform != 'darwin':
            Logger.info("🍏 Apple Sync: 非 macOS 系统，外部同步已禁用")
            return
        
        try:
            # Try to import the core modules
            from .task_sync_core.calendar_service import check_calendars_exist_simple
            from .task_sync_core.apple_state_manager import StateManager as AppleStateManager
            
            if check_calendars_exist_simple():
                self.enabled = True
                self.sm = AppleStateManager(Config.APPLE_SYNC_STATE_FILE)
                Logger.info("🍏 Apple Calendar Sync 模块已加载")
            else:
                Logger.error_once("apple_cal_check", "❌ 无法连接 Apple Calendar，外部同步已禁用")
        except ImportError as e:
            Logger.error_once("apple_import_fail", f"❌ Apple Sync 模块导入失败: {e}")
        except Exception as e:
            Logger.error_once("apple_init_fail", f"❌ Apple Sync 初始化失败: {e}")
    
    def sync_day(self, date_str: str):
        """
        Execute single-day sync to Apple Calendar.
        
        Note: This function is relatively slow due to AppleScript calls.
        Do not call frequently.
        
        Args:
            date_str: Date string in YYYY-MM-DD format        """
        if not self.enabled:
            return False, False
        
        try:
            target_dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{date_str}.md")
            
            if not os.path.exists(daily_path):
                return
            
            # Import and call the core sync logic
            from .task_sync_core.sync_engine import perform_bidirectional_sync
            
            # Call the original TaskSynctoreminder sync logic
            return perform_bidirectional_sync(date_str, daily_path, self.sm, target_dt)
            
        except Exception as e:
            Logger.error_once(f"apple_sync_err_{date_str}", f"Apple Sync Error: {e}")
            return False, False
    
    def is_available(self) -> bool:
        """Check if Apple Sync is available and initialized."""
        return self.enabled

```

---
## File: src\external\task_sync_core\__init__.py
```py
# TaskSynctoreminder core modules

```

---
## File: src\external\task_sync_core\apple_state_manager.py
```py
"""
Apple Sync State Manager - Manages sync state for Apple Calendar integration.
Renamed from state_manager.py to avoid conflict with Dailynotes StateManager.
"""
import os
import json
from datetime import datetime


class StateManager:
    """Manages bidirectional sync state between Obsidian and Apple Calendar."""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.data = self.load()

    def load(self):
        """Load state from file."""
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save(self):
        """Save state to file."""
        temp_path = self.filepath + ".tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.filepath)
        except IOError:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def get_snapshot(self, date_str):
        """Get the last known state snapshot for a date."""
        if date_str not in self.data:
            return {}, {}
        entry = self.data[date_str]
        return entry.get("obsidian", {}), entry.get("calendar", {})

    def update_snapshot(self, date_str, obs_state, cal_state):
        """Update the state snapshot for a date."""
        clean_obs = {}
        for k, v in obs_state.items():
            clean_obs[k] = {
                'name': v['name'],
                'start_time': v['start_time'],
                'end_time': v['end_time'],
                'target_calendar': v['target_calendar'],
                'tag': v.get('tag', ''),
                'status': v.get('status', ' ')
            }
        clean_cal = {}
        for k, v in cal_state.items():
            clean_cal[k] = {
                'name': v['name'],
                'id': v['id'],
                'current_calendar': v['current_calendar'],
                'duration': v['duration'],
                'start_time': v.get('start_time', ''),
                'is_completed': v.get('is_completed', False)
            }
        self.data[date_str] = {
            "obsidian": clean_obs,
            "calendar": clean_cal,
            "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.save()

```

---
## File: src\external\task_sync_core\calendar_service.py
```py
"""
Apple Calendar Service - Adapted for unified config.
"""
from datetime import datetime, timedelta
from config import Config
from .utils import escape_as_text, run_applescript

# Use config values
ALL_MANAGED_CALENDARS = Config.ALL_MANAGED_CALENDARS
DELIMITER_FIELD = Config.DELIMITER_FIELD
DELIMITER_ROW = Config.DELIMITER_ROW
ALARM_RULES = Config.ALARM_RULES


def check_calendars_exist_simple():
    """Check if all required calendars exist in Apple Calendar."""
    cal_list_str = "{" + ", ".join([f'"{escape_as_text(c)}"' for c in ALL_MANAGED_CALENDARS]) + "}"
    script = f'''
    set neededCalendars to {cal_list_str}
    set missingCalendars to {{}}
    tell application "Calendar"
        repeat with calName in neededCalendars
            if not (exists calendar calName) then
                set end of missingCalendars to calName
            end if
        end repeat
    end tell
    return missingCalendars
    '''
    result = run_applescript(script)
    if result and "{" not in result:
        missing = result.replace(", ", ",").split(",")
        if len(missing) > 0 and missing[0] != "":
            print(f"❌ 错误：找不到日历：{missing}")
            return False
    return True


def get_all_calendars_state(target_dt):
    """
    Get all calendar events for a specific date.
    
    Args:
        target_dt: datetime object for target date
    
    Returns:
        dict: Calendar events keyed by "name_starttime"
    """
    cal_list_str = "{" + ", ".join([f'"{escape_as_text(c)}"' for c in ALL_MANAGED_CALENDARS]) + "}"

    # Construct date parameters for AppleScript
    y = target_dt.year
    m = target_dt.month
    d = target_dt.day

    script = f'''
    set event_data to ""
    set targetCalendars to {cal_list_str}

    -- [精准日期构建]
    set targetDate to current date
    set year of targetDate to {y}
    set month of targetDate to {m}
    set day of targetDate to {d}
    set time of targetDate to 0 -- 00:00:00

    set dayStart to targetDate
    set dayEnd to dayStart + (1 * days)

    tell application "Calendar"
        repeat with calName in targetCalendars
            if exists calendar calName then
                tell calendar calName
                    set all_events to (every event whose start date ≥ dayStart and start date < dayEnd)
                    repeat with e in all_events
                        try
                            set e_name to summary of e
                            set e_date to start date of e
                            set e_id to uid of e
                            set e_end to end date of e
                            set durationSeconds to (e_end - e_date)
                            set durationMins to (durationSeconds / 60) as integer

                            set h to (hours of e_date)
                            set m to (minutes of e_date)
                            set h_str to h as string
                            if h < 10 then set h_str to "0" & h_str
                            set m_str to m as string
                            if m < 10 then set m_str to "0" & m_str
                            set time_key to h_str & ":" & m_str

                            set event_data to event_data & e_name & "{DELIMITER_FIELD}" & time_key & "{DELIMITER_FIELD}" & e_id & "{DELIMITER_FIELD}" & calName & "{DELIMITER_FIELD}" & durationMins & "{DELIMITER_ROW}"
                        end try
                    end repeat
                end tell
            end if
        end repeat
    end tell
    return event_data
    '''
    output = run_applescript(script)
    calendar_events = {}
    if output is None:
        return calendar_events

    for entry in output.strip().split(DELIMITER_ROW):
        if not entry:
            continue
        try:
            parts = entry.split(DELIMITER_FIELD)
            if len(parts) < 5:
                continue
            raw_name, time_str, e_id, cal_name, duration_mins = parts

            is_completed = False
            clean_name = raw_name.strip()
            if clean_name.startswith("✅"):
                is_completed = True
                clean_name = clean_name.replace("✅", "", 1).strip()
            elif clean_name.startswith("✓"):
                is_completed = True
                clean_name = clean_name.replace("✓", "", 1).strip()

            key = f"{clean_name}_{time_str}"

            calendar_events[key] = {
                'name': clean_name,
                'id': e_id,
                'current_calendar': cal_name.strip(),
                'duration': int(duration_mins),
                'start_time': time_str,
                'is_completed': is_completed,
                'raw_name': raw_name.strip()
            }
        except:
            continue
    return calendar_events


class BatchExecutor:
    """Batch executor for Apple Calendar operations."""
    
    def __init__(self, target_dt):
        self.target_dt = target_dt
        self.creates = []
        self.updates = []
        self.deletes = []

    def add_create(self, name, start_time, duration, calendar_name, is_completed):
        clean_name = name.replace("✅", "").replace("✓", "").strip()
        final_title = f"✅ {clean_name}" if is_completed else clean_name
        alarm = ALARM_RULES.get(calendar_name, 0)

        self.creates.append({
            "title": escape_as_text(final_title),
            "start": start_time,
            "dur": duration,
            "cal": escape_as_text(calendar_name),
            "alarm": alarm
        })

    def add_update(self, event_id, calendar_name, new_name, start_time, duration, is_completed):
        clean_name = new_name.replace("✅", "").replace("✓", "").strip()
        final_title = f"✅ {clean_name}" if is_completed else clean_name

        self.updates.append({
            "id": escape_as_text(event_id),
            "title": escape_as_text(final_title),
            "start": start_time,
            "dur": duration,
            "cal": escape_as_text(calendar_name)
        })

    def add_delete(self, event_id, calendar_name):
        self.deletes.append({
            "id": escape_as_text(event_id),
            "cal": escape_as_text(calendar_name)
        })

    def execute(self):
        if not (self.creates or self.updates or self.deletes):
            return

        y, m, d = self.target_dt.year, self.target_dt.month, self.target_dt.day

        script = f'''
        -- 基础日期
        set targetBaseDate to current date
        set year of targetBaseDate to {y}
        set month of targetBaseDate to {m}
        set day of targetBaseDate to {d}
        set time of targetBaseDate to 0
        
        tell application "Calendar"
        '''

        # 1. Deletes
        for op in self.deletes:
            script += f'''
            try
                tell calendar "{op['cal']}" to delete (first event whose uid is "{op['id']}")
            end try
            '''

        # 2. Creates
        for op in self.creates:
            h = int(op['start'][:2])
            mn = int(op['start'][3:])
            script += f'''
            try
                tell calendar "{op['cal']}"
                    set sDate to targetBaseDate
                    set hours of sDate to {h}
                    set minutes of sDate to {mn}
                    set eDate to sDate + ({op['dur']} * minutes)

                    set newE to make new event with properties {{summary:"{op['title']}", start date:sDate, end date:eDate}}
                    tell newE
                        make new sound alarm with properties {{trigger interval:{op['alarm']}}}
                    end tell
                end tell
            end try
            '''

        # 3. Updates
        for op in self.updates:
            h = int(op['start'][:2])
            mn = int(op['start'][3:])
            script += f'''
            try
                tell calendar "{op['cal']}"
                    set targetEvent to (first event whose uid is "{op['id']}")
                    set summary of targetEvent to "{op['title']}"

                    set sDate to targetBaseDate
                    set hours of sDate to {h}
                    set minutes of sDate to {mn}
                    set eDate to sDate + ({op['dur']} * minutes)

                    set start date of targetEvent to sDate
                    set end date of targetEvent to eDate
                end tell
            end try
            '''

        script += "\nend tell"
        print(f"⚡ 执行批处理: +{len(self.creates)} ~{len(self.updates)} -{len(self.deletes)}")
        run_applescript(script)

```

---
## File: src\external\task_sync_core\obsidian_service.py
```py
"""
Obsidian Service - Adapted for unified config.
Parses Obsidian daily notes for task extraction.
"""
import os
import re
import shutil
from config import Config

# Use config values
TAG_MAPPINGS = Config.TAG_MAPPINGS
DEFAULT_CALENDAR = Config.REMINDERS_LIST_NAME


def create_note_from_template(target_path, template_path):
    """Create a new note from template."""
    if template_path and os.path.exists(template_path):
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(template_path, target_path)
            print(f"📄 已通过模板创建日志: {os.path.basename(target_path)}")
            return True
        except Exception:
            return False
    else:
        return False


def parse_obsidian_line(line, line_index):
    """
    Parse a single line from Obsidian for task information.
    
    Returns:
        tuple: (key, data_dict) or None if not a valid task line
    """
    # Pre-check
    if not re.search(r"^\s*- \[[ xX]\]", line):
        return None

    # Flexible regex to match task format
    pattern = re.compile(r"^\s*- \[(.)\]\s+(?:(\d{1,2}:\d{2})(?:\s*-\s*(\d{1,2}:\d{2}))?\s+)?(.*)")
    match = pattern.match(line)
    if not match:
        return None

    status, start_time, end_time, raw_text = match.groups()

    # Normalize time format
    if not start_time:
        start_time = "00:00"
    else:
        start_time = start_time.zfill(5)  # "9:00" -> "09:00"

    if end_time:
        end_time = end_time.zfill(5)

    target_calendar = DEFAULT_CALENDAR
    clean_name = raw_text.strip()
    found_tag = ""

    for mapping in TAG_MAPPINGS:
        tag = mapping["tag"]
        if tag in clean_name:
            target_calendar = mapping["calendar"]
            clean_name = clean_name.replace(tag, "", 1).strip()
            clean_name = re.sub(r'\s+', ' ', clean_name).strip()
            found_tag = tag
            break

    key = f"{clean_name}_{start_time}"
    return key, {
        'name': clean_name,
        'start_time': start_time,
        'end_time': end_time,
        'target_calendar': target_calendar,
        'tag': found_tag,
        'line_index': line_index,
        'raw_text': raw_text.strip(),
        'status': status.lower()
    }


def get_obsidian_state(file_path):
    """
    Get the current state of tasks from an Obsidian file.
    
    Strategy:
    1. Read: Scan entire file for time-blocked tasks
    2. Write Anchor: Find '# Day planner' header for insertion point
    
    Returns:
        tuple: (tasks, lines, mod_time, insertion_index)
    """
    tasks = {}
    if not os.path.exists(file_path):
        return tasks, [], 0, -1

    mod_time = os.path.getmtime(file_path)
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # --- 1. Locate write region (Anchor) ---
    header_line_index = -1
    section_end_index = len(lines)

    # Find Day planner header
    for i, line in enumerate(lines):
        clean_line = line.strip().lower().replace(" ", "")
        if line.strip().startswith("#") and "#dayplanner" in clean_line:
            header_line_index = i
            break

    # If header found, find section end (next header)
    if header_line_index != -1:
        for i in range(header_line_index + 1, len(lines)):
            if lines[i].strip().startswith("#"):
                section_end_index = i
                break
        insertion_index = section_end_index
    else:
        # If no header found, default to end of file
        insertion_index = len(lines)

    # --- 2. Global task scan ---
    for i, line in enumerate(lines):
        result = parse_obsidian_line(line, i)
        if result:
            key, data = result
            tasks[key] = data

    return tasks, lines, mod_time, insertion_index

```

---
## File: src\external\task_sync_core\sync_engine.py
```py
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

```

---
## File: src\external\task_sync_core\utils.py
```py
"""
TaskSynctoreminder utilities adapted for unified config.
"""
import subprocess
from datetime import datetime, timedelta


def escape_as_text(text):
    """Escape text for AppleScript."""
    if not text:
        return ""
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')


def run_applescript(script):
    """Execute AppleScript and return output."""
    try:
        process = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True
        )
        return process.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def calculate_duration_minutes(start_str, end_str):
    """Calculate duration in minutes between two time strings."""
    if not end_str:
        return 30
    try:
        t1 = datetime.strptime(start_str, "%H:%M")
        t2 = datetime.strptime(end_str, "%H:%M")
        if t2 < t1:
            t2 += timedelta(days=1)
        return int((t2 - t1).total_seconds() / 60)
    except ValueError:
        return 30

```

---
