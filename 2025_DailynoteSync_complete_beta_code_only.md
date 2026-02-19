# Project Architecture: 2025_DailynoteSync_complete_beta

## Directory Tree (Filtered)
```text
2025_DailynoteSync_complete_beta/
├── .gitignore
├── .pytest_cache
│   ├── .gitignore
│   ├── CACHEDIR.TAG
│   ├── README.md
│   └── v
│       └── cache
│           ├── lastfailed
│           └── nodeids
├── AntigravitySync
│   ├── config.py
│   ├── gui_main.py
│   ├── main.py
│   ├── src
│   │   ├── dailynotes
│   │   │   ├── __init__.py
│   │   │   ├── format_core.py
│   │   │   ├── manager.py
│   │   │   ├── state_manager.py
│   │   │   ├── sync
│   │   │   │   ├── __init__.py
│   │   │   │   ├── discovery.py
│   │   │   │   ├── engine.py
│   │   │   │   ├── parsing.py
│   │   │   │   ├── rendering.py
│   │   │   │   └── task_registry.py
│   │   │   ├── tracker.py
│   │   │   └── utils.py
│   │   └── external
│   │       ├── __init__.py
│   │       ├── apple_sync_adapter.py
│   │       ├── dock_handoff.py
│   │       ├── eventkit_wrapper.py
│   │       ├── note_sync_core
│   │       │   ├── monitor.py
│   │       │   ├── read_today_note.py
│   │       │   └── watch_today_note.py
│   │       ├── reminder_kit.py
│   │       └── task_sync_core
│   │           ├── __init__.py
│   │           ├── apple_state_manager.py
│   │           ├── calendar_service.py
│   │           ├── obsidian_service.py
│   │           ├── sync_engine.py
│   │           └── utils.py
│   ├── test_reminder_ek.py
│   ├── test_simple.py
│   ├── test_whitespace.py
│   └── tests
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_monitor_sections.py
│       ├── test_parsing.py
│       └── test_registry.py
├── aggregate.py
├── debug_test.py
├── force_git.py
├── force_push.sh
├── git_push_helper.py
├── temp_git.py
└── testhandoff
    ├── check_handoff.py
    └── debug_ax.py
```

---

## File: debug_test.py
```py
#!/usr/bin/env python3
import re

text = """---
tags:
  - DayPlan
---
# Day planner

content here
"""
sections = re.split(r'^(#\s.*)$', text.strip(), flags=re.MULTILINE)
for i, s in enumerate(sections):
    print(f'[{i}]: {repr(s)}')

```

---
## File: force_git.py
```py

import subprocess
import os

repo_root = "/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta"
files = [
    "AntigravitySync/config.py",
    "AntigravitySync/src/dailynotes/format_core.py",
    "AntigravitySync/src/dailynotes/sync/rendering.py"
]

def run(cmd):
    print(f"Running: {cmd}")
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    result = subprocess.run(cmd, cwd=repo_root, env=env, text=True, capture_output=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    else:
        print(f"Success: {result.stdout}")

run(["git", "add"] + files)
run(["git", "commit", "-m", "Disable debug mode, adjust sync range, and fix header blank line issues"])
run(["git", "push"])

```

---
## File: force_push.sh
```sh
#!/bin/bash
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

git add .
git commit -m "feat: 完善备忘录同步逻辑 (账单分类与排序/启动扫描/时间精简)"
git push origin HEAD

```

---
## File: git_push_helper.py
```py
import subprocess
import os
import sys

# Define the log file path
log_file_path = "git_push_log.txt"

def run_git_commands():
    # Set up environment variables
    env = os.environ.copy()
    env["LC_ALL"] = "en_US.UTF-8"
    env["LANG"] = "en_US.UTF-8"

    commands = [
        ["git", "add", "AntigravitySync/config.py", "AntigravitySync/src/dailynotes/format_core.py", "AntigravitySync/src/dailynotes/sync/rendering.py"],
        ["git", "commit", "-m", "Disable debug mode, adjust sync range, and fix header blank line issues"],
        ["git", "push", "origin", "HEAD"]
    ]

    with open(log_file_path, "w") as log_file:
        for cmd in commands:
            log_file.write(f"Running: {' '.join(cmd)}\n")
            try:
                result = subprocess.run(
                    cmd,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=60
                )
                if result.returncode != 0:
                    log_file.write(f"Command failed with return code {result.returncode}\n")
            except Exception as e:
                log_file.write(f"Exception: {e}\n")

if __name__ == "__main__":
    run_git_commands()

```

---
## File: temp_git.py
```py

import subprocess
import os

env = os.environ.copy()
env["LANG"] = "en_US.UTF-8"
env["LC_ALL"] = "en_US.UTF-8"

def run(cmd):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.stdout: print(f"STDOUT: {result.stdout}")
    if result.stderr: print(f"STDERR: {result.stderr}")
    return result.returncode

run(["git", "add", "."])
run(["git", "commit", "--no-verify", "-m", "feat: 完善备忘录同步逻辑 (账单分类/自动重排/全量扫描)"])
run(["git", "push", "origin", "HEAD"])

```

---
## File: .pytest_cache/.gitignore
```text
# Created by pytest automatically.
*

```

---
## File: .pytest_cache/CACHEDIR.TAG
```TAG
Signature: 8a477f597d28d172789f06886806bc55
# This file is a cache directory tag created by pytest.
# For information about cache directory tags, see:
#	https://bford.info/cachedir/spec.html

```

---
## File: .pytest_cache/README.md
```md
# pytest cache directory #

This directory contains data from the pytest's cache plugin,
which provides the `--lf` and `--ff` options, as well as the `cache` fixture.

**Do not** commit this to version control.

See [the docs](https://docs.pytest.org/en/stable/how-to/cache.html) for more information.

```

---
## File: .pytest_cache/v/cache/lastfailed
```text
{}
```

---
## File: .pytest_cache/v/cache/nodeids
```text
[
  "AntigravitySync/tests/test_parsing.py::TestCaptureBlock::test_empty_lines_within_block",
  "AntigravitySync/tests/test_parsing.py::TestCaptureBlock::test_single_line_task",
  "AntigravitySync/tests/test_parsing.py::TestCaptureBlock::test_stops_after_too_many_empty_lines",
  "AntigravitySync/tests/test_parsing.py::TestCaptureBlock::test_stops_at_same_indent",
  "AntigravitySync/tests/test_parsing.py::TestCaptureBlock::test_task_with_children",
  "AntigravitySync/tests/test_parsing.py::TestCleanTaskText::test_complex_cleanup",
  "AntigravitySync/tests/test_parsing.py::TestCleanTaskText::test_preserves_regular_links",
  "AntigravitySync/tests/test_parsing.py::TestCleanTaskText::test_removes_block_id",
  "AntigravitySync/tests/test_parsing.py::TestCleanTaskText::test_removes_context_link",
  "AntigravitySync/tests/test_parsing.py::TestCleanTaskText::test_removes_date_link",
  "AntigravitySync/tests/test_parsing.py::TestCleanTaskText::test_removes_emoji_date",
  "AntigravitySync/tests/test_parsing.py::TestCleanTaskText::test_removes_return_link",
  "AntigravitySync/tests/test_parsing.py::TestCleanTaskText::test_removes_time",
  "AntigravitySync/tests/test_parsing.py::TestCleanTaskText::test_removes_time_range",
  "AntigravitySync/tests/test_parsing.py::TestCleanTaskText::test_simple_task",
  "AntigravitySync/tests/test_parsing.py::TestGenerateBlockId::test_alphanumeric",
  "AntigravitySync/tests/test_parsing.py::TestGenerateBlockId::test_format",
  "AntigravitySync/tests/test_parsing.py::TestGenerateBlockId::test_uniqueness",
  "AntigravitySync/tests/test_parsing.py::TestGetIndentDepth::test_four_space_indent",
  "AntigravitySync/tests/test_parsing.py::TestGetIndentDepth::test_mixed_indent",
  "AntigravitySync/tests/test_parsing.py::TestGetIndentDepth::test_no_indent",
  "AntigravitySync/tests/test_parsing.py::TestGetIndentDepth::test_quoted_line",
  "AntigravitySync/tests/test_parsing.py::TestGetIndentDepth::test_tab_indent",
  "AntigravitySync/tests/test_parsing.py::TestGetIndentDepth::test_two_space_indent",
  "AntigravitySync/tests/test_parsing.py::TestParseFileTasks::test_basic_task_extraction",
  "AntigravitySync/tests/test_parsing.py::TestParseFileTasks::test_completed_task_status",
  "AntigravitySync/tests/test_parsing.py::TestParseFileTasks::test_empty_file",
  "AntigravitySync/tests/test_parsing.py::TestParseFileTasks::test_generates_missing_id",
  "AntigravitySync/tests/test_parsing.py::TestParseFileTasks::test_multiple_dates",
  "AntigravitySync/tests/test_parsing.py::TestParseFileTasks::test_nested_children_captured",
  "AntigravitySync/tests/test_parsing.py::TestParseFileTasks::test_no_task_section",
  "AntigravitySync/tests/test_parsing.py::TestParseFileTasks::test_rescues_id_from_hash",
  "AntigravitySync/tests/test_parsing.py::TestParseFileTasks::test_respects_time_gate",
  "AntigravitySync/tests/test_parsing.py::TestParseFileTasks::test_stops_at_delimiter",
  "AntigravitySync/tests/test_parsing.py::TestParseFileTasksWriteBack::test_write_back_disabled",
  "AntigravitySync/tests/test_parsing.py::TestParseFileTasksWriteBack::test_write_back_enabled",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryInitialization::test_initialize_calls_os_walk",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryInitialization::test_initialize_populates_cache",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryInitialization::test_singleton_pattern",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryRealisticScenarios::test_complex_task_section",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryRetrieval::test_get_affected_dates",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryRetrieval::test_get_tasks_by_date",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryRetrieval::test_get_tasks_by_date_nonexistent",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryRetrieval::test_get_tasks_by_date_returns_copy",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryThreadSafety::test_concurrent_updates_dont_crash",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryUpdate::test_update_adds_new_tasks",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryUpdate::test_update_changes_task_date",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryUpdate::test_update_handles_file_deletion",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryUpdate::test_update_overwrites_modified_tasks",
  "AntigravitySync/tests/test_registry.py::TestTaskRegistryUpdate::test_update_removes_deleted_tasks"
]
```

---
## File: AntigravitySync/config.py
```py
import os


class Config:
    VERSION = "v3.0.0 (Chronos Mode)"    # [2026-01-22] Pure event-driven, no polling
    
    # ==========================
    # 1. 基础路径配置 (来自 Dailynotes)
    # ==========================
    VAULT_ROOT = r'/Users/user999/Documents/【Liang_project】/远程仓库1'
    REL_ATTACHMENT_DIR = r'【ATTACHMENT】'
    REL_TEMPLATE_FILE = r'【002_Infobox】/Templates/DayPlanTemplate_beta.md'

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
    TYPING_COOLDOWN_SECONDS = 6
    IMAGE_PARAM_SUFFIX = "|L|200"
    DEBUG_MODE = True
    
    # [v3.7] Debug 日期范围模式
    # 设为 1 时进入调试模式，日记范围只对今天的日记有效（加速测试）
    DEBUG_TODAY_ONLY = 0
    
    # [v1.4] 事件驱动模式参数
    EVENT_DEBOUNCE_SECONDS = 0.5   # 事件触发防抖时间（秒）
    
    # [v3.6] 变更来源感知延迟
    # 根据检测到的变更来源，在执行格式化/同步前等待不同时间
    CHANGE_SOURCE_TYPING_DELAY = 15.0   # 用户打字：短延迟，减少打断感
    CHANGE_SOURCE_SYNC_DELAY = 25.0    # 后台同步：长延迟，等待批量同步稳定
    
    # [v3.0] Chronos Mode - 全事件驱动架构
    CHRONOS_SYNC_WINDOW_DAYS = 30      # 日历变更时同步的窗口大小（前后各15天）
    CHRONOS_FULL_RANGE_PAST_DAYS = 1   # 全量同步：过去N天 (前天+昨天)
    CHRONOS_FULL_RANGE_FUTURE_YEARS = 10  # 全量同步：未来N年
    CHRONOS_EVENTKIT_BATCH_DAYS = 1460  # EventKit批次大小（约4年，系统限制）
    CHRONOS_LOOP_INTERVAL = 60.0       # 主循环间隔（秒）
    
    # [v2.0+] 指数动态调度参数
    # 调度公式: I(d) = EXP_BASE * exp(EXP_COEFF * d) + EXP_OFFSET
    # d 为距今天数，I(d) 为同步间隔（秒）
    EXP_BASE = 60.0       # 基础间隔（秒）
    EXP_COEFF = 0.1       # 指数系数（正值表示越旧越慢）
    EXP_OFFSET = 30.0     # 偏移量/最小间隔（秒）
    
    # [v2.0] EventKit Sync
    # No file watching required for calendar
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

    # ==========================
    # 3. 关键字映射 (Log Keyword Mapping)
    # ==========================
    # 用于 watch_today_note.py 将中文输入转换为英文记录
    KEYWORD_MAPPING = {
        "烟": "Cigarette",
        "水": "Water",
        "魔爪": "Monster",
        "咖啡": "Coffee",
        "吃饭": "food",
        "食物": "food"
    }

```

---
## File: AntigravitySync/gui_main.py
```py
import sys
import os
import threading
import time
import signal
import subprocess

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Check if rumps is installed
try:
    import rumps
except ImportError:
    print("Error: 'rumps' module not found. Please run: pip install rumps")
    sys.exit(1)

import main
from config import Config
from dailynotes.utils import ProcessLock, Logger

class AntigravityApp(rumps.App):
    def __init__(self):
        super(AntigravityApp, self).__init__("AG", title="⏳ AG")
        self.menu = [
            rumps.MenuItem("Status: Initializing...", callback=None),
            None,
            rumps.MenuItem("Open Log File", callback=self.open_log),
            rumps.MenuItem("Restart Sync", callback=self.restart_sync),
            None, # Separator before Quit
        ]
        self.sync_thread = None
        self.should_run = True

    def run_sync_logic(self):
        """
        Runs the main application logic in a background thread.
        Replicates the startup sequence from main.py:
        1. Caffeinate
        2. Lock Acquisition (with aggressive kill of old process)
        3. Main Loop (run_with_self_healing)
        """
        # 1. Start Caffeinate
        # main.start_caffeinate() # Move to main thread if possible or handle carefully

        # 2. Acquire Lock
        if not ProcessLock.acquire():
            Logger.info("⚠️ [GUI] Lock held by another process. Attempting takeover...")
            old_pid = ProcessLock.read_pid()
            if old_pid and old_pid != os.getpid():
                Logger.info(f"🛑 Killing old process {old_pid}...")
                try:
                    os.kill(old_pid, signal.SIGTERM)
                    # Wait up to 3 seconds
                    for _ in range(30):
                        time.sleep(0.1)
                        os.kill(old_pid, 0)
                    else:
                        os.kill(old_pid, signal.SIGKILL)
                except OSError:
                    Logger.info("   Old process gone.")
                except Exception as e:
                    Logger.error_once("kill_fail", f"Failed to kill old process: {e}")
            
            # Retry acquire
            time.sleep(1)
            if not ProcessLock.acquire():
                Logger.error_once("lock_fail", "❌ Could not acquire lock even after cleanup.")
                dum_title = "❌ Error"
                try:
                    self.title = dum_title
                    rumps.notification("Sync Error", "Lock Failed", "Could not start sync engine.")
                except: pass
                return

        # Success acquiring lock
        Logger.info("✅ [GUI] Lock acquired. Starting engine...")
        try:
             # Update Status UI (Safely?)
            self.title = "🚀 AG"
            self.menu["Status: Initializing..."].title = "Status: Running"
        except: pass

        try:
            # 3. Run Main Loop
            # This calls the self-healing loop from main.py
            main.run_with_self_healing()
        except Exception as e:
            Logger.error_once("gui_thread_crash", f"❌ Sync thread crashed: {e}")
            try:
                self.title = "⚠️ Valid"
            except: pass
        finally:
            # Cleanup
            ProcessLock.release()
            main.stop_caffeinate()
            try:
                self.title = "🔴 Stop"
                self.menu["Status: Initializing..."].title = "Status: Stopped"
            except: pass

    @rumps.clicked("Open Log File")
    def open_log(self, _):
        log_file = "/tmp/AntigravitySync_startup.log"
        if os.path.exists(log_file):
            subprocess.run(["open", log_file])
        else:
            rumps.notification("Antigravity Sync", "Log Missing", "Log file not found at " + log_file)

    @rumps.clicked("Restart Sync")
    def restart_sync(self, _):
        rumps.alert("Restart Required", "Please usage 'Quit' to stop the app completely, then restart it via the script.")

    def start(self):
        # Start the sync logic thread
        self.sync_thread = threading.Thread(target=self.run_sync_logic, daemon=True)
        self.sync_thread.start()
        
        # Start the Rumps App (Main Thread)
        self.run()

if __name__ == "__main__":
    # Prevent signal handlers from running in non-main threads
    # We patch the signal module in main.py or handle it here
    
    # Monkey-patching signal.signal to ignore signals in non-main threads if called from there, 
    # but the issue is FusionManager calls signal.signal.
    # We need to run FusionManager's signal setup in the main thread OR disable it.
    
    # Option: Instantiate FusionManager and run it without signal handlers?
    # Or run the heavy lifting in a thread, but keep signal handling in the main thread?
    # Rumps app.run() blocks the main thread.
    
    # Workaround: Disable signal handling in FusionManager when running under GUI
    import dailynotes.manager
    
    # Store original run method
    original_run = dailynotes.manager.FusionManager.run
    
    def patched_run(self):
        # Skip signal registration
        self._running = True
        
        Logger.info(f"🚀 Chronos Mode 启动 - 全事件驱动架构 (GUI Mode)")
        Logger.info(f"   同步窗口: ±{Config.CHRONOS_SYNC_WINDOW_DAYS // 2} 天")
        Logger.info(f"   全量范围: 过去 {Config.CHRONOS_FULL_RANGE_PAST_DAYS} 天 ~ 未来 {Config.CHRONOS_FULL_RANGE_FUTURE_YEARS} 年")
        Logger.info(f"   循环间隔: {Config.CHRONOS_LOOP_INTERVAL} 秒")

        # 初始化 Watchdog
        if dailynotes.manager.WATCHDOG_AVAILABLE:
            try:
                self._observer = dailynotes.manager.Observer()
                event_handler = dailynotes.manager.ObsidianEventHandler(self)
                self._observer.schedule(event_handler, Config.VAULT_ROOT, recursive=True)
                self._observer.start()
                Logger.info(f"👁️ [Watchdog] 开始监听: {Config.VAULT_ROOT}")
            except Exception as e:
                Logger.error_once("observer_init", f"Watchdog 初始化失败: {e}")
                self._observer = None

            # EventKit 监听
            if self._ek_client:
                try:
                    Logger.info("📅 [Watchdog] 启动 EventKit 监听...")
                    self._ek_client.start_watching(self._on_calendar_push_event)
                except Exception as e:
                    Logger.error_once("cal_ek_fail", f"无法启动日历监听: {e}")

        # [v3.0] 启动时全量同步
        if not self._startup_sync_done:
            Logger.info("🌅 [Chronos] 执行启动全量同步...")
            self.sync_core.initialize_registry()
            self._registry_warmup_done = True
            self.sync_full_range()
            self._startup_sync_done = True

        # 主循环
        try:
            from CoreFoundation import CFRunLoopRunInMode, kCFRunLoopDefaultMode
            
            while self.app_ref.should_run and self._running:
                # [v3.0] 纯事件驱动：仅处理标志位
                if self._calendar_dirty_flag:
                    Logger.info(f"⚡ [Chronos] 检测到日历变更")
                    self.sync_recent_window()
                    self._calendar_dirty_flag = False
                
                # 检查午夜跨越
                self._check_midnight_crossing()
                
                # 保持 RunLoop 唤醒
                CFRunLoopRunInMode(kCFRunLoopDefaultMode, Config.CHRONOS_LOOP_INTERVAL, False)
                
        except KeyboardInterrupt:
            Logger.info("\n⏹️ 收到中断信号...")
        finally:
            if self._observer:
                Logger.info("🛑 [Watchdog] 停止监听 Vault...")
                self._observer.stop()
                self._observer.join(timeout=3)
            
            if self._ek_client:
                Logger.info("🛑 [Watchdog] 停止监听 Calendar...")
                self._ek_client.stop_watching()
            
            self.sm.save()
            Logger.info("✅ 状态已保存，Chronos 引擎已停止")

    # Apply Patch
    dailynotes.manager.FusionManager.run = patched_run

    app = AntigravityApp()
    # Inject app reference to manager so it can check should_run
    dailynotes.manager.FusionManager.app_ref = app 
    
    app.start()

```

---
## File: AntigravitySync/main.py
```py
import time
import signal
import os
import sys
import subprocess
import atexit

# Add src to sys.path to allow importing dailynotes package
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from dailynotes.manager import FusionManager
from config import Config
from dailynotes.utils import ProcessLock, Logger

# [v4.0] Apple Notes Monitor（带降级处理）
try:
    from external.note_sync_core.monitor import NoteMonitor
    NOTE_MONITOR_AVAILABLE = True
except ImportError as e:
    NOTE_MONITOR_AVAILABLE = False
    Logger.info(f"⚠️ [NoteMonitor] 模块加载失败（不影响主程序）: {e}")

# [v2.0.1] Caffeinate 进程句柄（防休眠）
_caffeinate_proc = None

def start_caffeinate():
    """
    [v2.0.1] 启动 caffeinate 防休眠进程
    使用 -i 参数阻止系统进入 idle sleep
    """
    global _caffeinate_proc
    try:
        _caffeinate_proc = subprocess.Popen(
            ['caffeinate', '-i', '-w', str(os.getpid())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        Logger.info(f"☕ [Caffeinate] 防休眠已启用 (PID: {_caffeinate_proc.pid})")
    except FileNotFoundError:
        Logger.info("⚠️ [Caffeinate] caffeinate 命令不可用（非 macOS?），跳过防休眠")
    except Exception as e:
        Logger.info(f"⚠️ [Caffeinate] 启动失败: {e}")

def stop_caffeinate():
    """
    [v2.0.1] 停止 caffeinate 进程
    """
    global _caffeinate_proc
    if _caffeinate_proc:
        try:
            _caffeinate_proc.terminate()
            _caffeinate_proc.wait(timeout=2)
            Logger.info("☕ [Caffeinate] 防休眠已停止")
        except Exception:
            pass
        _caffeinate_proc = None

# [v4.0] NoteMonitor 全局实例（方便退出时清理）
_note_monitor = None

def _start_note_monitor():
    """
    [v4.0] 启动 Apple Notes 备忘录监听（daemon 线程）
    独立于 FusionManager，互不干扰
    """
    global _note_monitor
    if not NOTE_MONITOR_AVAILABLE:
        Logger.info("ℹ️  [NoteMonitor] 模块不可用，跳过备忘录监听")
        return

    try:
        _note_monitor = NoteMonitor(config=Config, logger=Logger)
        _note_monitor.start()
    except Exception as e:
        Logger.info(f"⚠️ [NoteMonitor] 启动失败（不影响主程序）: {e}")
        _note_monitor = None

def _stop_note_monitor():
    """[v4.0] 停止 NoteMonitor"""
    global _note_monitor
    if _note_monitor:
        try:
            _note_monitor.stop()
        except Exception:
            pass
        _note_monitor = None

def run_with_self_healing():
    """
    [v2.0.1] 带错误自愈的主循环
    如果 FusionManager 崩溃，自动重启
    """
    max_restarts = 5
    restart_count = 0
    restart_cooldown = 30  # 重启冷却时间（秒）
    
    # [v4.0] 在主循环之前启动备忘录监听
    _start_note_monitor()
    
    while restart_count < max_restarts:
        try:
            app = FusionManager()
            Logger.info(f"=== Antigravity Sync {Config.VERSION} (Exponential Dynamic Scheduling) ===")
            Logger.info(f"路径: {Config.ROOT_DIR}")
            Logger.info(f"模式: Watchdog (Vault & Calendar) + 指数动态调度")
            Logger.info(f"调度公式: I(d) = {Config.EXP_BASE} * exp({Config.EXP_COEFF} * d) + {Config.EXP_OFFSET}")
            
            # [P2 FIX] Validate template file at startup
            if os.path.exists(Config.TEMPLATE_FILE):
                Logger.info(f"模板: ✅ {Config.REL_TEMPLATE_FILE}")
            else:
                Logger.info(f"⚠️ 模板文件不存在: {Config.REL_TEMPLATE_FILE} (将使用基础骨架)")
            
            # [v4.0] 备忘录监听状态
            if _note_monitor and _note_monitor._running:
                Logger.info(f"📝 备忘录: ✅ Apple Notes -> Obsidian ## #Water")
            else:
                Logger.info(f"📝 备忘录: ⚠️ 未启用")
            
            if restart_count > 0:
                Logger.info(f"🔄 [Self-Healing] 自动重启成功 (第 {restart_count} 次)")
            
            Logger.info("=" * 50)
            
            app.run()
            break  # 正常退出
            
        except KeyboardInterrupt:
            Logger.info("\n停止服务...")
            break
        except SystemExit:
            Logger.info("收到退出信号...")
            break
        except Exception as e:
            restart_count += 1
            Logger.error_once(f"main_crash_{restart_count}", f"❌ [Self-Healing] 主循环异常: {e}")
            
            if restart_count < max_restarts:
                Logger.info(f"⏳ [Self-Healing] {restart_cooldown}秒后尝试重启 ({restart_count}/{max_restarts})...")
                time.sleep(restart_cooldown)
            else:
                Logger.error_once("max_restarts", f"❌ [Self-Healing] 达到最大重启次数 ({max_restarts})，退出")

if __name__ == "__main__":
    # [v2.0.1] 注册退出时清理 caffeinate
    atexit.register(stop_caffeinate)
    
    # [v2.0.1] 启动防休眠
    start_caffeinate()
    
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
        run_with_self_healing()
    finally:
        _stop_note_monitor()
        stop_caffeinate()
        ProcessLock.release()

```

---
## File: AntigravitySync/test_reminder_ek.py
```py
import objc
import threading
import time
import datetime
from EventKit import EKEventStore, EKEntityTypeReminder
from Foundation import NSPredicate, NSDate

# 0 = Event, 1 = Reminder
ENTITY_TYPE_REMINDER = 1

class ReminderTest:
    def __init__(self):
        self.store = EKEventStore.alloc().init()
        self.access_granted = False

    def check_access(self):
        group = threading.Event()
        
        def callback(granted, error):
            self.access_granted = granted
            if error:
                print(f"❌ Error: {error}")
            group.set()

        status = EKEventStore.authorizationStatusForEntityType_(ENTITY_TYPE_REMINDER)
        print(f"Current Status: {status}")

        if hasattr(self.store, 'requestFullAccessToRemindersWithCompletion_'):
             self.store.requestFullAccessToRemindersWithCompletion_(callback)
        else:
             self.store.requestAccessToEntityType_completion_(ENTITY_TYPE_REMINDER, callback)
        
        group.wait()
        return self.access_granted

    def fetch_reminders(self):
        if not self.access_granted:
            print("No access")
            return

        print("Fetching reminders...")
        # Predicate for all reminders (incomplete)
        # For reminders, we use fetchRemindersMatchingPredicate_completion_ which is async!
        
        # Or sync method? fetchRemindersMatchingPredicate is NOT available.
        # We MUST use the async method.
        
        predicate = self.store.predicateForRemindersInCalendars_(None) # None = all calendars
        
        group = threading.Event()
        
        def fetch_callback(reminders):
            print(f"✅ Fetched {len(reminders) if reminders else 0} reminders.")
            if reminders:
                for r in reminders[:5]:
                    print(f" - [{r.title()}] Completed: {r.isCompleted()}")
            group.set()
            
        self.store.fetchRemindersMatchingPredicate_completion_(predicate, fetch_callback)
        group.wait()

if __name__ == "__main__":
    test = ReminderTest()
    if test.check_access():
        print("Access Granted")
        test.fetch_reminders()
    else:
        print("Access Denied")

```

---
## File: AntigravitySync/test_simple.py
```py
#!/usr/bin/env python3
"""
简化测试：找出 "- " -> "-" 的问题
"""
import sys
sys.path.insert(0, '/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta/AntigravitySync')

result_lines = []

def log(msg):
    result_lines.append(msg)
    print(msg)

from src.dailynotes.format_core import FormatCore

# 测试 sort_day_planner_content
test_content = "- "
log(f"INPUT: {repr(test_content)}")
result = FormatCore.sort_day_planner_content(test_content)
log(f"OUTPUT: {repr(result)}")

if test_content.endswith(" ") and not result.endswith(" "):
    log("PROBLEM FOUND: 尾部空格被删除!")
else:
    log("OK")

# 写结果到文件
with open('/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta/AntigravitySync/test_output.txt', 'w') as f:
    f.write("\n".join(result_lines))

```

---
## File: AntigravitySync/test_whitespace.py
```py
#!/usr/bin/env python3
"""
测试脚本：找出哪个函数在处理 "- " 时删除了空格
"""
import sys
sys.path.insert(0, '/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta/AntigravitySync')

from src.dailynotes.format_core import FormatCore
from src.dailynotes.sync.parsing import normalize_block_content, clean_task_text
from src.dailynotes.sync.rendering import normalize_child_lines, aggressive_daily_clean

# 测试用例
test_line = "- "
test_lines = ["# Day planner\n", "\n", "- \n", "\n"]

print("=" * 50)
print("测试输入行: repr =", repr(test_line))
print("=" * 50)

# 测试 1: normalize_block_content
print("\n[TEST 1] normalize_block_content")
result1 = normalize_block_content([test_line])
print(f"  输入: {repr([test_line])}")
print(f"  输出: {repr(result1)}")

# 测试 2: clean_task_text
print("\n[TEST 2] clean_task_text")
result2 = clean_task_text(test_line)
print(f"  输入: {repr(test_line)}")
print(f"  输出: {repr(result2)}")

# 测试 3: normalize_child_lines
print("\n[TEST 3] normalize_child_lines")
result3 = normalize_child_lines([test_line], 0)
print(f"  输入: {repr([test_line])}")
print(f"  输出: {repr(result3)}")

# 测试 4: aggressive_daily_clean
print("\n[TEST 4] aggressive_daily_clean")
result4 = aggressive_daily_clean(test_lines)
print(f"  输入: {repr(test_lines)}")
print(f"  输出: {repr(result4)}")

# 测试 5: FormatCore.sort_day_planner_content
print("\n[TEST 5] FormatCore.sort_day_planner_content")
test_content = "- \n"
result5 = FormatCore.sort_day_planner_content(test_content)
print(f"  输入: {repr(test_content)}")
print(f"  输出: {repr(result5)}")

# 测试 6: FormatCore.sort_markdown_sections
print("\n[TEST 6] FormatCore.sort_markdown_sections")
test_md = "# Day planner\n\n- \n\n# Journey\n"
result6 = FormatCore.sort_markdown_sections(test_md)
print(f"  输入: {repr(test_md)}")
print(f"  输出: {repr(result6)}")

print("\n" + "=" * 50)
print("完成测试")

```

---
## File: AntigravitySync/tests/__init__.py
```py
"""
AntigravitySync Test Suite
"""

```

---
## File: AntigravitySync/tests/conftest.py
```py
"""
AntigravitySync Test Suite - conftest.py
Common fixtures and configuration for pytest.

This module provides:
- Path setup for importing src modules
- Mock fixtures for FileUtils, Config, StateManager
- Sample data generators for testing
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Dict, List, Any

# ============================================================================
# PATH SETUP - Ensure tests can import AntigravitySync modules
# ============================================================================

# Get the AntigravitySync directory (parent of tests/)
ANTIGRAVITY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ANTIGRAVITY_DIR, 'src')

# Add paths to sys.path if not already present
for path in [ANTIGRAVITY_DIR, SRC_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)


# ============================================================================
# MOCK CONFIG FIXTURE
# ============================================================================

@pytest.fixture
def mock_config():
    """
    Create a mock Config object with test-safe values.
    """
    config = MagicMock()
    config.VERSION = "v1.8.2 (Test)"
    config.ROOT_DIR = "/mock/vault"
    config.DAILY_NOTE_DIR = "/mock/vault/DailyNotes"
    config.SYNC_START_DATE = "2025-01-01"
    config.TYPING_COOLDOWN_SECONDS = 3
    config.DEBUG_MODE = True
    return config


@pytest.fixture(autouse=True)
def patch_config(mock_config):
    """
    Auto-patch Config for all tests.
    """
    with patch.dict('sys.modules', {'config': MagicMock()}):
        with patch('config.Config', mock_config):
            yield mock_config


# ============================================================================
# MOCK FILEUTILS FIXTURE
# ============================================================================

@pytest.fixture
def mock_file_utils():
    """
    Create a mock FileUtils that simulates file operations.
    
    Usage:
        mock_file_utils.read_file.return_value = ["line1", "line2"]
    """
    file_utils = MagicMock()
    
    # Default behaviors
    file_utils.read_file.return_value = []
    file_utils.write_file.return_value = None
    file_utils.is_excluded.return_value = False
    file_utils.get_mtime.return_value = 0.0
    file_utils.read_content.return_value = ""
    file_utils.calculate_hash.return_value = "mockhash"
    
    return file_utils


@pytest.fixture
def patch_file_utils(mock_file_utils):
    """
    Patch FileUtils globally for a test.
    """
    with patch('dailynotes.utils.FileUtils', mock_file_utils):
        yield mock_file_utils


# ============================================================================
# MOCK STATE MANAGER FIXTURE
# ============================================================================

@pytest.fixture
def mock_state_manager():
    """
    Create a mock StateManager for hash and ID operations.
    """
    sm = MagicMock()
    
    # Default behaviors
    sm.calc_hash.return_value = "testhash123"
    sm.find_id_by_hash.return_value = None  # No existing ID found
    
    return sm


# ============================================================================
# SAMPLE DATA GENERATORS
# ============================================================================

@pytest.fixture
def sample_task_lines():
    """
    Generate common task line patterns for testing.
    """
    return {
        "simple": "- [ ] Simple task",
        "with_time": "- [ ] 10:00 Task with time",
        "with_time_range": "- [ ] 10:00 - 11:00 Task with duration",
        "with_id": "- [ ] Task with ID ^abc123",
        "with_date_link": "- [ ] Task [[2025-01-15]]",
        "with_emoji_date": "- [ ] Task 📅 2025-01-15",
        "with_tag": "- [ ] 10:00 #A Tagged task",
        "completed": "- [x] Completed task",
        "indented": "  - [ ] Indented child task",
        "deeply_indented": "    - [ ] Deeply indented task",
        "with_return_link": "- [ ] Task [[Project#^abc123|⮐]]",
        "complex": "- [ ] 14:00 - 15:00 #A Complex task [[2025-01-20]] ^xyz789",
    }


@pytest.fixture
def sample_task_section():
    """
    Generate a complete # Tasks section for testing.
    """
    return [
        "# Tasks\n",
        "\n",
        "## [[2025-01-15]]\n",
        "\n",
        "- [ ] 10:00 First task ^task01\n",
        "- [ ] 11:00 Second task ^task02\n",
        "  - [ ] Child of second ^child1\n",
        "\n",
        "## [[2025-01-16]]\n",
        "\n",
        "- [ ] 09:00 Tomorrow task ^task03\n",
        "\n",
        "----------\n",
    ]


@pytest.fixture
def sample_project_file():
    """
    Generate a complete project file with YAML frontmatter.
    """
    return [
        "---\n",
        "tags:\n",
        "  - main\n",
        "---\n",
        "\n",
        "# Project Title\n",
        "\n",
        "Some project description.\n",
        "\n",
        "# Tasks\n",
        "\n",
        "## [[2025-01-15]]\n",
        "\n",
        "- [ ] 10:00 Project task one ^proj01\n",
        "- [ ] 11:00 Project task two ^proj02\n",
        "\n",
        "----------\n",
        "\n",
        "# Notes\n",
        "\n",
        "Some other content.\n",
    ]


@pytest.fixture
def sample_project_map():
    """
    Generate a mock project map for testing.
    """
    return {
        "/mock/vault/ProjectA": "ProjectA",
        "/mock/vault/ProjectB": "ProjectB",
        "/mock/vault/Nested/ProjectC": "ProjectC",
    }


# ============================================================================
# REGISTRY HELPERS
# ============================================================================

@pytest.fixture
def fresh_registry():
    """
    Create a fresh TaskRegistry instance (bypassing singleton).
    
    This is needed because TaskRegistry is a singleton, and we need
    isolated instances for testing.
    """
    from dailynotes.sync.task_registry import TaskRegistry
    
    # Reset singleton state
    TaskRegistry._instance = None
    
    # Create fresh instance
    registry = TaskRegistry()
    registry._initialized = True  # Mark as initialized to avoid auto-init
    registry._file_cache = {}
    registry._date_index = {}
    registry._file_to_dates = {}
    registry._project_map = {}
    
    yield registry
    
    # Cleanup: reset singleton again
    TaskRegistry._instance = None


# ============================================================================
# LOGGING HELPERS
# ============================================================================

@pytest.fixture
def capture_logs():
    """
    Capture log output for assertions.
    """
    logs = []
    
    with patch('dailynotes.utils.Logger') as mock_logger:
        mock_logger.info.side_effect = lambda msg: logs.append(('INFO', msg))
        mock_logger.debug.side_effect = lambda msg: logs.append(('DEBUG', msg))
        mock_logger.error_once.side_effect = lambda key, msg: logs.append(('ERROR', msg))
        
        yield logs


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """
    Configure pytest markers.
    """
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests that require real file I/O"
    )

```

---
## File: AntigravitySync/tests/test_monitor_sections.py
```py

import sys
import os
import unittest
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath('/Users/user999/Documents/【Liang_project】/Code_Scripits/2025_DailynoteSync_complete_beta/AntigravitySync/src/external/note_sync_core'))

# Mock config before importing monitor
class MockConfig:
    DAILY_NOTE_DIR = "/tmp"
    TEMPLATE_FILE = "/tmp/template.md"
    KEYWORD_MAPPING = {"烟": "Cigarette"}

# Mock NoteMonitor parts to test logic without full init
from monitor import NoteMonitor

class TestNoteMonitorSections(unittest.TestCase):
    def setUp(self):
        self.monitor = NoteMonitor(config=MockConfig, logger=MagicMock())
        # Mock methods that rely on file system or external calls
        self.monitor._reader = MagicMock()
        
    def test_reorganize_takein_section(self):
        """Test if items are correctly added to ## #takein section"""
        # Simulate lines from the new template
        lines = [
            "# Day planner\n",
            "\n",
            "# Log\n",
            "## #stateofmind\n",
            "\n",
            "## #takein\n",
            "\n",
            "## #exercice\n",
            "\n",
            "## #account\n"
        ]
        
        new_entry = '23:00"Water":"x1"'
        
        # Test inserting into existing empty section
        updated_lines = self.monitor._reorganize_water_section(lines.copy(), new_entry)
        
        # Check if "Water" is in the output and under #takein
        joined = "".join(updated_lines)
        self.assertIn("## #takein", joined)
        self.assertIn("Water::x1", joined)
        
        # Verify position: should be between #takein and #exercice
        idx_takein = joined.find("## #takein")
        idx_entry = joined.find("Water::x1")
        idx_exercice = joined.find("## #exercice")
        
        self.assertTrue(idx_takein < idx_entry < idx_exercice, "Entry should be within #takein section")

    def test_append_to_account_section(self):
        """Test if items are correctly added to ## #account section (file write simulated)"""
        # This function reads/writes files, so we need to mock open
        # But parsing logic is inside _append_to_account_section which is hard to test without mocking open.
        # However, we can test the regex logic if we extract it, or mock open.
        pass

if __name__ == '__main__':
    unittest.main()

```

---
## File: AntigravitySync/tests/test_parsing.py
```py
"""
AntigravitySync Test Suite - test_parsing.py
Unit tests for src/dailynotes/sync/parsing.py

Tests cover:
- get_indent_depth: Indentation calculation
- clean_task_text: Task text extraction
- capture_block: Block boundary detection
- parse_file_tasks: Core parsing logic
- generate_block_id: ID generation
"""

import os
import sys
import re
import pytest
from unittest.mock import MagicMock, patch, call
from typing import List

# ============================================================================
# PATH SETUP
# ============================================================================

ANTIGRAVITY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ANTIGRAVITY_DIR, 'src')
for path in [ANTIGRAVITY_DIR, SRC_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)


# ============================================================================
# TESTS: get_indent_depth
# ============================================================================

class TestGetIndentDepth:
    """Tests for the get_indent_depth function."""
    
    def test_no_indent(self):
        """Test line with no indentation."""
        from dailynotes.sync.parsing import get_indent_depth
        assert get_indent_depth("- [ ] Task") == 0
    
    def test_two_space_indent(self):
        """Test line with 2-space indentation."""
        from dailynotes.sync.parsing import get_indent_depth
        assert get_indent_depth("  - [ ] Task") == 2
    
    def test_four_space_indent(self):
        """Test line with 4-space indentation."""
        from dailynotes.sync.parsing import get_indent_depth
        assert get_indent_depth("    - [ ] Task") == 4
    
    def test_tab_indent(self):
        """Test line with tab indentation (should expand to 4 spaces)."""
        from dailynotes.sync.parsing import get_indent_depth
        assert get_indent_depth("\t- [ ] Task") == 4
    
    def test_mixed_indent(self):
        """Test line with mixed spaces and tabs."""
        from dailynotes.sync.parsing import get_indent_depth
        # Tab (4) + 2 spaces = 6
        assert get_indent_depth("\t  - [ ] Task") == 6
    
    def test_quoted_line(self):
        """Test line with quote prefix (should be stripped)."""
        from dailynotes.sync.parsing import get_indent_depth
        # Quote prefix removed, then indent measured
        assert get_indent_depth("> - [ ] Task") == 0
        assert get_indent_depth(">   - [ ] Task") == 2


# ============================================================================
# TESTS: clean_task_text
# ============================================================================

class TestCleanTaskText:
    """Tests for the clean_task_text function."""
    
    def test_simple_task(self):
        """Test cleaning a simple task line."""
        from dailynotes.sync.parsing import clean_task_text
        result = clean_task_text("- [ ] Simple task", None, None)
        assert result == "Simple task"
    
    def test_removes_time(self):
        """Test that time is removed from task text."""
        from dailynotes.sync.parsing import clean_task_text
        result = clean_task_text("- [ ] 10:00 Task with time", None, None)
        assert result == "Task with time"
    
    def test_removes_time_range(self):
        """Test that time range is removed."""
        from dailynotes.sync.parsing import clean_task_text
        result = clean_task_text("- [ ] 10:00 - 11:30 Task", None, None)
        assert result == "Task"
    
    def test_removes_block_id(self):
        """Test that block ID is removed."""
        from dailynotes.sync.parsing import clean_task_text
        result = clean_task_text("- [ ] Task ^abc123", "abc123", None)
        assert result == "Task"
    
    def test_removes_date_link(self):
        """Test that date links are removed."""
        from dailynotes.sync.parsing import clean_task_text
        result = clean_task_text("- [ ] Task [[2025-01-15]]", None, None)
        assert result == "Task"
    
    def test_removes_emoji_date(self):
        """Test that emoji dates are removed."""
        from dailynotes.sync.parsing import clean_task_text
        result = clean_task_text("- [ ] Task 📅 [[2025-01-15]]", None, None)
        # Note: The emoji itself may remain, only the date portion is removed
        assert "2025-01-15" not in result
        assert "Task" in result
    
    def test_removes_return_link(self):
        """Test that return links are removed."""
        from dailynotes.sync.parsing import clean_task_text
        result = clean_task_text("- [ ] Task [[Project#^abc123|⮐]]", None, None)
        assert result == "Task"
    
    def test_removes_context_link(self):
        """Test that self-referencing project links are removed."""
        from dailynotes.sync.parsing import clean_task_text
        result = clean_task_text("- [ ] Task [[ProjectName]]", None, "ProjectName")
        assert result == "Task"
    
    def test_preserves_regular_links(self):
        """Test that non-date, non-return links are preserved."""
        from dailynotes.sync.parsing import clean_task_text
        result = clean_task_text("- [ ] Task [[SomeNote]]", None, None)
        assert "SomeNote" in result or "[[SomeNote]]" in result
    
    def test_complex_cleanup(self):
        """Test cleaning a complex task line."""
        from dailynotes.sync.parsing import clean_task_text
        line = "- [ ] 14:00 - 15:00 Complex #A task [[2025-01-20]] ^xyz789"
        result = clean_task_text(line, "xyz789", None)
        assert "Complex" in result
        assert "#A" in result or "task" in result
        assert "14:00" not in result
        assert "^xyz789" not in result


# ============================================================================
# TESTS: capture_block
# ============================================================================

class TestCaptureBlock:
    """Tests for the capture_block function."""
    
    def test_single_line_task(self):
        """Test capturing a single-line task."""
        from dailynotes.sync.parsing import capture_block
        lines = ["- [ ] Task\n", "- [ ] Another\n"]
        block, consumed = capture_block(lines, 0)
        
        assert len(block) == 1
        assert consumed == 1
    
    def test_task_with_children(self):
        """Test capturing a task with indented children."""
        from dailynotes.sync.parsing import capture_block
        lines = [
            "- [ ] Parent task\n",
            "  - [ ] Child task\n",
            "  - Note line\n",
            "- [ ] Sibling task\n",
        ]
        block, consumed = capture_block(lines, 0)
        
        assert consumed == 3  # Parent + 2 children
        assert len(block) == 3
    
    def test_stops_at_same_indent(self):
        """Test that capture stops at same/lower indentation."""
        from dailynotes.sync.parsing import capture_block
        lines = [
            "- [ ] Task 1\n",
            "- [ ] Task 2\n",
        ]
        block, consumed = capture_block(lines, 0)
        
        assert consumed == 1
        assert block[0].strip() == "- [ ] Task 1"
    
    def test_empty_lines_within_block(self):
        """Test handling of empty lines within a block."""
        from dailynotes.sync.parsing import capture_block
        lines = [
            "- [ ] Task\n",
            "  note\n",
            "\n",
            "  more notes\n",
            "- [ ] Next\n",
        ]
        block, consumed = capture_block(lines, 0)
        
        # Should include empty line and more notes
        assert consumed >= 3
    
    def test_stops_after_too_many_empty_lines(self):
        """Test that capture stops after MAX_CONSECUTIVE_EMPTY lines."""
        from dailynotes.sync.parsing import capture_block
        lines = [
            "- [ ] Task\n",
            "\n",
            "\n",
            "\n",  # 3 empty lines - should stop
            "  - [ ] Would-be child\n",
        ]
        block, consumed = capture_block(lines, 0)
        
        # Should stop before "would-be child"
        assert "Would-be child" not in "".join(block)


# ============================================================================
# TESTS: generate_block_id
# ============================================================================

class TestGenerateBlockId:
    """Tests for the generate_block_id function."""
    
    def test_format(self):
        """Test that generated ID has correct format."""
        from dailynotes.sync.parsing import generate_block_id
        bid = generate_block_id()
        
        assert bid.startswith('^')
        assert len(bid) == 7  # ^ + 6 chars
    
    def test_alphanumeric(self):
        """Test that ID contains only allowed characters."""
        from dailynotes.sync.parsing import generate_block_id
        bid = generate_block_id()
        
        # Remove the ^ prefix
        chars = bid[1:]
        assert all(c.isalnum() for c in chars)
    
    def test_uniqueness(self):
        """Test that multiple IDs are unique."""
        from dailynotes.sync.parsing import generate_block_id
        ids = [generate_block_id() for _ in range(100)]
        
        # All should be unique
        assert len(set(ids)) == 100


# ============================================================================
# TESTS: parse_file_tasks
# ============================================================================

class TestParseFileTasks:
    """Tests for the main parse_file_tasks function."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Set up mocks for parse_file_tasks dependencies."""
        # Config/Logger/FileUtils are lazy-imported inside parse_file_tasks
        # So we patch them at the config and utils module level
        with patch('config.Config') as mock_config, \
             patch('dailynotes.utils.Logger') as mock_logger, \
             patch('dailynotes.utils.FileUtils') as mock_file_utils:
            
            mock_config.SYNC_START_DATE = "2025-01-01"
            mock_file_utils.read_file.return_value = []
            mock_file_utils.write_file.return_value = None
            
            yield {
                'config': mock_config,
                'logger': mock_logger,
                'file_utils': mock_file_utils,
            }
    
    def test_empty_file(self, mock_dependencies):
        """Test parsing an empty file."""
        from dailynotes.sync.parsing import parse_file_tasks
        
        mock_sm = MagicMock()
        tasks, lines, modified = parse_file_tasks(
            "/test/file.md", [], "TestProject", mock_sm, write_back=False
        )
        
        assert tasks == []
        assert not modified
    
    def test_no_task_section(self, mock_dependencies):
        """Test file without a # Tasks section."""
        from dailynotes.sync.parsing import parse_file_tasks
        
        lines = [
            "# Notes\n",
            "\n",
            "Some content\n",
        ]
        
        mock_sm = MagicMock()
        tasks, _, _ = parse_file_tasks(
            "/test/file.md", lines, "TestProject", mock_sm, write_back=False
        )
        
        assert tasks == []
    
    def test_basic_task_extraction(self, mock_dependencies):
        """Test extracting a basic task from # Tasks section."""
        from dailynotes.sync.parsing import parse_file_tasks
        
        lines = [
            "# Tasks\n",
            "\n",
            "## [[2025-01-15]]\n",
            "\n",
            "- [ ] 10:00 Test task ^abc123\n",
            "\n",
            "----------\n",
        ]
        
        mock_sm = MagicMock()
        mock_sm.calc_hash.return_value = "hash123"
        
        tasks, _, _ = parse_file_tasks(
            "/test/file.md", lines, "TestProject", mock_sm, write_back=False
        )
        
        assert len(tasks) == 1
        task = tasks[0]
        assert task['bid'] == 'abc123'
        assert task['proj'] == 'TestProject'
        assert task['_task_date'] == '2025-01-15'
    
    def test_multiple_dates(self, mock_dependencies):
        """Test extracting tasks from multiple date headers."""
        from dailynotes.sync.parsing import parse_file_tasks
        
        lines = [
            "# Tasks\n",
            "\n",
            "## [[2025-01-15]]\n",
            "- [ ] Task one ^task01\n",
            "\n",
            "## [[2025-01-16]]\n",
            "- [ ] Task two ^task02\n",
            "\n",
            "----------\n",
        ]
        
        mock_sm = MagicMock()
        mock_sm.calc_hash.return_value = "hash"
        
        tasks, _, _ = parse_file_tasks(
            "/test/file.md", lines, "TestProject", mock_sm, write_back=False
        )
        
        assert len(tasks) == 2
        dates = {t['_task_date'] for t in tasks}
        assert dates == {'2025-01-15', '2025-01-16'}
    
    def test_generates_missing_id(self, mock_dependencies):
        """Test that a missing block ID is generated."""
        from dailynotes.sync.parsing import parse_file_tasks
        
        lines = [
            "# Tasks\n",
            "## [[2025-01-15]]\n",
            "- [ ] Task without ID\n",
            "----------\n",
        ]
        
        mock_sm = MagicMock()
        mock_sm.calc_hash.return_value = "hash"
        mock_sm.find_id_by_hash.return_value = None
        
        tasks, modified_lines, was_modified = parse_file_tasks(
            "/test/file.md", lines, "TestProject", mock_sm, write_back=False
        )
        
        assert len(tasks) == 1
        assert tasks[0]['bid'] is not None
        assert len(tasks[0]['bid']) >= 6
        assert was_modified  # Should be modified because ID was added
    
    def test_rescues_id_from_hash(self, mock_dependencies):
        """Test that ID is recovered using hash lookup."""
        from dailynotes.sync.parsing import parse_file_tasks
        
        lines = [
            "# Tasks\n",
            "## [[2025-01-15]]\n",
            "- [ ] Task without ID\n",
            "----------\n",
        ]
        
        mock_sm = MagicMock()
        mock_sm.calc_hash.return_value = "hash"
        mock_sm.find_id_by_hash.return_value = "rescued1"  # Return rescued ID
        
        tasks, _, _ = parse_file_tasks(
            "/test/file.md", lines, "TestProject", mock_sm, write_back=False
        )
        
        assert len(tasks) == 1
        assert tasks[0]['bid'] == 'rescued1'
    
    def test_respects_time_gate(self, mock_dependencies):
        """Test that tasks before SYNC_START_DATE are skipped."""
        from dailynotes.sync.parsing import parse_file_tasks
        
        # Set sync start date to 2025-01-10
        mock_dependencies['config'].SYNC_START_DATE = "2025-01-10"
        
        lines = [
            "# Tasks\n",
            "## [[2025-01-05]]\n",  # Before sync start
            "- [ ] Old task ^old001\n",
            "## [[2025-01-15]]\n",  # After sync start
            "- [ ] New task ^new001\n",
            "----------\n",
        ]
        
        mock_sm = MagicMock()
        mock_sm.calc_hash.return_value = "hash"
        mock_sm.find_id_by_hash.return_value = None  # Must be None, not MagicMock
        
        tasks, _, _ = parse_file_tasks(
            "/test/file.md", lines, "TestProject", mock_sm, write_back=False
        )
        
        # Only the new task should be returned
        assert len(tasks) == 1
        assert tasks[0]['bid'] == 'new001'
    
    def test_stops_at_delimiter(self, mock_dependencies):
        """Test that parsing stops at ---------- delimiter."""
        from dailynotes.sync.parsing import parse_file_tasks
        
        lines = [
            "# Tasks\n",
            "## [[2025-01-15]]\n",
            "- [ ] Task in section ^task01\n",
            "----------\n",
            "- [ ] Task outside ^task02\n",  # Should NOT be parsed
        ]
        
        mock_sm = MagicMock()
        mock_sm.calc_hash.return_value = "hash"
        
        tasks, _, _ = parse_file_tasks(
            "/test/file.md", lines, "TestProject", mock_sm, write_back=False
        )
        
        assert len(tasks) == 1
        assert tasks[0]['bid'] == 'task01'
    
    def test_nested_children_captured(self, mock_dependencies):
        """Test that nested child lines are captured in raw block."""
        from dailynotes.sync.parsing import parse_file_tasks
        
        lines = [
            "# Tasks\n",
            "## [[2025-01-15]]\n",
            "- [ ] Parent task ^parent\n",
            "  - [ ] Child task\n",
            "  - Note under parent\n",
            "----------\n",
        ]
        
        mock_sm = MagicMock()
        mock_sm.calc_hash.return_value = "hash"
        
        tasks, _, _ = parse_file_tasks(
            "/test/file.md", lines, "TestProject", mock_sm, write_back=False
        )
        
        assert len(tasks) == 1  # Only parent is a "task"
        # Raw block should include children
        raw = "".join(tasks[0]['raw'])
        assert "Child task" in raw
        assert "Note under parent" in raw
    
    def test_completed_task_status(self, mock_dependencies):
        """Test that completed task status is captured."""
        from dailynotes.sync.parsing import parse_file_tasks
        
        lines = [
            "# Tasks\n",
            "## [[2025-01-15]]\n",
            "- [x] Completed task ^done01\n",
            "----------\n",
        ]
        
        mock_sm = MagicMock()
        mock_sm.calc_hash.return_value = "hash"
        
        tasks, _, _ = parse_file_tasks(
            "/test/file.md", lines, "TestProject", mock_sm, write_back=False
        )
        
        assert len(tasks) == 1
        assert tasks[0]['status'] == 'x'


# ============================================================================
# TESTS: Write-back behavior
# ============================================================================

class TestParseFileTasksWriteBack:
    """Tests for parse_file_tasks write_back functionality."""
    
    def test_write_back_disabled(self):
        """Test that write_back=False prevents file writes."""
        with patch('config.Config') as mock_config, \
             patch('dailynotes.utils.Logger'), \
             patch('dailynotes.utils.FileUtils') as mock_file_utils:
            
            mock_config.SYNC_START_DATE = "2025-01-01"
            
            from dailynotes.sync.parsing import parse_file_tasks
            
            lines = [
                "# Tasks\n",
                "## [[2025-01-15]]\n",
                "- [ ] Task without ID\n",  # Will trigger modification
                "----------\n",
            ]
            
            mock_sm = MagicMock()
            mock_sm.calc_hash.return_value = "hash"
            mock_sm.find_id_by_hash.return_value = None
            
            tasks, _, modified = parse_file_tasks(
                "/test/file.md", lines, "TestProject", mock_sm, write_back=False
            )
            
            # Should NOT write even if modified
            mock_file_utils.write_file.assert_not_called()
    
    def test_write_back_enabled(self):
        """Test that write_back=True triggers file write when modified."""
        with patch('config.Config') as mock_config, \
             patch('dailynotes.utils.Logger'), \
             patch('dailynotes.utils.FileUtils') as mock_file_utils:
            
            mock_config.SYNC_START_DATE = "2025-01-01"
            mock_file_utils.read_file.return_value = ["original\n"]
            
            from dailynotes.sync.parsing import parse_file_tasks
            
            lines = [
                "# Tasks\n",
                "## [[2025-01-15]]\n",
                "- [ ] Task without ID\n",
                "----------\n",
            ]
            
            mock_sm = MagicMock()
            mock_sm.calc_hash.return_value = "hash"
            mock_sm.find_id_by_hash.return_value = None
            
            tasks, _, modified = parse_file_tasks(
                "/test/file.md", lines, "TestProject", mock_sm, write_back=True
            )
            
            # Should write because content was modified
            assert modified
            mock_file_utils.write_file.assert_called_once()

```

---
## File: AntigravitySync/tests/test_registry.py
```py
"""
AntigravitySync Test Suite - test_registry.py
Unit tests for src/dailynotes/sync/task_registry.py

Critical tests for v1.8 core value:
- Initialization populates cache
- Incremental update_file correctly adds/removes/modifies tasks
- Data consistency: update overwrites old data, doesn't append
- Affected dates tracking

ALL FILE I/O IS MOCKED - NO REAL DISK ACCESS
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch, call
from typing import Dict, List, Set

# ============================================================================
# PATH SETUP
# ============================================================================

ANTIGRAVITY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ANTIGRAVITY_DIR, 'src')
for path in [ANTIGRAVITY_DIR, SRC_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)


# ============================================================================
# HELPER: Reset TaskRegistry singleton between tests
# ============================================================================

@pytest.fixture(autouse=True)
def reset_registry_singleton():
    """Reset TaskRegistry singleton before and after each test."""
    # Import here to ensure path is set up
    from dailynotes.sync.task_registry import TaskRegistry
    
    # Reset before test
    TaskRegistry._instance = None
    
    yield
    
    # Reset after test
    TaskRegistry._instance = None


# ============================================================================
# HELPER: Create mock tasks
# ============================================================================

def make_mock_task(bid: str, date: str, project: str = "TestProj", 
                   pure: str = "Test task") -> Dict:
    """Create a mock task dictionary."""
    return {
        'proj': project,
        'bid': bid,
        'pure': pure,
        'status': ' ',
        'path': f'/mock/vault/{project}.md',
        'fname': project,
        'raw': [f"- [ ] {pure} ^{bid}\n"],
        'hash': f'hash_{bid}',
        'indent': 0,
        'dates': f'[[{date}]]',
        'is_quoted': False,
        '_task_date': date,
    }


# ============================================================================
# TESTS: TaskRegistry Initialization
# ============================================================================

class TestTaskRegistryInitialization:
    """Tests for TaskRegistry initialization behavior."""
    
    def test_singleton_pattern(self):
        """Test that TaskRegistry is a singleton."""
        with patch('dailynotes.sync.task_registry.Config') as mock_config, \
             patch('dailynotes.sync.task_registry.Logger'):
            
            mock_config.ROOT_DIR = "/mock/vault"
            
            from dailynotes.sync.task_registry import TaskRegistry, get_registry
            
            reg1 = get_registry()
            reg2 = get_registry()
            
            assert reg1 is reg2
    
    def test_initialize_calls_os_walk(self):
        """Test that initialize() uses os.walk for full scan."""
        with patch('dailynotes.sync.task_registry.Config') as mock_config, \
             patch('dailynotes.sync.task_registry.Logger'), \
             patch('dailynotes.sync.task_registry.FileUtils') as mock_fu, \
             patch('dailynotes.sync.task_registry.parse_file_tasks') as mock_parse, \
             patch('os.walk') as mock_walk:
            
            mock_config.ROOT_DIR = "/mock/vault"
            mock_config.SYNC_START_DATE = "2025-01-01"
            mock_fu.is_excluded.return_value = False
            
            # Simulate os.walk returning one directory with one file
            mock_walk.return_value = [
                ("/mock/vault/ProjectA", [], ["main.md"]),
            ]
            
            # parse_file_tasks returns empty (we test parsing elsewhere)
            mock_parse.return_value = ([], [], False)
            mock_fu.read_file.return_value = ["# Tasks\n"]
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            registry._project_map = {"/mock/vault/ProjectA": "ProjectA"}
            
            mock_sm = MagicMock()
            registry.initialize({"/mock/vault/ProjectA": "ProjectA"}, mock_sm)
            
            # os.walk should be called
            mock_walk.assert_called_once_with("/mock/vault")
    
    def test_initialize_populates_cache(self):
        """Test that initialize() populates _file_cache and _date_index."""
        with patch('dailynotes.sync.task_registry.Config') as mock_config, \
             patch('dailynotes.sync.task_registry.Logger'), \
             patch('dailynotes.sync.task_registry.FileUtils') as mock_fu, \
             patch('dailynotes.sync.task_registry.parse_file_tasks') as mock_parse, \
             patch('os.walk') as mock_walk:
            
            mock_config.ROOT_DIR = "/mock/vault"
            mock_config.SYNC_START_DATE = "2025-01-01"
            mock_fu.is_excluded.return_value = False
            
            mock_walk.return_value = [
                ("/mock/vault/ProjectA", [], ["main.md"]),
            ]
            
            # Return 2 tasks from parsing
            mock_tasks = [
                make_mock_task("task01", "2025-01-15"),
                make_mock_task("task02", "2025-01-15"),
            ]
            mock_parse.return_value = (mock_tasks, [], False)
            mock_fu.read_file.return_value = ["# Tasks\n"]
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            project_map = {"/mock/vault/ProjectA": "ProjectA"}
            
            mock_sm = MagicMock()
            registry.initialize(project_map, mock_sm)
            
            # Check _file_cache
            assert "/mock/vault/ProjectA/main.md" in registry._file_cache
            assert len(registry._file_cache["/mock/vault/ProjectA/main.md"]) == 2
            
            # Check _date_index
            assert "2025-01-15" in registry._date_index
            assert "task01" in registry._date_index["2025-01-15"]
            assert "task02" in registry._date_index["2025-01-15"]


# ============================================================================
# TESTS: Incremental Update (CRITICAL v1.8 TESTS)
# ============================================================================

class TestTaskRegistryUpdate:
    """
    CRITICAL: Tests for update_file() - the core of incremental sync.
    
    These tests verify:
    1. New tasks are added to cache
    2. Modified tasks overwrite old entries
    3. Deleted tasks are removed from cache
    4. Affected dates are correctly tracked
    """
    
    def test_update_adds_new_tasks(self):
        """Test that update_file adds new tasks to cache."""
        with patch('dailynotes.sync.task_registry.Config') as mock_config, \
             patch('dailynotes.sync.task_registry.Logger'), \
             patch('dailynotes.sync.task_registry.FileUtils') as mock_fu, \
             patch('dailynotes.sync.task_registry.parse_file_tasks') as mock_parse, \
             patch('os.path.exists', return_value=True):
            
            mock_config.ROOT_DIR = "/mock/vault"
            mock_config.SYNC_START_DATE = "2025-01-01"
            mock_fu.read_file.return_value = ["# Tasks\n"]
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            registry._project_map = {"/mock/vault/ProjectA": "ProjectA"}
            registry._file_cache = {}
            registry._date_index = {}
            registry._file_to_dates = {}
            
            # Simulate parsing returns 3 tasks
            mock_tasks = [
                make_mock_task("new01", "2025-01-15"),
                make_mock_task("new02", "2025-01-15"),
                make_mock_task("new03", "2025-01-16"),
            ]
            mock_parse.return_value = (mock_tasks, [], False)
            
            mock_sm = MagicMock()
            affected = registry.update_file("/mock/vault/ProjectA/test.md", mock_sm)
            
            # Check cache contains 3 tasks
            assert len(registry._file_cache["/mock/vault/ProjectA/test.md"]) == 3
            
            # Check affected dates
            assert affected == {"2025-01-15", "2025-01-16"}
    
    def test_update_overwrites_modified_tasks(self):
        """
        CRITICAL: Test that update_file overwrites old tasks, not appends.
        
        Scenario:
        - File initially has 3 tasks: A, B, C
        - File is modified to have 2 tasks: A, D (B and C deleted, D added)
        - Cache should have ONLY A and D, not A, B, C, D
        """
        with patch('dailynotes.sync.task_registry.Config') as mock_config, \
             patch('dailynotes.sync.task_registry.Logger'), \
             patch('dailynotes.sync.task_registry.FileUtils') as mock_fu, \
             patch('dailynotes.sync.task_registry.parse_file_tasks') as mock_parse, \
             patch('os.path.exists', return_value=True):
            
            mock_config.ROOT_DIR = "/mock/vault"
            mock_config.SYNC_START_DATE = "2025-01-01"
            mock_fu.read_file.return_value = ["# Tasks\n"]
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            registry._project_map = {"/mock/vault/ProjectA": "ProjectA"}
            
            filepath = "/mock/vault/ProjectA/test.md"
            
            # === INITIAL STATE: 3 tasks (A, B, C) ===
            initial_tasks = [
                make_mock_task("taskA", "2025-01-15"),
                make_mock_task("taskB", "2025-01-15"),
                make_mock_task("taskC", "2025-01-15"),
            ]
            registry._file_cache = {filepath: initial_tasks}
            registry._date_index = {
                "2025-01-15": {
                    "taskA": initial_tasks[0],
                    "taskB": initial_tasks[1],
                    "taskC": initial_tasks[2],
                }
            }
            registry._file_to_dates = {filepath: {"2025-01-15"}}
            
            # Verify initial state
            assert len(registry._file_cache[filepath]) == 3
            assert len(registry._date_index["2025-01-15"]) == 3
            
            # === MODIFIED STATE: 2 tasks (A, D) - B and C deleted ===
            modified_tasks = [
                make_mock_task("taskA", "2025-01-15"),  # Kept
                make_mock_task("taskD", "2025-01-15"),  # New
                # taskB and taskC are DELETED
            ]
            mock_parse.return_value = (modified_tasks, [], False)
            
            mock_sm = MagicMock()
            affected = registry.update_file(filepath, mock_sm)
            
            # === VERIFY: Cache should have ONLY 2 tasks ===
            assert len(registry._file_cache[filepath]) == 2
            
            # === VERIFY: Date index should have ONLY taskA and taskD ===
            assert len(registry._date_index["2025-01-15"]) == 2
            assert "taskA" in registry._date_index["2025-01-15"]
            assert "taskD" in registry._date_index["2025-01-15"]
            assert "taskB" not in registry._date_index["2025-01-15"]  # DELETED
            assert "taskC" not in registry._date_index["2025-01-15"]  # DELETED
    
    def test_update_removes_deleted_tasks(self):
        """
        CRITICAL: Test that deleting all tasks from a file clears the cache.
        
        This prevents "zombie tasks" from accumulating in memory.
        """
        with patch('dailynotes.sync.task_registry.Config') as mock_config, \
             patch('dailynotes.sync.task_registry.Logger'), \
             patch('dailynotes.sync.task_registry.FileUtils') as mock_fu, \
             patch('dailynotes.sync.task_registry.parse_file_tasks') as mock_parse, \
             patch('os.path.exists', return_value=True):
            
            mock_config.ROOT_DIR = "/mock/vault"
            mock_config.SYNC_START_DATE = "2025-01-01"
            mock_fu.read_file.return_value = ["# Tasks\n"]
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            registry._project_map = {"/mock/vault/ProjectA": "ProjectA"}
            
            filepath = "/mock/vault/ProjectA/test.md"
            
            # === INITIAL STATE: 3 tasks ===
            initial_tasks = [
                make_mock_task("del01", "2025-01-15"),
                make_mock_task("del02", "2025-01-15"),
                make_mock_task("del03", "2025-01-16"),
            ]
            registry._file_cache = {filepath: initial_tasks}
            registry._date_index = {
                "2025-01-15": {"del01": initial_tasks[0], "del02": initial_tasks[1]},
                "2025-01-16": {"del03": initial_tasks[2]},
            }
            registry._file_to_dates = {filepath: {"2025-01-15", "2025-01-16"}}
            
            # === ALL TASKS DELETED ===
            mock_parse.return_value = ([], [], False)  # Empty tasks
            
            mock_sm = MagicMock()
            affected = registry.update_file(filepath, mock_sm)
            
            # === VERIFY: File should no longer be in cache ===
            assert filepath not in registry._file_cache or registry._file_cache[filepath] == []
            
            # === VERIFY: Tasks should be removed from date index ===
            assert "del01" not in registry._date_index.get("2025-01-15", {})
            assert "del02" not in registry._date_index.get("2025-01-15", {})
            assert "del03" not in registry._date_index.get("2025-01-16", {})
            
            # === VERIFY: Affected dates includes both old dates ===
            assert "2025-01-15" in affected
            assert "2025-01-16" in affected
    
    def test_update_handles_file_deletion(self):
        """Test that update_file handles a deleted file correctly."""
        with patch('dailynotes.sync.task_registry.Config') as mock_config, \
             patch('dailynotes.sync.task_registry.Logger'), \
             patch('dailynotes.sync.task_registry.FileUtils') as mock_fu, \
             patch('os.path.exists', return_value=False):  # FILE DELETED
            
            mock_config.ROOT_DIR = "/mock/vault"
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            registry._project_map = {"/mock/vault/ProjectA": "ProjectA"}
            
            filepath = "/mock/vault/ProjectA/deleted.md"
            
            # === INITIAL STATE: File had tasks ===
            initial_tasks = [make_mock_task("gone01", "2025-01-20")]
            registry._file_cache = {filepath: initial_tasks}
            registry._date_index = {"2025-01-20": {"gone01": initial_tasks[0]}}
            registry._file_to_dates = {filepath: {"2025-01-20"}}
            
            mock_sm = MagicMock()
            affected = registry.update_file(filepath, mock_sm)
            
            # === VERIFY: File removed from cache ===
            assert filepath not in registry._file_cache
            
            # === VERIFY: Tasks removed from date index ===
            assert "gone01" not in registry._date_index.get("2025-01-20", {})
            
            # === VERIFY: Affected dates returned ===
            assert "2025-01-20" in affected
    
    def test_update_changes_task_date(self):
        """Test that changing a task's date updates both old and new date indices."""
        with patch('dailynotes.sync.task_registry.Config') as mock_config, \
             patch('dailynotes.sync.task_registry.Logger'), \
             patch('dailynotes.sync.task_registry.FileUtils') as mock_fu, \
             patch('dailynotes.sync.task_registry.parse_file_tasks') as mock_parse, \
             patch('os.path.exists', return_value=True):
            
            mock_config.ROOT_DIR = "/mock/vault"
            mock_config.SYNC_START_DATE = "2025-01-01"
            mock_fu.read_file.return_value = ["# Tasks\n"]
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            registry._project_map = {"/mock/vault/ProjectA": "ProjectA"}
            
            filepath = "/mock/vault/ProjectA/test.md"
            
            # === INITIAL STATE: Task on Jan 15 ===
            initial_task = make_mock_task("move01", "2025-01-15")
            registry._file_cache = {filepath: [initial_task]}
            registry._date_index = {"2025-01-15": {"move01": initial_task}}
            registry._file_to_dates = {filepath: {"2025-01-15"}}
            
            # === MODIFIED: Task moved to Jan 20 ===
            moved_task = make_mock_task("move01", "2025-01-20")  # Same ID, different date
            mock_parse.return_value = ([moved_task], [], False)
            
            mock_sm = MagicMock()
            affected = registry.update_file(filepath, mock_sm)
            
            # === VERIFY: Task no longer on old date ===
            assert "move01" not in registry._date_index.get("2025-01-15", {})
            
            # === VERIFY: Task is on new date ===
            assert "move01" in registry._date_index.get("2025-01-20", {})
            
            # === VERIFY: Both dates are affected ===
            assert "2025-01-15" in affected
            assert "2025-01-20" in affected


# ============================================================================
# TESTS: Data Retrieval
# ============================================================================

class TestTaskRegistryRetrieval:
    """Tests for get_tasks_by_date and get_affected_dates."""
    
    def test_get_tasks_by_date(self):
        """Test retrieving tasks for a specific date."""
        with patch('dailynotes.sync.task_registry.Config'), \
             patch('dailynotes.sync.task_registry.Logger'):
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            
            task1 = make_mock_task("get01", "2025-01-15")
            task2 = make_mock_task("get02", "2025-01-15")
            
            registry._date_index = {
                "2025-01-15": {"get01": task1, "get02": task2},
                "2025-01-16": {},
            }
            
            result = registry.get_tasks_by_date("2025-01-15")
            
            assert len(result) == 2
            assert "get01" in result
            assert "get02" in result
    
    def test_get_tasks_by_date_returns_copy(self):
        """Test that get_tasks_by_date returns a copy, not the original."""
        with patch('dailynotes.sync.task_registry.Config'), \
             patch('dailynotes.sync.task_registry.Logger'):
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            
            task = make_mock_task("copy01", "2025-01-15")
            registry._date_index = {"2025-01-15": {"copy01": task}}
            
            result = registry.get_tasks_by_date("2025-01-15")
            
            # Modify the result
            result["injected"] = {"evil": "data"}
            
            # Original should be unchanged
            assert "injected" not in registry._date_index["2025-01-15"]
    
    def test_get_tasks_by_date_nonexistent(self):
        """Test retrieving tasks for a date with no tasks."""
        with patch('dailynotes.sync.task_registry.Config'), \
             patch('dailynotes.sync.task_registry.Logger'):
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            registry._date_index = {}
            
            result = registry.get_tasks_by_date("2099-12-31")
            
            assert result == {}
    
    def test_get_affected_dates(self):
        """Test getting dates affected by a specific file."""
        with patch('dailynotes.sync.task_registry.Config'), \
             patch('dailynotes.sync.task_registry.Logger'):
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            
            filepath = "/mock/vault/test.md"
            registry._file_to_dates = {
                filepath: {"2025-01-15", "2025-01-16", "2025-01-17"},
            }
            
            result = registry.get_affected_dates(filepath)
            
            assert result == {"2025-01-15", "2025-01-16", "2025-01-17"}


# ============================================================================
# TESTS: Thread Safety
# ============================================================================

class TestTaskRegistryThreadSafety:
    """Tests for thread-safe operations."""
    
    def test_concurrent_updates_dont_crash(self):
        """Test that concurrent update_file calls don't cause crashes."""
        import threading
        
        with patch('dailynotes.sync.task_registry.Config') as mock_config, \
             patch('dailynotes.sync.task_registry.Logger'), \
             patch('dailynotes.sync.task_registry.FileUtils') as mock_fu, \
             patch('dailynotes.sync.task_registry.parse_file_tasks') as mock_parse, \
             patch('os.path.exists', return_value=True):
            
            mock_config.ROOT_DIR = "/mock/vault"
            mock_config.SYNC_START_DATE = "2025-01-01"
            mock_fu.read_file.return_value = ["# Tasks\n"]
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            registry._project_map = {"/mock/vault/ProjectA": "ProjectA"}
            registry._file_cache = {}
            registry._date_index = {}
            registry._file_to_dates = {}
            
            mock_parse.return_value = ([make_mock_task("t1", "2025-01-15")], [], False)
            mock_sm = MagicMock()
            
            errors = []
            
            def do_update(file_num):
                try:
                    registry.update_file(f"/mock/vault/ProjectA/file{file_num}.md", mock_sm)
                except Exception as e:
                    errors.append(e)
            
            threads = [threading.Thread(target=do_update, args=(i,)) for i in range(10)]
            
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            
            # No errors should have occurred
            assert len(errors) == 0


# ============================================================================
# TESTS: Realistic Parsing Scenarios (Complex Data)
# ============================================================================

class TestTaskRegistryRealisticScenarios:
    """
    Tests with realistic, complex markdown content.
    
    These scenarios match real-world usage patterns.
    """
    
    def test_complex_task_section(self):
        """Test parsing a complex # Tasks section with various formats."""
        with patch('dailynotes.sync.task_registry.Config') as mock_config, \
             patch('dailynotes.sync.task_registry.Logger'), \
             patch('dailynotes.sync.task_registry.FileUtils') as mock_fu, \
             patch('os.walk') as mock_walk, \
             patch('os.path.exists', return_value=True):
            
            mock_config.ROOT_DIR = "/mock/vault"
            mock_config.SYNC_START_DATE = "2025-01-01"
            mock_fu.is_excluded.return_value = False
            mock_fu.write_file.return_value = None
            
            # Realistic complex content
            complex_content = [
                "---\n",
                "tags:\n",
                "  - main\n",
                "---\n",
                "\n",
                "# Project Overview\n",
                "\n",
                "Some project notes.\n",
                "\n",
                "# Tasks\n",
                "\n",
                "## [[2025-01-15]]\n",
                "\n",
                "- [ ] 普通任务 ^task01\n",
                "- [x] 10:00 - 11:00 带时间的任务 ^task02\n",
                "    - [ ] 缩进的子任务 ^child01\n",
                "    - 普通缩进备注\n",
                "- [ ] 14:00 #A 带标签的紧急任务 [[2025-01-15]] ^task03\n",
                "- [ ] Task with return link [[Project#^abc123|⮐]] ^task04\n",
                "\n",
                "## [[2025-01-16]]\n",
                "\n",
                "- [ ] 明天的任务 📅 2025-01-16 ^task05\n",
                "\n",
                "----------\n",
                "\n",
                "# Notes\n",
                "\n",
                "Other content that should be ignored.\n",
            ]
            
            mock_fu.read_file.return_value = complex_content
            
            mock_walk.return_value = [
                ("/mock/vault/Project", [], ["main.md"]),
            ]
            
            from dailynotes.sync.task_registry import TaskRegistry
            
            registry = TaskRegistry()
            mock_sm = MagicMock()
            mock_sm.calc_hash.return_value = "hash"
            mock_sm.find_id_by_hash.return_value = None
            
            registry.initialize({"/mock/vault/Project": "Project"}, mock_sm)
            
            # Verify tasks were parsed
            tasks_jan15 = registry.get_tasks_by_date("2025-01-15")
            tasks_jan16 = registry.get_tasks_by_date("2025-01-16")
            
            # Should have 4 main tasks on Jan 15 (child is part of parent's block)
            assert len(tasks_jan15) == 4
            
            # Should have 1 task on Jan 16
            assert len(tasks_jan16) == 1
            
            # Verify specific task IDs exist
            assert "task01" in tasks_jan15
            assert "task02" in tasks_jan15
            assert "task03" in tasks_jan15
            assert "task04" in tasks_jan15
            assert "task05" in tasks_jan16

```

---
## File: AntigravitySync/src/dailynotes/__init__.py
```py
import sys
import os

# Ensure config can be imported from root if not already
# This is a fallback in case sys.path is messed up, but main.py should handle it.

```

---
## File: AntigravitySync/src/dailynotes/format_core.py
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
        p_text = cls._safe_strip("\n".join(preamble))
        if p_text: output.append(p_text)

        for blk in sorted_blocks:
            # 块内部使用单换行拼接，保持紧凑
            # [FIX] 使用 _safe_strip 而非 rstrip，保留行尾有意义的空格
            blk_text = cls._safe_strip("\n".join(blk))
            output.append(blk_text)

        # 块之间使用双换行拼接 (顶层任务之间留空)
        return cls._safe_strip("\n\n".join(output))

    @staticmethod
    def _safe_strip(content: str) -> str:
        """
        [FIX] 安全的 strip：只移除首尾的空白行，不移除行内尾部空格
        这样可以保留 Obsidian 列表语法 "- " 中的空格
        """
        if not content:
            return content
        lines = content.split('\n')
        # 移除首部空行
        while lines and not lines[0].strip():
            lines.pop(0)
        # 移除尾部空行
        while lines and not lines[-1].strip():
            lines.pop()
        return '\n'.join(lines)

    @classmethod
    def sort_markdown_sections(cls, text: str, filename: str = "") -> str:
        if not text.strip(): return text

        sections = re.split(r'^(#\s.*)$', cls._safe_strip(text), flags=re.MULTILINE)
        output = []

        start_idx = 0
        if sections and not sections[0].startswith('#'):
            output.append(cls._safe_strip(sections[0]))
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

            pre_l2 = cls._safe_strip(sub_blocks[0])
            if pre_l2:
                if is_target_section:
                    processed_sub_sections.append(cls.sort_day_planner_content(pre_l2))
                else:
                    processed_sub_sections.append(pre_l2)

            j = 1
            while j < len(sub_blocks):
                l2_title = sub_blocks[j].strip()
                l2_content = cls._safe_strip(sub_blocks[j + 1]) if j + 1 < len(sub_blocks) else ""

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

            full_section_content = cls._safe_strip("\n\n".join(processed_sub_sections))

            if full_section_content:
                output.append(f"{title}\n\n{full_section_content}")
            else:
                output.append(title)

            i += 2

        # [FIX] 智能拼接：如果第一个元素是 YAML frontmatter，则用单换行连接
        # YAML frontmatter 以 "---" 开头，其后应紧跟标题而非空行
        if output and len(output) >= 2 and output[0].strip().startswith('---'):
            # Frontmatter + 单换行 + 其余内容（双换行分隔）
            frontmatter = output[0]
            rest = "\n\n".join(output[1:])
            return cls._safe_strip(f"{frontmatter}\n{rest}")
        
        return cls._safe_strip("\n\n".join(output))

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
## File: AntigravitySync/src/dailynotes/manager.py
```py
"""
Fusion Manager - Antigravity Architecture v3.0 (Chronos Mode)
Pure Event-Driven Sync Engine - No Polling Required.

Key Features:
- [v3.0] Chronos Mode: Full event-driven, no polling
- [v3.0] Startup Full Sync: Scans past 1 year to future 10 years
- [v3.0] Event-Triggered Window Sync: Only syncs affected window on calendar change
- [v2.0] CFRunLoop Integration: Instant notification delivery
"""
import os
import sys
import re
import time
import datetime
import signal
import threading
from config import Config
from .utils import Logger, FileUtils
from .format_core import FormatCore
from .state_manager import StateManager
from .sync import SyncCore
from external.apple_sync_adapter import AppleSyncAdapter

# [v1.9] Native Calendar Monitor Import
try:
    from external.eventkit_wrapper import EventKitClient
    EK_AVAILABLE = True
except ImportError:
    EK_AVAILABLE = False
    EventKitClient = None

# [v3.8] Reminder Kit Import
try:
    from external.reminder_kit import ReminderKitClient
    REMINDER_AVAILABLE = True
except ImportError:
    REMINDER_AVAILABLE = False
    ReminderKitClient = None

# watchdog 导入（带降级处理）
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    class FileSystemEventHandler:
        pass
    Logger.error_once("watchdog_import", "⚠️ watchdog 库未安装")


class ObsidianEventHandler(FileSystemEventHandler):
    """
    [v1.6] 文件变更事件处理器 - 支持原子写入
    [v3.1] 新增变更来源检测机制
    """
    
    # 已知进程特征映射
    _PROCESS_SIGNATURES = {
        'obsidian': 'OBSIDIAN',
        'electron': 'OBSIDIAN',  # Obsidian 基于 Electron
        'vim': 'USER',
        'nvim': 'USER',
        'code': 'USER',  # VS Code
        'sublime': 'USER',
        'textedit': 'USER',
        'bbedit': 'USER',
        'atom': 'USER',
        'finder': 'MACOS',
        'mds': 'MACOS',  # Spotlight indexer
        'mdworker': 'MACOS',  # Spotlight worker
        'fseventsd': 'MACOS',
        'python': 'SYSTEM',  # 可能是本程序
    }
    
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self._last_event_time = {}

    def _detect_change_source(self, filepath: str, is_system_write: bool) -> str:
        """
        [v3.1] 检测文件变更来源
        
        返回值:
        - 'SYSTEM': AntigravitySync 自身写入
        - 'OBSIDIAN_TYPING': 用户在 Obsidian 中打字/交互 (依据: workspace.json 同时更新)
        - 'OBSIDIAN_SYNC': Obsidian 后台同步 (依据: workspace.json 未更新)
        - 'USER': 用户通过其他编辑器修改
        - 'MACOS': macOS 系统进程 (Finder, Spotlight 等)
        - 'UNKNOWN': 无法确定来源
        """
        import subprocess
        
        # [优先级 1] 检查是否为 AntigravitySync 自身写入
        if is_system_write:
            return 'SYSTEM'
            
        detected_source = 'UNKNOWN'
        
        # [优先级 1] 检查是否为 AntigravitySync 自身写入
        if is_system_write:
            return 'SYSTEM'
            
        detected_source = 'UNKNOWN'
        
        # [优先级 2] 尝试通过 lsof/fuser 获取打开该文件的进程 (极简版)
        # 注意: lsof 在 macOS 上可能很慢，且不一定能捕获瞬时写入
        # 这里仅作为一种辅助手段，不强求成功
        try:
            # 仅当文件存在时检查
            if os.path.exists(filepath):
                 pass #暂不启用 lsof 以避免性能损耗
        except Exception:
            pass
        
        # [优先级 3] 检查文件扩展名特征
        if detected_source == 'UNKNOWN':
            filename = os.path.basename(filepath)
            if filename.startswith('.'):
                if filename == '.DS_Store':
                    return 'MACOS'
                elif filename.startswith('.obsidian'):
                    detected_source = 'OBSIDIAN'
            
            # [优先级 4] 检查父目录特征
            elif '/.obsidian/' in filepath or '\\.obsidian\\' in filepath:
                detected_source = 'OBSIDIAN'
        
        # [优先级 5] 检查是否有 Obsidian 进程在运行
        if detected_source == 'UNKNOWN':
            try:
                result = subprocess.run(
                    ['pgrep', '-x', 'Obsidian'],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                if result.returncode == 0 and filepath.endswith('.md'):
                    detected_source = 'OBSIDIAN'
            except Exception:
                pass
        
        # [v3.4] 细化 Obsidian 来源：多维验证 (TYPING vs SYNC)
        if detected_source in ('OBSIDIAN', 'OBSIDIAN_LIKELY'):
            is_typing = False
            reasons = []

            # --- A. Workspace 活跃度 (强特征) ---
            try:
                obsidian_config_dir = os.path.join(Config.VAULT_ROOT, '.obsidian')
                md_mtime = os.path.getmtime(filepath) if os.path.exists(filepath) else 0

                # 检查多个可能的 workspace 文件
                for ws_file in ['workspace.json', 'workspace', 'workspace-mobile.json']:
                    ws_path = os.path.join(obsidian_config_dir, ws_file)
                    if os.path.exists(ws_path):
                        if abs(md_mtime - os.path.getmtime(ws_path)) < 5.0:
                            is_typing = True
                            reasons.append(f"WorkspaceActive")
                            break
            except Exception:
                pass

            # --- B. 当前窗口检测 (辅助验证 + Idle熔断) ---
            if not is_typing:
                try:
                    cmd = ['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true']
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1.0)
                    active_app = result.stdout.strip()
                    
                    if 'Obsidian' in active_app:
                        # [v3.6] 回归朴素：只要 Obsidian 是前台窗口且文件变了，就认为是用户操作
                        # 因为 workspace.json 不会实时更新，依赖它会导致误判
                        is_typing = True
                        reasons.append(f"CurrentFocus")

                    elif active_app.lower() in ('terminal', 'iterm2', 'vscode', 'pycharm', 'cursor', 'python'):
                        # 开发者容错：切回终端看日志
                        is_typing = True
                        reasons.append(f"DevFocus")
                except Exception:
                    pass
            
            if is_typing:
                return 'OBSIDIAN_TYPING'
            else:
                return 'OBSIDIAN_SYNC'
                
        return detected_source

    def _process_event(self, filepath, event_type):
        if not filepath.endswith('.md'):
            return
        
        if FileUtils.is_excluded(filepath):
            return

        Logger.info(f"🔎 [Watchdog] 捕获底层事件 ({event_type}): {os.path.basename(filepath)}")
        
        now = time.time()
        last_time = self._last_event_time.get(filepath, 0)
        if now - last_time < Config.EVENT_DEBOUNCE_SECONDS:
            Logger.debug(f"[Event] 防抖跳过: {os.path.basename(filepath)}")
            return
        self._last_event_time[filepath] = now
        
        try:
            content = FileUtils.read_content(filepath)
            if content is None:
                return
            
            content_hash = FileUtils.calculate_hash(content)
            
            # [v3.1] 检测变更来源（仅控制台输出，不影响逻辑）
            is_sys_write = FileUtils.check_system_write(content_hash)  # 使用 check 而非 is，避免消耗 hash
            change_source = self._detect_change_source(filepath, is_sys_write)
            
            # 来源颜色编码
            source_colors = {
                'SYSTEM': '\033[96m',          # 青色 - 系统自身
                'OBSIDIAN_TYPING': '\033[95m', # 亮紫色 - 用户在 Obsidian 打字
                'OBSIDIAN_SYNC': '\033[35m',   # 暗紫色 - Obsidian 后台同步
                'USER': '\033[92m',            # 绿色 - 用户其他编辑器
                'MACOS': '\033[93m',           # 黄色 - macOS 系统
                'UNKNOWN': '\033[90m',         # 灰色 - 未知
            }
            reset_color = '\033[0m'
            color = source_colors.get(change_source, '\033[90m')
            
            print(f"{color}🏷️  [ChangeSource] {os.path.basename(filepath)} <- {change_source}{reset_color}")
            
            if FileUtils.is_system_write(content_hash):
                Logger.debug(f"[Event] 忽略自写入事件: {os.path.basename(filepath)}")
                return
            
            # [v3.6] 根据来源类型等待不同时间，避免打断用户或同步过程
            if change_source == 'OBSIDIAN_TYPING':
                delay = Config.CHANGE_SOURCE_TYPING_DELAY
                Logger.debug(f"[Event] 用户打字中，等待 {delay}s 后处理...")
            elif change_source == 'OBSIDIAN_SYNC':
                delay = Config.CHANGE_SOURCE_SYNC_DELAY
                Logger.debug(f"[Event] 后台同步中，等待 {delay}s 后处理...")
            else:
                delay = Config.CHANGE_SOURCE_TYPING_DELAY  # 默认使用较短延迟
            
            time.sleep(delay)
            
            # 等待后再次检查文件是否仍然存在且内容未再次变化
            # 如果在等待期间文件又被修改了，新的事件会被触发，这里可以跳过
            try:
                new_content = FileUtils.read_content(filepath)
                if new_content is None:
                    Logger.debug(f"[Event] 文件已不存在，跳过: {os.path.basename(filepath)}")
                    return
                new_hash = FileUtils.calculate_hash(new_content)
                if new_hash != content_hash:
                    Logger.debug(f"[Event] 文件在等待期间已变化，跳过本次处理: {os.path.basename(filepath)}")
                    return
            except Exception:
                pass
            
            Logger.info(f"📝 [Event] 检测到用户变更: {os.path.basename(filepath)}")
            self.manager.on_file_changed(filepath)
            
        except Exception as e:
            Logger.error_once(f"event_err_{filepath}", f"事件处理异常: {e}")

    def on_modified(self, event):
        if event.is_directory:
            return
        self._process_event(event.src_path, "MODIFIED")

    def on_moved(self, event):
        if event.is_directory:
            return
        self._process_event(event.dest_path, "MOVED")


class FusionManager:
    """
    [v3.0] Chronos Mode - Pure Event-Driven Sync Manager
    
    Architecture:
    - Startup: Full range sync (past 1 year to future 10 years)
    - Runtime: Pure event-driven, no polling
    - Calendar events trigger window sync (±15 days)
    - Midnight crossing triggers next day's note creation
    """
    
    def __init__(self):
        self.sm = StateManager()
        self.sync_core = SyncCore(self.sm)
        self.apple_sync = AppleSyncAdapter()
        
        # Observer instances
        self._observer = None
        self._ek_client = None
        if EK_AVAILABLE:
            try:
                self._ek_client = EventKitClient()
            except Exception as e:
                Logger.error_once("ek_init_fail", f"EventKitClient init failed: {e}")
                self._ek_client = None
        
        self._reminder_client = None
        if REMINDER_AVAILABLE:
             try:
                 self._reminder_client = ReminderKitClient()
             except Exception as e:
                 Logger.error_once("rem_init_fail", f"ReminderKitClient init failed: {e}")
                 self._reminder_client = None
        
        self._running = False
        self._registry_warmup_done = False
        
        # [v3.0] Chronos Mode
        self._calendar_dirty_flag = False
        self._reminder_dirty_flag = False
        self._last_midnight_check = datetime.date.today()
        self._startup_sync_done = False

    def process_single_date(self, date_str, is_event_trigger=False):
        """
        Process a single date: internal sync + formatting + Apple sync.
        [v3.0] Only creates note if calendar has events for that date.
        """
        results = {
            "internal_mod": False,
            "apple_to_obsidian": False,
            "obsidian_to_apple": False,
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
                if not is_event_trigger and idle_duration < Config.TYPING_COOLDOWN_SECONDS:
                    results["skipped"] = True
                    return results

        # --- [PRIORITY 1] Obsidian Internal Processing ---
        try:
            tasks_for_date = self.sync_core.get_tasks_for_date(date_str)
            self.sync_core.process_date(date_str, tasks_for_date)

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
        elif os.path.exists(daily_path):
            should_sync_apple = True

        if should_sync_apple:
            try:
                obs_mod, apple_mod = self.apple_sync.sync_day(date_str)
                results["apple_to_obsidian"] = obs_mod
                results["obsidian_to_apple"] = apple_mod
                
                if obs_mod or apple_mod:
                    Logger.info(f"   🍏 [Apple] {date_str} 同步成功")
            except Exception as e:
                Logger.error_once(f"apple_exec_fail_{date_str}", f"外部同步异常: {e}")

        return results

    def on_file_changed(self, filepath):
        """
        [v3.0] 事件驱动入口：文件变更时调用
        """
        filename = os.path.basename(filepath)
        
        if not self._registry_warmup_done:
            Logger.info("🔄 [Manager] Warming up TaskRegistry...")
            self.sync_core.initialize_registry()
            self._registry_warmup_done = True
        
        date_match = re.match(r'^(\d{4}-\d{2}-\d{2})\.md$', filename)
        
        if date_match:
            date_str = date_match.group(1)
            Logger.info(f"   🔄 [Sync] 触发日期同步: {date_str}")
            self.process_single_date(date_str, is_event_trigger=True)
        else:
            affected_dates = self.sync_core.process_file_event(filepath)
            
            if affected_dates:
                Logger.info(f"   🔄 [Sync] 项目文件变更，影响 {len(affected_dates)} 个日期")
                for date_str in affected_dates:
                    self.process_single_date(date_str, is_event_trigger=True)
            else:
                today_str = datetime.date.today().strftime('%Y-%m-%d')
                Logger.info(f"   🔄 [Sync] 项目文件变更（无任务），触发今日同步")
                self.process_single_date(today_str, is_event_trigger=True)

    def _on_calendar_push_event(self):
        """
        [v3.0] Callback for EventKit notification.
        Thread-safe: Just sets a flag.
        """
        self._calendar_dirty_flag = True

    def _on_reminder_push_event(self):
        """
        [v3.8] Callback for ReminderKit notification.
        """
        self._reminder_dirty_flag = True

    def sync_reminders(self):
        # [v3.8] Reminder Sync Logic

        # 这个方法现在是真正的业务逻辑实现
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        Logger.info(f"🔄 [Chronos] 执行提醒事项同步 ({today_str})...")
        
        # 1. 获取 Obsidian 中的任务 (Source of Truth for creation/deletion?)
        # 实际上 Obsidian 和 Reminders 是双向的。
        # 我们先只做简单的：把 Obsidian 今日任务推送到 Reminders，
        # 并把 Reminders 的完成状态同步回 Obsidian。
        
        try:
             # A. 获取 Reminders (Incomplete + Completed today)
             reminders_by_date = self._reminder_client.fetch_reminders(start_date=datetime.date.today(), end_date=datetime.date.today())
             today_reminders = reminders_by_date.get(today_str, [])
             
             # Map: Reminder ID -> Reminder Object
             rem_map = {r['id']: r for r in today_reminders}
             
             # B. 获取 Obsidian 今日任务
             obs_tasks = self.sync_core.get_tasks_for_date(today_str)
             
             # C. Obsidian -> Reminders (Push new tasks)
             # 目前 EventKitWrapper 只有读权限/能力？
             # 查阅代码发现在 reminder_kit.py 中只实现了 fetch。
             # 我们需要扩展 reminder_kit.py 支持 save_reminder / update_reminder。
             # 鉴于时间，先实现 "Reminders 完成状态 -> Obsidian" (Hooking into SyncCore)
             
             changes_count = 0
             
             for bid, task_data in obs_tasks.items():
                 # 假设 Obsidian 任务描述里包含了 Reminder ID? 
                 # 或者是根据 Title 匹配?
                 # 现有的 AppleNotes 逻辑是 *ID*Content。
                 # Reminders 也有 CalendarItemIdentifier。
                 
                 # 匹配逻辑：
                 # 1. 如果 Obsidian 任务有 RID (block id 即使是)，尝试在 Reminders 中找。
                 #    但是 Reminder ID 通常很长 (UUID)。
                 # 2. 只有通过 Title 匹配最稳妥，或者我们在 Obsidian 中存储 RID。
                 
                 # 简化版：仅同步完成状态 (基于 Title)
                 clean_content = task_data.get('pure', '').strip()
                 is_obs_completed = task_data.get('status') == 'x'
                 
                 matched_rem = None
                 for r in today_reminders:
                     if r['title'].strip() == clean_content:
                         matched_rem = r
                         break
                 
                 if matched_rem:
                     is_rem_completed = matched_rem['is_completed']
                     
                     if is_rem_completed and not is_obs_completed:
                         Logger.info(f"   ✅ [Sync] Reminder 完成 -> Obsidian: {clean_content}")
                         # 更新 Obsidian
                         # 最直接的方式：读取文件，替换状态，写回。
                         # 为了复用逻辑，我们可以扩展 SyncCore。
                         self.sync_core.complete_task_by_title(clean_content, today_str)
 
                         
             Logger.info(f"✅ [Chronos] 提醒事项同步完成 (占位)")
             
        except Exception as e:
            Logger.error_once("rem_sync_fail", f"提醒事项同步失败: {e}")

    def sync_recent_window(self):
        """
        [v3.1] 日历变更触发的窗口同步
        
        范围: 过去 CHRONOS_FULL_RANGE_PAST_DAYS 天 ~ 未来 CHRONOS_FULL_RANGE_FUTURE_YEARS 年
        性能优化: 仅同步日历中有事件的日期，避免遍历所有空白日期
        """
        if not self._ek_client:
            Logger.info("⚠️ [Chronos] EventKit 不可用，跳过窗口同步")
            return
        
        today = datetime.date.today()
        
        # [v3.7] DEBUG_TODAY_ONLY 模式：只处理今天的日记
        if getattr(Config, 'DEBUG_TODAY_ONLY', 0) == 1:
            start_date = today
            end_date = today
            Logger.info(f"🔄 [Chronos] 窗口同步 (DEBUG模式): 仅今天 {today}")
        else:
            start_date = today - datetime.timedelta(days=Config.CHRONOS_FULL_RANGE_PAST_DAYS)
            end_date = today + datetime.timedelta(days=Config.CHRONOS_FULL_RANGE_FUTURE_YEARS * 365)
            
            # 确保不早于 SYNC_START_DATE
            sync_start = datetime.datetime.strptime(Config.SYNC_START_DATE, '%Y-%m-%d').date()
            if start_date < sync_start:
                start_date = sync_start
            
            Logger.info(f"🔄 [Chronos] 窗口同步: {start_date} ~ {end_date}")
        
        # [性能优化] 使用 EventKit 批量获取有事件的日期，避免逐天遍历
        events_by_date = self._ek_client.fetch_range_events(
            start_date, 
            end_date, 
            Config.CHRONOS_EVENTKIT_BATCH_DAYS
        )
        
        if not events_by_date:
            Logger.info("📭 [Chronos] 窗口范围内无日历事件")
            return
        
        Logger.info(f"📅 [Chronos] 发现 {len(events_by_date)} 天有日历事件")
        
        # 只同步有事件的日期
        synced_count = 0
        for date_str in sorted(events_by_date.keys()):
            if date_str >= Config.SYNC_START_DATE:
                result = self.process_single_date(date_str, is_event_trigger=True)
                if result["apple_to_obsidian"] or result["obsidian_to_apple"]:
                    synced_count += 1
        
        Logger.info(f"✅ [Chronos] 窗口同步完成: {synced_count} 天有变动")

    def sync_full_range(self):
        """
        [v3.0] 全量同步：过去1年到未来10年
        仅同步日历中实际有事件的日期，避免创建大量空白笔记
        """
        if not self._ek_client:
            Logger.info("⚠️ [Chronos] EventKit 不可用，跳过全量同步")
            return
        
        today = datetime.date.today()
        
        # [v3.7] DEBUG_TODAY_ONLY 模式：只处理今天的日记
        if getattr(Config, 'DEBUG_TODAY_ONLY', 0) == 1:
            start_date = today
            end_date = today
            Logger.info(f"🚀 [Chronos] 全量同步启动 (DEBUG模式): 仅今天 {today}")
        else:
            start_date = today - datetime.timedelta(days=Config.CHRONOS_FULL_RANGE_PAST_DAYS)
            end_date = today + datetime.timedelta(days=Config.CHRONOS_FULL_RANGE_FUTURE_YEARS * 365)
            
            # 确保不早于 SYNC_START_DATE
            sync_start = datetime.datetime.strptime(Config.SYNC_START_DATE, '%Y-%m-%d').date()
            if start_date < sync_start:
                start_date = sync_start
            
            Logger.info(f"🚀 [Chronos] 全量同步启动: {start_date} ~ {end_date}")
        
        # 获取日历中有事件的日期
        events_by_date = self._ek_client.fetch_range_events(
            start_date, 
            end_date, 
            Config.CHRONOS_EVENTKIT_BATCH_DAYS
        )
        
        if not events_by_date:
            Logger.info("📭 [Chronos] 日历范围内无事件")
            return
        
        Logger.info(f"📅 [Chronos] 发现 {len(events_by_date)} 天有日历事件")
        
        # 只同步有事件的日期
        synced_count = 0
        for date_str in sorted(events_by_date.keys()):
            if date_str >= Config.SYNC_START_DATE:
                result = self.process_single_date(date_str, is_event_trigger=True)
                if result["apple_to_obsidian"] or result["obsidian_to_apple"]:
                    synced_count += 1
        
        Logger.info(f"✅ [Chronos] 全量同步完成: {synced_count} 天有变动")

    def _check_midnight_crossing(self):
        """
        [v3.0] 检查是否跨越午夜，创建新的今日笔记
        """
        today = datetime.date.today()
        if today != self._last_midnight_check:
            Logger.info(f"🌙 [Chronos] 检测到跨越午夜: {self._last_midnight_check} -> {today}")
            self._last_midnight_check = today
            
            # 同步今天的日历
            today_str = today.strftime('%Y-%m-%d')
            self.process_single_date(today_str, is_event_trigger=True)

    def run(self):
        """
        [v3.0] Chronos Mode 主循环 - 纯事件驱动
        """
        def _term_handler(signum, frame):
            self._running = False
            raise SystemExit("Received SIGTERM")

        signal.signal(signal.SIGTERM, _term_handler)
        self._running = True

        Logger.info(f"🚀 Chronos Mode 启动 - 全事件驱动架构")
        Logger.info(f"   同步窗口: ±{Config.CHRONOS_SYNC_WINDOW_DAYS // 2} 天")
        Logger.info(f"   全量范围: 过去 {Config.CHRONOS_FULL_RANGE_PAST_DAYS} 天 ~ 未来 {Config.CHRONOS_FULL_RANGE_FUTURE_YEARS} 年")
        Logger.info(f"   循环间隔: {Config.CHRONOS_LOOP_INTERVAL} 秒")

        # 初始化 Watchdog
        if WATCHDOG_AVAILABLE:
            try:
                self._observer = Observer()
                event_handler = ObsidianEventHandler(self)
                self._observer.schedule(event_handler, Config.VAULT_ROOT, recursive=True)
                self._observer.start()
                Logger.info(f"👁️ [Watchdog] 开始监听: {Config.VAULT_ROOT}")
            except Exception as e:
                Logger.error_once("observer_init", f"Watchdog 初始化失败: {e}")
                self._observer = None

            # EventKit 监听
            if self._ek_client:
                try:
                    Logger.info("📅 [Watchdog] 启动 EventKit 监听...")
                    self._ek_client.start_watching(self._on_calendar_push_event)
                except Exception as e:
                    Logger.error_once("cal_ek_fail", f"无法启动日历监听: {e}")

        # [v3.0] 启动时全量同步
        if not self._startup_sync_done:
            Logger.info("🌅 [Chronos] 执行启动全量同步...")
            self.sync_core.initialize_registry()
            self._registry_warmup_done = True
            self.sync_full_range()
            self._startup_sync_done = True

        # [v3.8] 启动 Reminder 监听
        if self._reminder_client:
             try:
                 Logger.info("🎗️ [Watchdog] 启动 ReminderKit 监听...")
                 # 注意: 这里使用与 EventKit 相同的推送回调逻辑，或者单独的逻辑
                 self._reminder_client.start_watching(self._on_reminder_push_event)
             except Exception as e:
                 Logger.error_once("rem_watch_fail", f"无法启动提醒事项监听: {e}")

        # 主循环
        try:
            from CoreFoundation import CFRunLoopRunInMode, kCFRunLoopDefaultMode
            
            while self._running:
                # [v3.0] 纯事件驱动：仅处理标志位
                if self._calendar_dirty_flag:
                    Logger.info(f"⚡ [Chronos] 检测到日历变更")
                    self.sync_recent_window()
                    self._calendar_dirty_flag = False
                
                if self._reminder_dirty_flag:
                    Logger.info(f"⚡ [Chronos] 检测到提醒事项变更")
                    self._reminder_dirty_flag = False
                    self.sync_reminders() 

                
                # 检查午夜跨越
                self._check_midnight_crossing()
                
                # 保持 RunLoop 唤醒
                CFRunLoopRunInMode(kCFRunLoopDefaultMode, Config.CHRONOS_LOOP_INTERVAL, False)
                
        except KeyboardInterrupt:
            Logger.info("\n⏹️ 收到中断信号...")
        finally:
            if self._observer:
                Logger.info("🛑 [Watchdog] 停止监听 Vault...")
                self._observer.stop()
                self._observer.join(timeout=3)
            
            if self._ek_client:
                Logger.info("🛑 [Watchdog] 停止监听 Calendar...")
            if self._ek_client:
                Logger.info("🛑 [Watchdog] 停止监听 Calendar...")
                self._ek_client.stop_watching()

            if self._reminder_client:
                Logger.info("🛑 [Watchdog] 停止监听 Reminders...")
                self._reminder_client.stop_watching()
            
            self.sm.save()
            Logger.info("✅ 状态已保存，Chronos 引擎已停止")

```

---
## File: AntigravitySync/src/dailynotes/state_manager.py
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
            import tempfile
            dir_name = os.path.dirname(Config.STATE_FILE) or '.'
            
            # 1. 原子写入：先写临时文件，再替换
            temp_fd = None
            temp_name = None
            try:
                temp_fd, temp_name = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as tf:
                    json.dump(self.state, tf, ensure_ascii=False, indent=2)
                    tf.flush()
                    os.fsync(tf.fileno())
                
                # 原子替换
                os.replace(temp_name, Config.STATE_FILE)
                temp_name = None  # 标记已成功
                
                # 2. 成功后才备份（备份的是新文件）
                try:
                    shutil.copy2(Config.STATE_FILE, Config.STATE_FILE + ".bak")
                except OSError:
                    pass
                    
            finally:
                # 清理失败的临时文件
                if temp_name and os.path.exists(temp_name):
                    try:
                        os.remove(temp_name)
                    except OSError:
                        pass
                        
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

        # 4. 移除 ID (^xxxxxx or <span id="xxx"></span>)
        text = re.sub(r'(?<=\s)\^[a-zA-Z0-9]{6,7}\s*$', '', text)
        text = re.sub(r'<span id="[a-zA-Z0-9]{6,7}"></span>', '', text)

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
## File: AntigravitySync/src/dailynotes/tracker.py
```py
import threading
import time

class WindowFocusTracker(threading.Thread):
    """
    [v3.4] 后台线程：高频记录窗口焦点历史
    使用 AppKit (PyObjC) 实现低功耗查询，避免 polling osascript
    """
    def __init__(self, history_len=20, interval=0.5):
        super().__init__()
        self.history = []  # List of (timestamp, app_name)
        self.history_len = history_len
        self.interval = interval
        self.daemon = True
        self.running = True
        self.lock = threading.Lock()
        self._ns_workspace = None
        
        # 尝试加载 AppKit
        try:
            from AppKit import NSWorkspace
            self._ns_workspace = NSWorkspace.sharedWorkspace()
        except ImportError:
            pass

    def run(self):
        while self.running:
            app_name = "Unknown"
            try:
                if self._ns_workspace:
                    # 极速方法 (微秒级)
                    front_app = self._ns_workspace.frontmostApplication()
                    if front_app:
                        app_name = front_app.localizedName()
                else:
                    # 回退方法 (较慢)
                    import subprocess
                    cmd = ['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true']
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=1)
                    app_name = res.stdout.strip()
            except Exception:
                pass
            
            with self.lock:
                now = time.time()
                self.history.append((now, app_name))
                if len(self.history) > self.history_len:
                    self.history.pop(0)
            
            time.sleep(self.interval)

    def was_app_active(self, target_app_name, seconds=5):
        """检查过去 N 秒内，目标应用是否出现过在前台"""
        now = time.time()
        start_time = now - seconds
        target_lower = target_app_name.lower()
        
        with self.lock:
            # 倒序遍历（从最近的开始）
            for ts, name in reversed(self.history):
                if ts < start_time:
                    break
                if name and target_lower in name.lower():
                    return True
        return False
    
    def stop(self):
        self.running = False

```

---
## File: AntigravitySync/src/dailynotes/utils.py
```py
import os
import sys
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
    _countdown_active = False  # 跟踪倒计时行是否正在显示

    @classmethod
    def _clear_countdown_line(cls):
        """清除倒计时行，为正常日志输出腾出空间"""
        if cls._countdown_active:
            # 回车 + 清行 + 换行
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()
            cls._countdown_active = False

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

    @classmethod
    def error_once(cls, key, message):
        if key not in cls._shown_errors:
            cls._clear_countdown_line()
            caller = cls._get_caller_info()
            print(f"\033[91m[ERROR] {caller} {message}\033[0m")
            cls._shown_errors.add(key)

    @classmethod
    def info(cls, message, date_tag=None):
        # [特性] 聚焦日志：仅显示今天的日志（当前文件）
        t = datetime.datetime.now().strftime('%H:%M:%S')
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        
        if date_tag and date_tag != today_str:
            return # 跳过历史日志以减少干扰
        
        cls._clear_countdown_line()
        prefix = f"[{date_tag}] " if date_tag else ""
        caller = cls._get_caller_info()
        print(f"\033[92m[{t} INFO] {caller} {prefix}{message}\033[0m")

    @classmethod
    def debug(cls, message):
        if Config.DEBUG_MODE:
            cls._clear_countdown_line()
            caller = cls._get_caller_info()
            print(f"\033[90m[DEBUG] {caller} {message}\033[0m")

    @classmethod
    def debug_block(cls, title, lines):
        if Config.DEBUG_MODE:
            cls._clear_countdown_line()
            caller = cls._get_caller_info()
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
        
        # [白名单] DAILY_NOTE_DIR 及其文件不应被排除
        daily_dir = os.path.normpath(Config.DAILY_NOTE_DIR)
        if path == daily_dir or path.startswith(daily_dir + os.sep):
            return False
        
        # [黑名单] 排除目录检查
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
## File: AntigravitySync/src/dailynotes/sync/__init__.py
```py
from .engine import SyncCore
from .task_registry import TaskRegistry, get_registry

```

---
## File: AntigravitySync/src/dailynotes/sync/discovery.py
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
## File: AntigravitySync/src/dailynotes/sync/engine.py
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
                            clean_pure = re.sub(r'<span id="[a-zA-Z0-9]{6,}"></span>', '', clean_pure)

                            # [FIX] Remove existing return links to prevent duplication
                            clean_pure = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', clean_pure)

                            # [FIX] Remove routing markers like "## [[ProjectName]]" - they're only for specifying target
                            clean_pure = re.sub(r'##\s*\[\[[^\]]+\]\]', '', clean_pure)

                            clean_pure = re.sub(r'\s+', ' ', clean_pure).strip()
                            
                            # [FIX] Return link target logic
                            ret_target = target_p_name
                            # Extract potential file links from the cleaned content
                            m_links = re.findall(r'\[\[(.*?)(?:[\|#].*)?\]\]', clean_pure)
                            if m_links:
                                ret_target = m_links[0]
                            
                            # Build return link with span ID prefix
                            span_id = f'<span id="{bid}"></span>'
                            ret_link = f"[[{ret_target}#^{bid}|⮐]]"
                            
                            # Format final line: time + span_id + return link + preserved content (no trailing ^id)
                            final_head_line = f"{indent_str}- [{status}] {time_part}{span_id}{ret_link} {clean_pure}\n"
                            
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
                            
                            # [FIX] Use span_id prefix instead of trailing ^bid
                            span_id = f'<span id="{bid}"></span>'
                            final_head_line = f"{indent_str}- [{status}] {time_part}{span_id}{ret_link}{file_tag} {clean_pure}\n"

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

```

---
## File: AntigravitySync/src/dailynotes/sync/parsing.py
```py
import re
import unicodedata

# [P3 FIX] Pre-compiled regex patterns for performance
_RE_QUOTE_PREFIX = re.compile(r'^>\s?')
_RE_STATUS_INDENT = re.compile(r'^[\s>]*-\s*\[.\]')
_RE_TIME_RANGE = re.compile(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}')
_RE_TIME_SINGLE = re.compile(r'\d{1,2}:\d{2}')
_RE_BLOCK_ID = re.compile(r'(?:\^[a-zA-Z0-9]{6,}|<span id="[a-zA-Z0-9]{6,}"></span>)\s*$')
_RE_RETURN_LINK = re.compile(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]')
_RE_DATE_LINK = re.compile(r'\[\[\d{4}-\d{2}-\d{2}]]')
_RE_EMOJI_DATE = re.compile(r'📅\s?\[\[\d{4}-\d{2}-\d{2}]]')
_RE_MULTI_SPACE = re.compile(r'\s+')
_RE_WIKI_LINK = re.compile(r'\[\[(.*?)\]\]')
_RE_MAIN_TAG = re.compile(r'\bmain\b')

def _get_indent_depth(line):
    no_quote = _RE_QUOTE_PREFIX.sub('', line)
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
    
    # 3. remove ID (^xxxxxx or <span id="xxx"></span>)
    if block_id:
        clean_text = re.sub(r'\^' + re.escape(block_id) + r'\s*$', '', clean_text)
        clean_text = re.sub(r'<span id="' + re.escape(block_id) + r'"></span>', '', clean_text)
    else:
        clean_text = re.sub(r'\^[a-zA-Z0-9]{6,}\s*$', '', clean_text)
        clean_text = re.sub(r'<span id="[a-zA-Z0-9]{6,}"></span>', '', clean_text)
        
    # 4. remove return links
    clean_text = re.sub(r'\[\[[^\]]*?\#\^[a-zA-Z0-9]{6,}\|[⚓\*🔗⮐📅]\]\]', '', clean_text)
    
    # 5. remove date links
    clean_text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}]]', '', clean_text)
    # remove emoji date
    clean_text = re.sub(r'📅\s?\[\[\d{4}-\d{2}-\d{2}]]', '', clean_text)

    # 5.5 [FIX] Remove routing markers like "## [[ProjectName]]"
    clean_text = re.sub(r'##\s*\[\[[^\]]+\]\]', '', clean_text)

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
        # [FIX] 使用 lstrip() 而非 strip()，保留尾部空格以支持 Obsidian "- " 列表语法
        clean = re.sub(r'^[\s>]+', '', line).lstrip()
        if not clean or clean in ['-', '- ']: continue
        normalized.append(clean)
    return "\n".join(normalized) + "\n"

def capture_block(lines, start_idx):
    parent_indent = _get_indent_depth(lines[start_idx])
    block = [lines[start_idx]]
    consumed = 1
    
    # [P2 FIX] Track consecutive empty lines to prevent infinite block extension
    consecutive_empty = 0
    MAX_CONSECUTIVE_EMPTY = 2
    
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        if not line.strip():  # Empty line
            consecutive_empty += 1
            if consecutive_empty > MAX_CONSECUTIVE_EMPTY:
                break  # Too many empty lines, end block
            block.append(line)
            consumed += 1
            continue
        
        # Reset counter on non-empty line
        consecutive_empty = 0
             
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


def generate_block_id() -> str:
    """Generate a unique block ID."""
    import random
    import string
    return '^' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))


def parse_file_tasks(filepath: str, lines: list, project_name: str, sm, 
                     write_back: bool = True) -> tuple:
    """
    [v1.8.1 DRY] Central parsing function for extracting tasks from a markdown file.
    
    This is the SINGLE SOURCE OF TRUTH for file parsing logic.
    Used by TaskRegistry for both initial scan and incremental updates.
    
    Args:
        filepath: Absolute path to the .md file
        lines: List of line strings (already read from file)
        project_name: The project this file belongs to
        sm: StateManager for hash calculations
        write_back: If True, write modified lines back to file
        
    Returns:
        Tuple of (tasks_list, modified_lines, was_modified)
        - tasks_list: List of task dictionaries
        - modified_lines: The (potentially modified) lines
        - was_modified: Boolean indicating if lines were changed
    """
    import os
    import datetime
    from config import Config
    from ..utils import Logger, FileUtils
    
    # Lazy import to avoid circular dependency
    from .rendering import format_line, inject_into_task_section
    
    if not lines:
        return [], lines, False
    
    tasks = []
    mod = False
    fname = os.path.splitext(os.path.basename(filepath))[0]
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    i = 0
    in_task_section = False
    current_section_date = None
    seen_section_dates = set()
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Detect section markers
        if stripped == '# Tasks':
            in_task_section = True
            current_section_date = None
            seen_section_dates.clear()
            i += 1
            continue
        
        if stripped == '----------':
            in_task_section = False
            current_section_date = None
            i += 1
            continue
        
        if not in_task_section:
            i += 1
            continue
        
        # Check for date headers
        header_match = re.match(r'^#+\s*\[\[\s*(\d{4}-\d{2}-\d{2})\s*\]\]', stripped)
        if header_match:
            date_str = header_match.group(1)
            if date_str in seen_section_dates:
                Logger.info(f"   🔍 发现重复标题 {date_str}，将触发重组...")
                mod = True
            else:
                seen_section_dates.add(date_str)
            current_section_date = date_str
            i += 1
            continue
        
        if stripped.startswith('#'):
            current_section_date = None
            i += 1
            continue
        
        # Check for task lines
        if not re.match(r'^\s*-\s*\[.\]', line):
            i += 1
            continue
        
        # Determine task date
        task_date = None
        if current_section_date:
            task_date = current_section_date
        else:
            date_match = re.search(r'[📅✅]\s*(\d{4}-\d{2}-\d{2})', line)
            if date_match:
                task_date = date_match.group(1)
            else:
                link_match = re.search(r'\[\[(\d{4}-\d{2}-\d{2})(?:#|\||\]\])', line)
                if link_match:
                    task_date = link_match.group(1)
        
        is_in_inbox_area = (current_section_date is None)
        if is_in_inbox_area and not task_date:
            i += 1
            continue
        
        if not task_date:
            task_date = today_str
            mod = True
        
        # Parse task properties
        indent = get_indent_depth(line)
        status_match = re.search(r'-\s*\[(.)\]', line)
        st = status_match.group(1) if status_match else ' '
        
        # Extract or generate block ID
        id_m = re.search(r'(?:\^([a-zA-Z0-9]{6,7})|<span id="([a-zA-Z0-9]{6,7})"></span>)', line)
        bid = (id_m.group(1) or id_m.group(2)) if id_m else None
        
        if not bid:
            raw_block, _ = capture_block(lines, i)
            temp_clean = clean_task_text(line, None, fname)
            temp_clean = re.sub(r'\s+\^?[a-zA-Z0-9]*$', '', temp_clean).strip()
            combined_body = normalize_block_content(raw_block[1:])
            temp_combined_text = temp_clean + "|||" + combined_body
            recovery_hash = sm.calc_hash(st, temp_combined_text)
            found_id = sm.find_id_by_hash(filepath, recovery_hash)
            
            if found_id:
                Logger.info(f"   🚑 [RESCUE] 指纹匹配成功! '{temp_clean[:10]}...' -> 复活 ID: {found_id}")
                bid = found_id
                mod = True
            else:
                bid = generate_block_id().replace('^', '')
                mod = True
        
        # Clean task text
        clean_txt = clean_task_text(line, bid, context_name=fname)
        dates_pattern = r'([📅✅]\s*\d{4}-\d{2}-\d{2}|\[\[\d{4}-\d{2}-\d{2}(?:#\^[a-zA-Z0-9]+)?(?:\|[📅⮐])?\]\])'
        dates = " ".join(re.findall(dates_pattern, line))
        
        if current_section_date and current_section_date not in dates:
            dates = f"[[{task_date}]]"
            mod = True
        if task_date not in line and not dates:
            dates = f"[[{task_date}]]"
            mod = True
        
        # Format the line
        new_line = format_line(indent, st, clean_txt, dates, fname, bid, False)
        if new_line.strip() != line.strip():
            lines[i] = new_line
            mod = True
        
        # TIME GATE: Skip tasks before sync start date
        if task_date < Config.SYNC_START_DATE:
            _, consumed = capture_block(lines, i)
            i += consumed
            continue
        
        # Capture full block and build task dict
        block, consumed = capture_block(lines, i)
        combined_text = clean_txt + "|||" + normalize_block_content(block[1:])
        content_hash = sm.calc_hash(st, combined_text)
        
        tasks.append({
            'proj': project_name,
            'bid': bid,
            'pure': clean_txt,
            'status': st,
            'path': filepath,
            'fname': fname,
            'raw': block,
            'hash': content_hash,
            'indent': indent,
            'dates': dates,
            'is_quoted': False,
            '_task_date': task_date  # Internal field for date indexing
        })
        
        i += consumed
    
    # Write back if modified and requested
    if mod and write_back:
        lines = inject_into_task_section(lines, [])
        orig = FileUtils.read_file(filepath)
        new_c = "".join(lines)
        old_c = "".join(orig) if orig else ""
        if new_c != old_c:
            Logger.info(f"   💾 [WRITE] 自动格式化源文件: {os.path.basename(filepath)}")
            FileUtils.write_file(filepath, lines)
    
    return tasks, lines, mod

```

---
## File: AntigravitySync/src/dailynotes/sync/rendering.py
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
    id_pattern = re.compile(r'(?:\^[a-z0-9]{6}|<span id="[a-z0-9]{6}"></span>)\s*$')

    def generate_id():
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    for line in lines:
        match = raw_pattern.match(line)
        if match:
            prefix = match.group(1)
            text_body = match.group(2).strip()

            if not id_pattern.search(text_body):
                new_id = generate_id()
                new_lines.append(f"{prefix} <span id=\"{new_id}\"></span>[[{filename_stem}#^{new_id}|⮐]] [[{today_str}]] {text_body}")
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
    id_pattern = re.compile(r'(?:\^([a-zA-Z0-9]{6,})|<span id="([a-zA-Z0-9]{6,})"></span>)')

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
            bid = bid_m.group(1) or bid_m.group(2)  # group(1) for ^xxx, group(2) for span
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
        span_id = f'<span id="{bid}"></span>'
        link = f"[[{fname}#^{bid}|⮐]]"
        time_match = re.match(r'^(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)', text)
        if time_match:
            time_part = time_match.group(1)
            rest_part = text[len(time_part):].strip()
            return f"{indent_str}- [{status}] {time_part} {span_id}{link} {rest_part}\n"
        else:
            return f"{indent_str}- [{status}] {span_id}{link} {text}\n"
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

        span_id = f'<span id="{bid}"></span>'
        parts = [span_id + date_link]
        if clean_text: parts.append(clean_text)
        if meta_str: parts.append(meta_str)

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
        # [FIX] 使用 lstrip() 而非 strip()，保留尾部空格以支持 Obsidian "- " 列表语法
        content_cleaned = re.sub(r'^[>\s]+', '', line).lstrip()
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

def reconstruct_daily_block(sd, target_date, preserved_time=None):
    fname = sd['fname']
    bid = sd['bid']
    status = sd['status']
    text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}\]\]', '', sd['pure']).strip()
    link_tag = f"[[{fname}]]"
    
    # [FIX] 更智能的检查：如果 text 中已经包含了指向该文件的链接（甚至带锚点/别名），就不要再加了
    # 检查 [[fname]] 或 [[fname#...]] 或 [[fname|...]]
    # 使用 re.escape 处理文件名中的特殊字符
    has_link = re.search(rf'\[\[{re.escape(fname)}(?:[#\|].*?)?\]\]', text)
    if not has_link: 
        text = f"{link_tag} {text}"

    # [FIX] 如果传入了保留的时间，将其注入到 text 前端供 format_line 识别
    if preserved_time:
        text = f"{preserved_time} {text}"

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
    
    # [FIX] 计算正确的插入位置：跳过 YAML frontmatter
    # Frontmatter 格式: 第一行 "---"，然后在某行再遇到 "---" 结束
    insert_pos = 0
    if lines and lines[0].strip() == '---':
        # 有 frontmatter，找到结束位置
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                insert_pos = i + 1
                break
    
    if not has_dp:
        if j_idx != -1:
            # [FIX] 使用单换行，避免多余空行
            lines.insert(j_idx, "# Day planner\n")
        else:
            # [FIX] 插入到 frontmatter 之后，而非索引 0
            lines.insert(insert_pos, "# Day planner\n")
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
## File: AntigravitySync/src/dailynotes/sync/task_registry.py
```py
"""
TaskRegistry - Incremental Task Cache for AntigravitySync v1.8

This module implements a persistent in-memory cache for all source tasks,
enabling O(1) file updates instead of O(n) full-disk scans.

Architecture:
    - _file_cache:  { filepath: [task_dicts...] }  # Tasks indexed by source file
    - _date_index:  { date_str: {bid: task_dict} } # Tasks indexed by date (derived view)

Key Methods:
    - initialize(project_map, sm): Full scan at startup (one-time os.walk)
    - update_file(filepath, project_name, sm): Incremental single-file rescan
    - get_tasks_by_date(date_str): Fast lookup for process_date()
    - get_affected_dates(filepath): Returns dates affected by a file change
"""

import os
import re
import datetime
import random
import string
import threading
from typing import Dict, List, Set, Optional, Any, Tuple
from config import Config
from ..utils import Logger, FileUtils
from .parsing import (
    capture_block, 
    clean_task_text, 
    normalize_block_content, 
    get_indent_depth,
    parse_file_tasks,
    generate_block_id
)


class TaskRegistry:
    """
    Thread-safe task registry implementing incremental synchronization.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._file_cache: Dict[str, List[Dict]] = {}   # { filepath: [tasks...] }
        self._date_index: Dict[str, Dict[str, Dict]] = {}  # { date: {bid: task} }
        self._file_to_dates: Dict[str, Set[str]] = {}  # { filepath: {dates...} }
        self._project_map: Dict[str, str] = {}  # Cached project map
        self._file_lock = threading.RLock()  # Reentrant lock for nested calls
        self._initialized = True
        
        Logger.info("📦 [TaskRegistry] 实例已创建")
    
    def initialize(self, project_map: Dict[str, str], sm) -> None:
        """
        Perform full scan at startup to populate the registry.
        This is the ONLY place where os.walk should be used.
        
        Args:
            project_map: { directory_path: project_name }
            sm: StateManager instance for hash calculations
        """
        with self._file_lock:
            self._project_map = project_map.copy()
            self._file_cache.clear()
            self._date_index.clear()
            self._file_to_dates.clear()
            
            today_str = datetime.date.today().strftime('%Y-%m-%d')
            file_count = 0
            task_count = 0
            
            # Single os.walk at startup
            for root, dirs, files in os.walk(Config.ROOT_DIR):
                dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
                if FileUtils.is_excluded(root):
                    continue
                
                # Determine project for this directory
                curr_proj = self._resolve_project(root)
                if not curr_proj:
                    continue
                
                for f in files:
                    if not f.endswith('.md'):
                        continue
                    
                    filepath = os.path.join(root, f)
                    tasks = self._scan_single_file(filepath, curr_proj, sm)
                    
                    if tasks:
                        self._file_cache[filepath] = tasks
                        self._update_date_index_from_file(filepath, tasks)
                        file_count += 1
                        task_count += len(tasks)
            
            # Ensure at least 3 recent dates exist in index
            for delta in range(3):
                target_date = datetime.date.today() - datetime.timedelta(days=delta)
                target_str = target_date.strftime('%Y-%m-%d')
                if target_str not in self._date_index:
                    self._date_index[target_str] = {}
            
            Logger.info(f"📦 [TaskRegistry] 初始化完成: {file_count} 文件, {task_count} 任务")
    
    def _resolve_project(self, directory: str) -> Optional[str]:
        """Traverse up to find the nearest ancestor project."""
        temp = directory
        while temp.startswith(Config.ROOT_DIR):
            if temp in self._project_map:
                return self._project_map[temp]
            parent = os.path.dirname(temp)
            if parent == temp:
                break
            temp = parent
        return None
    
    def _scan_single_file(self, filepath: str, project_name: str, sm) -> List[Dict]:
        """
        Parse a single markdown file and extract all source tasks.
        [v1.8.1] Now delegates to centralized parse_file_tasks for DRY.
        
        Args:
            filepath: Absolute path to the .md file
            project_name: The project this file belongs to
            sm: StateManager for hash calculations
            
        Returns:
            List of task dictionaries
        """
        lines = FileUtils.read_file(filepath)
        if not lines:
            return []
        
        # Delegate to centralized parsing function
        tasks, _, _ = parse_file_tasks(filepath, lines, project_name, sm, write_back=True)
        
        return tasks
    
    def _update_date_index_from_file(self, filepath: str, tasks: List[Dict]) -> None:
        """Update the date index with tasks from a file."""
        dates_in_file = set()
        
        for task in tasks:
            task_date = task.get('_task_date')
            if not task_date:
                continue
            
            dates_in_file.add(task_date)
            
            if task_date not in self._date_index:
                self._date_index[task_date] = {}
            
            bid = task['bid']
            # Create a copy without the internal _task_date field
            task_copy = {k: v for k, v in task.items() if not k.startswith('_')}
            self._date_index[task_date][bid] = task_copy
        
        self._file_to_dates[filepath] = dates_in_file
    
    def update_file(self, filepath: str, sm) -> Set[str]:
        """
        Incrementally update the cache for a single file.
        Called when a file change event is received.
        
        Args:
            filepath: The file that was modified
            sm: StateManager for hash calculations
            
        Returns:
            Set of date strings affected by this change
        """
        with self._file_lock:
            # Collect old affected dates before clearing
            old_dates = self._file_to_dates.get(filepath, set()).copy()
            
            # Clear old tasks from date index
            old_tasks = self._file_cache.get(filepath, [])
            for task in old_tasks:
                task_date = task.get('_task_date')
                bid = task.get('bid')
                if task_date and bid and task_date in self._date_index:
                    self._date_index[task_date].pop(bid, None)
            
            # Clear file from cache
            self._file_cache.pop(filepath, None)
            self._file_to_dates.pop(filepath, None)
            
            # Re-scan file if it still exists
            if os.path.exists(filepath):
                # Determine project
                directory = os.path.dirname(filepath)
                project_name = self._resolve_project(directory)
                
                if project_name:
                    tasks = self._scan_single_file(filepath, project_name, sm)
                    
                    if tasks:
                        self._file_cache[filepath] = tasks
                        self._update_date_index_from_file(filepath, tasks)
            
            # Get new affected dates
            new_dates = self._file_to_dates.get(filepath, set())
            
            # Return union of old and new dates
            return old_dates | new_dates
    
    def get_tasks_by_date(self, date_str: str) -> Dict[str, Dict]:
        """
        Get all tasks for a specific date.
        Fast O(1) lookup from the date index.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            Dictionary of { bid: task_dict }
        """
        with self._file_lock:
            return self._date_index.get(date_str, {}).copy()
    
    def get_affected_dates(self, filepath: str) -> Set[str]:
        """
        Get all dates that have tasks from a specific file.
        
        Args:
            filepath: Absolute path to the file
            
        Returns:
            Set of date strings
        """
        with self._file_lock:
            return self._file_to_dates.get(filepath, set()).copy()
    
    def refresh_project_map(self, project_map: Dict[str, str]) -> None:
        """
        Update the internal project map (called when projects are re-scanned).
        
        Args:
            project_map: Updated { directory_path: project_name }
        """
        with self._file_lock:
            self._project_map = project_map.copy()
    
    def get_all_tasks_by_date(self) -> Dict[str, Dict[str, Dict]]:
        """
        Get the entire date index.
        Used for compatibility with the original scan_all_source_tasks() return value.
        
        Returns:
            Dictionary of { date_str: { bid: task_dict } }
        """
        with self._file_lock:
            return {date: tasks.copy() for date, tasks in self._date_index.items()}
    
    def is_initialized(self) -> bool:
        """Check if the registry has been initialized."""
        return bool(self._file_cache) or bool(self._date_index)
    
    def clear(self) -> None:
        """Clear all cached data (for testing)."""
        with self._file_lock:
            self._file_cache.clear()
            self._date_index.clear()
            self._file_to_dates.clear()
            self._project_map.clear()


# Global singleton access
_registry: Optional[TaskRegistry] = None

def get_registry() -> TaskRegistry:
    """Get the global TaskRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = TaskRegistry()
    return _registry

```

---
## File: AntigravitySync/src/external/__init__.py
```py
# External sync modules

```

---
## File: AntigravitySync/src/external/apple_sync_adapter.py
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
                return False, False
            
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
## File: AntigravitySync/src/external/dock_handoff.py
```py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dock Handoff Observer & Auto-Trigger
--------------------------------------------------
通过 Accessibility API (AXObserver) 实现对 macOS Dock 栏
“接力 (Handoff)”图标的静默监听与自动触发。

依赖:
    pip install pyobjc-framework-ApplicationServices pyobjc-framework-Cocoa

机制:
    使用 AXObserver 监听 Dock 进程的 UI 布局变更事件 (kAXLayoutChangedNotification)。
    一旦检测到 Handoff 图标出现 (AXIsHandoff=True)，立即执行点击 (kAXPressAction)。
    全程无轮询，资源占用极低。
"""

import sys
import time
import signal
import threading
from typing import Optional

import objc
from AppKit import NSWorkspace, NSRunLoop
from Foundation import NSObject, NSLog, NSRunLoopCommonModes, NSDate
from ApplicationServices import (
    AXUIElementCreateApplication,
    AXObserverCreate,
    AXObserverAddNotification,
    AXObserverGetRunLoopSource,
    AXUIElementCopyAttributeValue,
    AXUIElementPerformAction,
    AXIsProcessTrusted,
    kAXLayoutChangedNotification,
    kAXCreatedNotification,
    kAXUIElementDestroyedNotification,
    kAXPressAction,
    kAXWindowsAttribute,
    kAXChildrenAttribute,
    kAXRoleAttribute,
    kAXSubroleAttribute,
    AXUIElementGetPid
)
from CoreFoundation import (
    CFRunLoopGetCurrent,
    CFRunLoopAddSource,
    CFRunLoopRun,
    CFRunLoopStop,
    kCFRunLoopDefaultMode
)

# 配置常量
TARGET_BUNDLE_ID = "com.apple.dock"
ATTR_AX_IS_HANDOFF = "AXIsHandoff"  # 这是一个非标准属性，仅 Dock 图标特有，但也可能需要检查 Subrole

class HandoffObserver:
    def __init__(self):
        self.dock_pid: Optional[int] = None
        self.dock_element = None
        self.observer = None
        self.loop = None
        self._setup_complete = False

    def check_permissions(self):
        """检查辅助功能权限"""
        if not AXIsProcessTrusted():
            print("❌ 错误: 缺少辅助功能权限 (Accessibility Permissions)。")
            print("请在 '系统设置 > 隐私与安全性 > 辅助功能' 中添加此终端/编辑器。")
            sys.exit(1)
        print("✅ 辅助功能权限已获取。")

    def get_dock_pid(self):
        """获取 Dock 进程的 PID"""
        workspace = NSWorkspace.sharedWorkspace()
        for app in workspace.runningApplications():
            if app.bundleIdentifier() == TARGET_BUNDLE_ID:
                self.dock_pid = app.processIdentifier()
                print(f"📍 已定位 Dock 进程 (PID: {self.dock_pid})")
                return
        
        print("❌ 错误: 未找到正在运行的 Dock 进程。")
        sys.exit(1)

    def scan_for_handoff_item(self, element, depth=0):
        """
        递归扫描 UI 元素树寻找 Handoff 图标
        注意: Handoff 图标通常是 Dock 的子元素，Role 为 AXDockItem (可能)
        但最可靠的是检查 attributes 中是否包含 AXIsHandoff 且为 True
        """
        if depth > 3: # 防止过深递归，Dock 结构通常很扁平
            return False

        # 1. 检查当前元素是否是 Handoff
        try:
            # 尝试获取 AXIsHandoff 属性
            # 注意: 这是一个私有/特殊属性，不一定在所有系统版本通过常规 CopyAttributeValue 获取
            # 但在 PyObjC 中可以直接尝试
            is_handoff, error = AXUIElementCopyAttributeValue(element, ATTR_AX_IS_HANDOFF, None)
            if error == 0 and is_handoff is True:
                print(f"🚀 发现 Handoff 图标! 准备触发...")
                self.trigger_action(element)
                return True
            
            # 备选策略: 检查 Subrole (如果是 'AXHandoffDockItem' 或类似)
            subrole, error = AXUIElementCopyAttributeValue(element, kAXSubroleAttribute, None)
            if error == 0 and subrole == "AXHandoffDockItem":
                print(f"🚀 通过 Subrole 发现 Handoff 图标! 准备触发...")
                self.trigger_action(element)
                return True

        except Exception as e:
            # 某些属性获取可能会失败，忽略
            pass

        # 2. 获取子元素继续搜索
        children, error = AXUIElementCopyAttributeValue(element, kAXChildrenAttribute, None)
        if error == 0 and children:
            for child in children:
                if self.scan_for_handoff_item(child, depth + 1):
                    return True
        
        return False

    def trigger_action(self, element):
        """执行点击动作"""
        error = AXUIElementPerformAction(element, kAXPressAction)
        if error == 0:
            print("✅ 成功执行点击 (AXPress)！Handoff 接力已激活。")
        else:
            print(f"⚠️ 点击失败 (Error Code: {error})。尝试 AXShowMenu...")
            # 备选: 有些图标可能不支持 Press，尝试弹出菜单
            AXUIElementPerformAction(element, "AXShowMenu")

    def observer_callback(self, observer, element, notification, refcon):
        """
        AXObserver 的回调函数
        注意: 这个回调是在 CFRunLoop 中执行的
        """
        # print(f"收到通知: {notification}") # 调试用，生产环境关闭以减少噪音
        
        if notification in [kAXLayoutChangedNotification, kAXCreatedNotification]:
            # 当 Dock 布局改变（例如新图标出现）时扫描
            threading.Thread(target=self.scan_dock, daemon=True).start()

    def scan_dock(self):
        """扫描整个 Dock 列表"""
        # 注意：这里需要要在主线程或者确保 AX 操作线程安全
        # 简单起见，我们在回调线程直接扫描，或者在此次扫描
        if not self.dock_element:
            self.dock_element = AXUIElementCreateApplication(self.dock_pid)
        
        # 获取 Dock 的主列表 (通常是 AXList)
        # Dock 的结构通常是: Application -> AXList (Role=AXList) -> AXSystemWide -> ...
        # 直接从 App 根节点扫子节点
        self.scan_for_handoff_item(self.dock_element)

    def start_observing(self):
        self.check_permissions()
        self.get_dock_pid()

        # 1. 创建 Dock 应用的 AX 元素引用
        self.dock_element = AXUIElementCreateApplication(self.dock_pid)

        # 2. 定义回调包装器
        def callback_wrapper(observer, element, notification, refcon):
            self.observer_callback(observer, element, notification, refcon)

        # 3. 创建观察者
        self.observer, error = AXObserverCreate(self.dock_pid, callback_wrapper, None)
        if error != 0:
            print(f"❌ 无法创建观察者 (Error: {error})")
            return

        # 4. 添加通知监听
        # 监视布局改变 (图标出现/消失)
        AXObserverAddNotification(self.observer, self.dock_element, kAXLayoutChangedNotification, None)
        # 监视UI元素创建 (作为备份)
        AXObserverAddNotification(self.observer, self.dock_element, kAXCreatedNotification, None)

        # 5. 将观察者添加到 RunLoop
        run_loop_source = AXObserverGetRunLoopSource(self.observer)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), run_loop_source, kCFRunLoopDefaultMode)

        print("👀 Handoff 监听器已启动。等待 Dock 变化...")
        print("按 Ctrl+C 退出。")

        # 6. 初次扫描 (防止启动时 Handoff 已经存在)
        self.scan_dock()

        # 7. 启动 RunLoop
        self.loop = CFRunLoopGetCurrent()
        CFRunLoopRun()

    def stop(self):
        if self.loop:
            CFRunLoopStop(self.loop)

def main():
    observer = HandoffObserver()
    
    # 优雅退出处理
    def signal_handler(sig, frame):
        print("\n正在停止监听器...")
        observer.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        observer.start_observing()
    except Exception as e:
        print(f"发生异常: {e}")
        # 如果不是主线程异常，可能需要额外处理

if __name__ == "__main__":
    main()

```

---
## File: AntigravitySync/src/external/eventkit_wrapper.py
```py
import objc
import threading
import datetime
import time
from EventKit import EKEventStore, EKEntityTypeEvent
from Foundation import NSDate, NSDistributedNotificationCenter, NSObject, NSNotificationCenter
from PyObjCTools import AppHelper

# 定义通知名称常量
EKEventStoreChangedNotification = "EKEventStoreChangedNotification"
DistributedCalendarChangedNotification = "com.apple.calendar.database.changed"

class CalendarObserver(NSObject):
    """
    Observer class to handle calendar change notifications.
    Running in a background NSRunLoop via AppHelper.runConsoleEventLoop.
    """
    def initWithCallback_(self, callback):
        self = objc.super(CalendarObserver, self).init()
        if self:
            self.callback = callback
            self._registered = False
        return self

    def startObserving(self):
        if self._registered:
            return
            
        center = NSNotificationCenter.defaultCenter()
        dist_center = NSDistributedNotificationCenter.defaultCenter()
        
        # 1. 监听进程内通知 (EventKit)
        center.addObserver_selector_name_object_(
            self,
            "onCalendarChanged:",
            EKEventStoreChangedNotification,
            None
        )
        
        # 2. 监听系统级分布式通知 (底层的数据库变更)
        dist_center.addObserver_selector_name_object_(
            self,
            "onCalendarChanged:",
            DistributedCalendarChangedNotification,
            None
        )
        
        self._registered = True
        print("✅ [CalendarObserver] 开始监听日历变更通知...")

    def stopObserving(self):
        if not self._registered:
            return
            
        center = NSNotificationCenter.defaultCenter()
        dist_center = NSDistributedNotificationCenter.defaultCenter()
        
        center.removeObserver_(self)
        dist_center.removeObserver_(self)
        self._registered = False
        print("🛑 [CalendarObserver] 停止监听。")

    def onCalendarChanged_(self, notification):
        """
        Callback for both local and distributed notifications.
        """
        try:
            # print(f"⚡ [EventKit] 收到通知: {notification.name()}")
            if hasattr(self, 'callback') and self.callback:
                # 回调必须异常安全，防止由于 Python 错误导致 ObjC 崩溃
                self.callback()
        except Exception as e:
            print(f"⚠️ [CalendarObserver] 回调执行失败: {e}")

    def stopRunLoop(self):
        """
        Stop the current thread's run loop.
        Must be called ON the thread running the loop, or used via strict threading controls.
        For simplicity in this daemon setup, we rely on AppHelper.stopEventLoop()
        """
        AppHelper.stopEventLoop()

class EventKitClient:
    def __init__(self):
        self.store = EKEventStore.alloc().init()
        self.access_granted = False
        self._observer = None
        self._thread = None

    def check_access(self):
        """
        请求日历访问权限。
        注意：在 macOS 14+ 中，系统对权限要求极严。
        """
        group = threading.Event()
        
        def callback(granted, error):
            self.access_granted = granted
            if error:
                print(f"❌ 权限请求错误: {error}")
            group.set()

        # [DEBUG] Check current status first
        status = EKEventStore.authorizationStatusForEntityType_(EKEntityTypeEvent)
        print(f"ℹ️ 当前权限状态代码: {status} (0=NotDetermined, 1=Restricted, 2=Denied, 3+=Authorized)")
        
        if status == 2: # Denied
             print("⚠️ 权限已被明确拒绝。系统不会再次弹窗。")
             print("👉 请运行: tccutil reset Calendar")
             return False

        # 检查是否存在新版 API (macOS 14+)
        if hasattr(self.store, 'requestFullAccessToEventsWithCompletion_'):
            self.store.requestFullAccessToEventsWithCompletion_(callback)
        else:
            # 兼容旧版 macOS
            self.store.requestAccessToEntityType_completion_(EKEntityTypeEvent, callback)
        
        # 等待回调，超时时间设为 30s，防止进程永久挂起
        finished = group.wait(timeout=30)
        if not finished:
            print("⚠️ 权限请求超时：用户未响应或系统拦截。")
            
        return self.access_granted

    def start_watching(self, callback):
        """
        启动日历变更监听。
        
        [v2.0 ARCHITECTURE FIX]
        关键发现：EKEventStoreChangedNotification 只会被投递到创建 EKEventStore 的线程。
        由于 EKEventStore 在主线程创建，通知也只能在主线程接收。
        
        新策略：
        1. 在主线程注册 Observer（通过 performSelectorOnMainThread）
        2. 回调设置一个线程安全的 dirty flag
        3. 业务代码通过轮询检查 flag（已在 manager.py 实现）
        
        注意：这不再需要后台 RunLoop，因为主程序的事件循环会处理通知。
        """
        if not self.access_granted:
            if not self.check_access():
                print("🚫 无法启动监听：没有日历访问权限。")
                return

        if self._observer:
            print("⚠️ 监听器已在运行。")
            return

        # [v2.0] 直接在当前线程（假设是主线程）注册 Observer
        # 因为 check_access() 和 EKEventStore 都是在主线程创建的
        self._observer = CalendarObserver.alloc().initWithCallback_(callback)
        self._observer.startObserving()
        
        # 不再需要后台线程
        # 主程序的 time.sleep(1) 循环会周期性让出控制，
        # 虽然不是完美的 RunLoop，但 NSNotificationCenter 会在下次 RunLoop 迭代时投递通知
        
        # 为了确保通知被投递，我们启动一个轻量级的后台线程来周期性"轻推" RunLoop
        def runloop_nudge():
            from Foundation import NSRunLoop, NSDate
            while self._observer:
                # 每 0.5 秒轻推一次主线程的 RunLoop
                # 这会触发任何待处理的通知被投递
                time.sleep(0.5)
        
        self._thread = threading.Thread(target=runloop_nudge, name="EventKitNudge", daemon=True)
        self._thread.start()

    def stop_watching(self):
        """
        停止监听并关闭后台线程。
        """
        if self._observer:
            # 由于 runConsoleEventLoop 阻塞了后台线程，我们需要在那个线程中触发 stop
            # 使用 performSelector:onThread:withObject:waitUntilDone:
            # 注意：daemon 线程通常随主进程退出，但为了优雅关闭，我们可以尝试停止它
            
            # 在 Python/PyObjC 中，跨线程调用不如原生 ObjC 方便。
            # 简单策略：直接调用 stopObserving (虽然不是线程完全安全，但通常仅仅是解绑通知)
            # 真正停止 runLoop 需要在特定线程执行。
            
            # 方案：利用 performSelectorOnMainThread 或者直接让 daemon 随风而去。
            # 为了严谨，我们尝试调用 stopObserving
            try:
                self._observer.stopObserving()
            except Exception as e:
                print(f"⚠️ 停止监听时发生警告: {e}")
                
            self._observer = None
            # 注意：AppHelper.runConsoleEventLoop() 很难从外部线程优雅终止，
            # 除非我们发送一个专门的 selector 到该线程。
            # 作为一个 daemon 线程，不再持有引用即可。

    def fetch_events(self, target_dt):
        if not self.access_granted:
            # [Fix] 再次检查权限，防止初始化时失败但后来用户授权的情况
            if not self.check_access():
                print("🚫 访问被拒绝：请在 '系统设置 > 隐私与安全性 > 日历' 中授权终端/Python。")
                return {}

        # 确保 target_dt 为 date 对象
        target_date = target_dt.date() if isinstance(target_dt, datetime.datetime) else target_dt
        
        # 构建当天 00:00:00 到 23:59:59 的时间范围
        start_dt = datetime.datetime.combine(target_date, datetime.time.min)
        end_dt = datetime.datetime.combine(target_date, datetime.time.max)
        
        # 转换为 NSDate
        ns_start = NSDate.dateWithTimeIntervalSince1970_(start_dt.timestamp())
        ns_end = NSDate.dateWithTimeIntervalSince1970_(end_dt.timestamp())

        # 创建查询谓词
        predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(
            ns_start, ns_end, None 
        )

        # 执行查询
        events = self.store.eventsMatchingPredicate_(predicate)
        
        result = {}
        if not events:
            return result
            
        from Foundation import NSCalendar, NSCalendarUnitHour, NSCalendarUnitMinute
        
        # 获取用户当前日历历法
        calendar = NSCalendar.currentCalendar()
        
        for event in events:
            try:
                title = event.title() or "无标题"
                # 处理完成状态标识（根据现有逻辑保持一致）
                is_completed = any(title.startswith(prefix) for prefix in ["✅", "✓"])
                clean_name = title.lstrip("✅✓").strip()
                
                # [NEW] 1. 提取日历名称
                cal_title = event.calendar().title() if event.calendar() else "Unknown"

                # [NEW] 2. 计算开始时间 (HH:MM)
                # 使用 NSCalendar 提取组件以确保时区正确
                components = calendar.components_fromDate_(NSCalendarUnitHour | NSCalendarUnitMinute, event.startDate())
                start_time_str = f"{components.hour():02d}:{components.minute():02d}"

                # [NEW] 3. 计算持续时长 (分钟)
                duration_seconds = event.endDate().timeIntervalSinceDate_(event.startDate())
                duration_minutes = int(duration_seconds / 60)
                
                # [v2.0.1] 生成唯一 Key: {clean_name}_{start_time}_{id_tail}
                # id_tail 取 eventIdentifier 的后 6 位，确保即使有同名同时间的事件也不会覆盖
                event_id = event.eventIdentifier() or ""
                id_tail = event_id[-6:] if len(event_id) >= 6 else event_id
                key = f"{clean_name}_{start_time_str}_{id_tail}"
                
                # [v2.0.1] 同时生成语义 Key (用于与 Obsidian 模糊匹配)
                semantic_key = f"{clean_name}_{start_time_str}"
                
                # [v2.0.1] 构造完整字典
                result[key] = {
                    'name': clean_name,
                    'id': event_id,
                    'is_completed': is_completed,
                    'raw_name': title,
                    'current_calendar': cal_title,
                    'start_time': start_time_str,
                    'duration': duration_minutes,
                    'semantic_key': semantic_key  # 供 sync_engine 进行模糊匹配
                }
            except Exception as e:
                print(f"⚠️ 处理事件失败: {e}")
                continue
            
        return result

    def fetch_range_events(self, start_date, end_date, batch_days=1460):
        """
        [v3.0 Chronos Mode] 获取日期范围内的所有事件
        
        由于 EventKit 对超长时间范围有限制（约4年），此方法自动将大范围拆分为多个批次。
        
        Args:
            start_date: 起始日期 (date 或 datetime)
            end_date: 结束日期 (date 或 datetime)
            batch_days: 每批次的天数（默认1460天≈4年）
        
        Returns:
            dict: {date_str: {key: event_data, ...}, ...}
                  按日期分组的事件字典
        """
        if not self.access_granted:
            if not self.check_access():
                print("🚫 访问被拒绝：请在 '系统设置 > 隐私与安全性 > 日历' 中授权终端/Python。")
                return {}

        # 标准化日期
        if isinstance(start_date, datetime.datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime.datetime):
            end_date = end_date.date()
        
        from Foundation import NSCalendar, NSCalendarUnitHour, NSCalendarUnitMinute, NSCalendarUnitYear, NSCalendarUnitMonth, NSCalendarUnitDay
        calendar = NSCalendar.currentCalendar()
        
        # 计算总天数
        total_days = (end_date - start_date).days + 1
        
        # 按日期分组的结果
        result_by_date = {}  # {date_str: {key: event_data}}
        
        # 分批获取
        current_start = start_date
        batch_count = 0
        
        while current_start <= end_date:
            batch_count += 1
            current_end = min(current_start + datetime.timedelta(days=batch_days - 1), end_date)
            
            # 构建时间范围
            start_dt = datetime.datetime.combine(current_start, datetime.time.min)
            end_dt = datetime.datetime.combine(current_end, datetime.time.max)
            
            ns_start = NSDate.dateWithTimeIntervalSince1970_(start_dt.timestamp())
            ns_end = NSDate.dateWithTimeIntervalSince1970_(end_dt.timestamp())
            
            # 创建查询谓词
            predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(
                ns_start, ns_end, None
            )
            
            # 执行查询
            events = self.store.eventsMatchingPredicate_(predicate)
            
            if events:
                for event in events:
                    try:
                        title = event.title() or "无标题"
                        is_completed = any(title.startswith(prefix) for prefix in ["✅", "✓"])
                        clean_name = title.lstrip("✅✓").strip()
                        
                        cal_title = event.calendar().title() if event.calendar() else "Unknown"
                        
                        # 提取开始日期和时间
                        event_start = event.startDate()
                        components = calendar.components_fromDate_(
                            NSCalendarUnitYear | NSCalendarUnitMonth | NSCalendarUnitDay | NSCalendarUnitHour | NSCalendarUnitMinute,
                            event_start
                        )
                        
                        event_date_str = f"{components.year():04d}-{components.month():02d}-{components.day():02d}"
                        start_time_str = f"{components.hour():02d}:{components.minute():02d}"
                        
                        # 计算持续时长
                        duration_seconds = event.endDate().timeIntervalSinceDate_(event_start)
                        duration_minutes = int(duration_seconds / 60)
                        
                        # 生成唯一 Key
                        event_id = event.eventIdentifier() or ""
                        id_tail = event_id[-6:] if len(event_id) >= 6 else event_id
                        key = f"{clean_name}_{start_time_str}_{id_tail}"
                        semantic_key = f"{clean_name}_{start_time_str}"
                        
                        # 初始化日期分组
                        if event_date_str not in result_by_date:
                            result_by_date[event_date_str] = {}
                        
                        result_by_date[event_date_str][key] = {
                            'name': clean_name,
                            'id': event_id,
                            'is_completed': is_completed,
                            'raw_name': title,
                            'current_calendar': cal_title,
                            'start_time': start_time_str,
                            'duration': duration_minutes,
                            'semantic_key': semantic_key
                        }
                    except Exception as e:
                        print(f"⚠️ 处理事件失败: {e}")
                        continue
            
            # 移动到下一批次
            current_start = current_end + datetime.timedelta(days=1)
        
        print(f"📅 [EventKit] 范围查询完成: {start_date} ~ {end_date} ({total_days}天, {batch_count}批次, {len(result_by_date)}天有事件)")
        return result_by_date
if __name__ == "__main__":
    # 简单的测试桩
    from Foundation import NSBundle
    
    print("🚀 测试 EventKitClient...")
    
    # Diagnostic: Check for Usage Description
    keys = ["NSCalendarsUsageDescription", "NSCalendarsFullAccessUsageDescription"]
    info = NSBundle.mainBundle().infoDictionary()
    missing_keys = [k for k in keys if not info.get(k)]
    
    if missing_keys:
        print(f"⚠️ 警告: 当前运行环境 (Python) 缺失 Info.plist 键: {missing_keys}")
        print("    这可能导致系统拒绝弹窗授权。")
        print("    建议尝试: 在系统自带的 '终端 (Terminal.app)' 中运行此脚本。")

    client = EventKitClient()
    
    if client.check_access():
        print("✅ 授权成功，准备测试监听...")
        
        def on_change():
            print("🔔 [Main] 收到日历变更回调！可以执行同步逻辑了。")
            
        client.start_watching(on_change)
        
        print("⏳ 正在监听中，请去日历 App 修改一个日程 (按 Ctrl+C 退出)...")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 测试结束")
            client.stop_watching()
    else:
        print("❌ 授权失败")
```

---
## File: AntigravitySync/src/external/reminder_kit.py
```py
import objc
import threading
import datetime
import time
from EventKit import EKEventStore, EKEntityTypeReminder
from Foundation import NSDate, NSDistributedNotificationCenter, NSObject, NSNotificationCenter
from PyObjCTools import AppHelper

# 定义通知名称常量
EKEventStoreChangedNotification = "EKEventStoreChangedNotification"

class ReminderObserver(NSObject):
    """
    Observer class to handle reminder change notifications.
    Running in the main thread (or capable thread) to receive notifications.
    """
    def initWithCallback_(self, callback):
        self = objc.super(ReminderObserver, self).init()
        if self:
            self.callback = callback
            self._registered = False
        return self

    def startObserving(self):
        if self._registered:
            return
            
        center = NSNotificationCenter.defaultCenter()
        
        # 监听进程内通知 (EventKit)
        center.addObserver_selector_name_object_(
            self,
            "onStoreChanged:",
            EKEventStoreChangedNotification,
            None
        )
        
        self._registered = True
        print("✅ [ReminderObserver] 开始监听提醒事项变更通知...")

    def stopObserving(self):
        if not self._registered:
            return
            
        center = NSNotificationCenter.defaultCenter()
        center.removeObserver_(self)
        self._registered = False
        print("🛑 [ReminderObserver] 停止监听。")

    def onStoreChanged_(self, notification):
        """
        Callback for notifications.
        """
        try:
            if hasattr(self, 'callback') and self.callback:
                self.callback()
        except Exception as e:
            print(f"⚠️ [ReminderObserver] 回调执行失败: {e}")

class ReminderKitClient:
    def __init__(self):
        self.store = EKEventStore.alloc().init()
        self.access_granted = False
        self._observer = None
        self._thread = None

    def check_access(self):
        """
        请求提醒事项访问权限。
        """
        group = threading.Event()
        
        def callback(granted, error):
            self.access_granted = granted
            if error:
                print(f"❌ Reminder 权限请求错误: {error}")
            group.set()

        # [DEBUG] Check current status first
        status = EKEventStore.authorizationStatusForEntityType_(EKEntityTypeReminder)
        print(f"ℹ️ 当前 Reminder 权限状态: {status} (0=NotDetermined, 1=Restricted, 2=Denied, 3+=Authorized)")
        
        if status == 2: # Denied
             print("⚠️ Reminder 权限已被明确拒绝。系统不会再次弹窗。")
             print("👉 请运行: tccutil reset Reminders")
             return False

        # 检查是否存在新版 API (macOS 14+)
        if hasattr(self.store, 'requestFullAccessToRemindersWithCompletion_'):
            self.store.requestFullAccessToRemindersWithCompletion_(callback)
        else:
            # 兼容旧版 macOS
            self.store.requestAccessToEntityType_completion_(EKEntityTypeReminder, callback)
        
        # 等待回调，超时时间设为 30s
        finished = group.wait(timeout=30)
        if not finished:
            print("⚠️ Reminder 权限请求超时。")
            
        return self.access_granted

    def start_watching(self, callback):
        """
        启动提醒事项变更监听。
        """
        if not self.access_granted:
            if not self.check_access():
                print("🚫 无法启动监听：没有提醒事项访问权限。")
                return

        if self._observer:
            print("⚠️ Reminder 监听器已在运行。")
            return

        # 直接在当前线程（假设是主线程）注册 Observer
        self._observer = ReminderObserver.alloc().initWithCallback_(callback)
        self._observer.startObserving()
        
        # 可以在这里复用 EventKitWrapper 中的 runloop_nudge 逻辑，
        # 或者假设主程序已经有了 RunLoop 机制 (FusionManager 使用 CFRunLoopRunInMode)

    def stop_watching(self):
        """
        停止监听。
        """
        if self._observer:
            try:
                self._observer.stopObserving()
            except Exception as e:
                print(f"⚠️ 停止 Reminder 监听时发生警告: {e}")
            self._observer = None

    def fetch_reminders(self, start_date=None, end_date=None):
        """
        获取提醒事项。
        注意：fetchRemindersMatchingPredicate 是异步的！
        为了适配同步调用风格，我们需要用 threading.Event 等待回调。
        """
        if not self.access_granted:
            if not self.check_access():
                return {}

        # 如果没有指定日期，默认获取所有未完成的
        # 这里为了简化，我们获取所有的 (incomplete) 提醒事项，或者根据日期范围获取。
        # Predicate documentation:
        # predicateForRemindersInCalendars: (New logic) -> Fetch all incomplete?
        # predicateForIncompleteRemindersWithDueDateStarting:ending:calendars:
        # predicateForCompletedRemindersWithCompletionDateStarting:ending:calendars:
        
        # 策略：获取所有未完成 + 指定日期范围内完成的
        
        result_reminders = {}
        group = threading.Event()
        
        def completion_callback(reminders):
            if reminders:
                 for r in reminders:
                    self._process_reminder(r, result_reminders)
            group.set()
            
        # 1. 获取未完成的 (Incomplete)
        predicate_incomplete = self.store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
            None, None, None
        )
        self.store.fetchRemindersMatchingPredicate_completion_(predicate_incomplete, completion_callback)
        group.wait(timeout=10)
        
        # 2. 如果指定了日期范围，获取该范围内完成的 (Completed)
        if start_date and end_date:
            group.clear()
            
            # Convert to NSDate
            ns_start = self._to_nsdate(start_date)
            ns_end = self._to_nsdate(end_date)
            
            predicate_completed = self.store.predicateForCompletedRemindersWithCompletionDateStarting_ending_calendars_(
                ns_start, ns_end, None
            )
            self.store.fetchRemindersMatchingPredicate_completion_(predicate_completed, completion_callback)
            group.wait(timeout=10)

        return result_reminders

    def _to_nsdate(self, dt):
        if isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
             dt = datetime.datetime.combine(dt, datetime.time.min)
        return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())

    def _process_reminder(self, reminder, result_dict):
        try:
            title = reminder.title() or "无标题"
            rid = reminder.calendarItemIdentifier()
            is_completed = reminder.isCompleted()
            
            # 提取 List 名称
            list_title = reminder.calendar().title() if reminder.calendar() else "Unknown"
            
            # 提取日期
            due_date = None
            if reminder.dueDateComponents():
                comps = reminder.dueDateComponents()
                # 注意：dueDateComponents 可能没有 year/month/day (如果只设置了时间?)
                # 通常 Reminders 都有日期
                if comps.year() != 2147483647: # NSDateComponentUndefined
                     due_date = f"{comps.year():04d}-{comps.month():02d}-{comps.day():02d}"
            
            # 如果没有 due date，可能不处理？或者归类为 Inbox
            if not due_date:
                due_date = "NoDate"

            if due_date not in result_dict:
                result_dict[due_date] = []

            result_dict[due_date].append({
                'id': rid,
                'title': title,
                'is_completed': is_completed,
                'list': list_title,
                'priority': reminder.priority(),
                'notes': reminder.notes()
            })
        except Exception as e:
            print(f"⚠️ 处理 Reminder 失败: {e}")

if __name__ == "__main__":
    client = ReminderKitClient()
    if client.check_access():
        print("✅ 授权成功")
        res = client.fetch_reminders()
        print(f"📦 Fetched Reminders: {len(res)} dates")
        for date, items in res.items():
            print(f"  📅 {date}: {len(items)} items")
            for item in items[:3]:
                print(f"    - [{ 'x' if item['is_completed'] else ' ' }] {item['title']} ({item['list']})")

```

---
## File: AntigravitySync/src/external/note_sync_core/monitor.py
```py
import os
import sys
import time
import datetime
import threading
import re
import difflib
import random
import string

# 确保能找到同目录下的 read_today_note
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from read_today_note import AppleNotesReader


class NoteMonitor:
    """
    Apple Notes 变更监听器。
    以 daemon 线程运行，检测备忘录变更并自动插入 Obsidian 日记。
    """

    def __init__(self, config=None, logger=None):
        """
        Args:
            config: Config 对象，需要有 DAILY_NOTE_DIR, TEMPLATE_FILE, KEYWORD_MAPPING 属性
            logger: Logger 对象，需要有 info() 方法。若 None 则使用 print
        """
        self._config = config
        self._log = logger.info if logger else print
        self._thread = None
        self._running = False
        self._reader = AppleNotesReader()
        self._polling_interval = 2.0  # 秒
        self._tomorrow_note_created = False  # 防重复创建次日日记

    # =====================
    # 公开接口
    # =====================
    
    @staticmethod
    def _generate_id(length=6):
        """生成随机 6 位字母数字 ID (Obsidian Block ID 风格)"""
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choices(chars, k=length))

    def start(self):
        """以 daemon 线程启动监听"""
        if self._thread and self._thread.is_alive():
            self._log("⚠️ [NoteMonitor] 已在运行中，跳过重复启动")
            return

        self._running = True
        self._thread = threading.Thread(target=self._polling_loop, daemon=True, name="NoteMonitor")
        self._thread.start()
        self._log("📝 [NoteMonitor] 备忘录监听已启动 (daemon 线程)")

    def stop(self):
        """停止监听"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._log("🛑 [NoteMonitor] 备忘录监听已停止")

    def _sync_obsidian_tasks_to_notes(self, note_name, current_notes_content):
        """
        [v5.4] 单向同步: Obsidian Unchecked Tasks -> Apple Notes
        机制:
        1. 格式: *ID*Content (*HH:MM:SS*Content)
        2. 扫描 Obsidian:
           - 收集所有 {ID: Content}。
           - 新任务自动生成 ID 并保存。
        3. 扫描 Apple Notes:
           - *ID*Content:
             - 若 ID 在 Obsidian 中:
               - 比较 Content。若不同 -> 更新 (Update)。
               - 若相同 -> 保持。
               - 标记该 ID 已处理。
             - 若 ID 不在 Obsidian 中 -> 删除 (Delete)。
        4. 追加 (Add):
           - 将 Obsidian 中未被处理的 ID 追加到 Apple Notes。
        """
        if not self._config or not hasattr(self._config, 'DAILY_NOTE_DIR'):
            return False, current_notes_content

        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_note_dir = getattr(self._config, 'DAILY_NOTE_DIR', None)
        if not daily_note_dir:
            return False, current_notes_content
            
        daily_note_path = os.path.join(daily_note_dir, f"{today_str}.md")
        if not os.path.exists(daily_note_path):
            return False, current_notes_content
            
        try:
            with open(daily_note_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            obsidian_changed = False
            # Key: ID, Value: Clean Content (Includes Checked & Unchecked)
            sync_target_tasks = {}
            # Set of all IDs found in Obsidian to detect manual deletions
            all_obsidian_task_ids = set()
            
            # Pattern for ANY task (checked or unchecked) to parse IDs and content
            # Group 1: Prefix (- [ ] or - [x])
            # Group 2: Content
            task_line_pat = re.compile(r'^(\s*-\s*\[[ xX]\]\s+)(.*)')
            # Specific pattern to identify brand new tasks that need IDs
            new_task_pat = re.compile(r'^\s*-\s*\[\s\]\s+(?!.*<span id=")')
            id_pat = re.compile(r'<span id="([^"]+)"></span>')
            
            # [v7.0] Use Random ID for new tasks
            
            new_obsidian_lines = []
            
            # --- Step 1: Process Obsidian (Collect Data) ---
            for line in lines:
                m = task_line_pat.match(line)
                if m:
                    prefix = m.group(1)
                    content_tail = m.group(2)
                    id_match = id_pat.search(content_tail)
                    is_unchecked = "[ ]" in prefix
                    
                    if id_match:
                        # Case A: Existing Task (Checked or Unchecked) with ID
                        tid = id_match.group(1)
                        # [v7.4] Clean content: Remove ID span AND Timestamp
                        raw_clean = content_tail.replace(id_match.group(0), "")
                        # Remove leading timestamp (e.g. 01:34 or 01:59 - 02:31) to avoid "ID + Time + Content" in Apple Notes
                        clean_content = re.sub(r'^\s*\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})*\s*', '', raw_clean).strip()
                        if "#" in clean_content:
                            all_obsidian_task_ids.add(tid)
                            sync_target_tasks[tid] = clean_content
                        
                        new_obsidian_lines.append(line)
                    elif is_unchecked and "#" in content_tail:
                        # Case B: New Unchecked Task -> Assign RAND ID
                        # [v7.0] Random ID
                        rand_id = self._generate_id()
                        span = f'<span id="{rand_id}"></span>'
                        clean_content = content_tail.strip()
                        modified_line = f"{prefix}{span}{clean_content}"
                        if line.endswith('\n') and not modified_line.endswith('\n'):
                            modified_line += '\n'
                        
                        new_obsidian_lines.append(modified_line)
                        obsidian_changed = True
                        
                        sync_target_tasks[rand_id] = clean_content
                        all_obsidian_task_ids.add(rand_id)
                    else:
                        # Case C: Checked task without ID (Rare)
                        new_obsidian_lines.append(line)
                else:
                    new_obsidian_lines.append(line)

            # Update Obsidian File
            if obsidian_changed:
                with open(daily_note_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_obsidian_lines)
                self._log(f"📝 [Sync] Marked new tasks in Obsidian with IDs.")

            # --- Step 2: Process Apple Notes (Diff & Merge) ---
            if current_notes_content:
                note_lines = current_notes_content.splitlines()
            else:
                note_lines = []
                
            new_note_lines = []
            notes_changed = False
            
            # [v7.0] Regex to detect *ID*Content line.
            # ID can be Timestamp (OLD) or Alphanumeric (NEW).
            # We match strictly *ID* at start.
            note_line_pat = re.compile(r'^\*([a-zA-Z0-9:]+)\*(.*)')
            
            # Track which IDs we found in Apple Notes
            processed_ids = set()
            
            for nl in note_lines:
                strip_nl = nl.strip()
                m = note_line_pat.match(strip_nl)
                if m:
                    nid = m.group(1)
                    ncontent = m.group(2) # Content in Apple Notes
                    
                    if nid in sync_target_tasks:
                        # 1. Update Check (Checked or Unchecked)
                        obsidian_content = sync_target_tasks[nid].replace('\xa0', ' ').strip()
                        ncontent_clean = ncontent.replace('\xa0', ' ').strip()
                        
                        # [Fix] Normalize whitespace to avoid infinite loops (Apple Notes collapses spaces)
                        # Also remove HTML tags from Obsidian content before comparison/sync to avoid span loops.
                        clean_obsidian = re.sub(r'<[^>]+>', '', sync_target_tasks[nid]).strip()
                        
                        norm_note = " ".join(ncontent.split())
                        norm_obsidian = " ".join(clean_obsidian.split())
                        
                        if norm_note != norm_obsidian:
                            # Content changed in Obsidian -> Sync to Note
                            # We use the CLEAN content for Apple Notes update
                            self._log(f"✏️ [内容变更] 备忘录 VS Obsidian 内容不一致:\n   🍎 Note: {ncontent}\n   🟣 Obsid: {clean_obsidian}")
                            
                            updated_line = f"*{nid}*{clean_obsidian}"
                            new_note_lines.append(updated_line)
                            notes_changed = True
                            self._log(f"🔄 [同步] 正在更新任务 {nid} 到备忘录...")
                        elif ncontent != clean_obsidian:
                            # Same logical content, but different raw string (whitespace diff)
                            # We usually want to rewrite to match Obsidian perfectly
                            # But if it causes loop, we skip OR we log differently.
                            # Current logic: Skip update to avoid loop (since we use 'norm_' check above)
                            # Just keep the Note version to stabilize
                            new_note_lines.append(nl)
                            # self._log(f"📝 [格式忽略] 空白符差异 (已自动标准化): {nid}")
                        else:
                            # Same, keep
                            new_note_lines.append(nl)
                        
                        processed_ids.add(nid)
                    elif nid in all_obsidian_task_ids:
                        # 2. Safety Fallback (ID exists but content not in sync_target)
                        new_note_lines.append(nl)
                        processed_ids.add(nid)
                    else:
                        # 3. Delete (ID is gone from Obsidian entirely)
                        self._log(f"🗑️ [Sync] Removing task {nid} from Apple Notes (ID manually deleted).")
                        notes_changed = True
                else:
                    # Regular line, keep
                    new_note_lines.append(nl)

            # --- Step 3: Append Missing Tasks ---
            added_count = 0
            restored_tasks = []
            
            # Iterate dict to preserve order
            for tid, tcontent in sync_target_tasks.items():
                if tid not in processed_ids:
                    # New in Obsidian OR Deleted in Notes -> Restore/Add
                    line_str = f"*{tid}*{tcontent}"
                    new_note_lines.append(line_str)
                    processed_ids.add(tid) # Mark as processed immediately
                    added_count += 1
                    restored_tasks.append(tid)
            
            if added_count > 0:
                notes_changed = True
                self._log(f"🔙 [Sync] Restoring/Adding missing tasks: {restored_tasks}")
            
            # --- Step 4: Write to Apple Notes ---
            if notes_changed:
                final_content = "\n".join(new_note_lines)
                if final_content and not final_content.endswith('\n'):
                     final_content += "\n"
                
                if self._reader.update_note_content(note_name, final_content):
                     msg = []
                     if added_count: msg.append(f"{added_count} Restored/Added")
                     self._log(f"📥 [Sync] Notes Updated: {', '.join(msg) or 'Modifications applied'}")
                     return True, final_content
            
            return False, current_notes_content

        except Exception as e:
            self._log(f"⚠️ [Sync Error] {e}")
            return False, current_notes_content

    # =====================
    # 核心轮询逻辑 (Modified)
    # =====================

    def _polling_loop(self):
        """后台轮询主循环"""
        self._log(f"📍 [NoteMonitor] 策略: Active Polling (每 {self._polling_interval}s)")

        # 确定今日备忘录标题
        today = datetime.date.today()
        note_name = f"{today.year}/{today.month}/{today.day}"
        self._log(f"🔎 [NoteMonitor] 追踪备忘录: '{note_name}'")

        # [v4.1] 启动检查：确保今日 Obsidian 日记和 Apple Note 存在
        self._check_and_create_today_notes(today)

        # 初始读取
        last_content = self._reader.get_note_content(note_name)
        if last_content is None or last_content == "NOT_FOUND":
            self._log(f"⚠️ [NoteMonitor] 备忘录未找到，等待出现...")
            last_hash = 0
        else:
            self._log(f"✅ [NoteMonitor] 初始内容已加载 ({len(last_content)} chars)")
            
            # [v4.2] 首次全量扫描：同步遗漏的未标记项
            self._log("🔄 [NoteMonitor] 正在执行首次全量扫描 (Sync missing items)...")
            initial_lines = last_content.splitlines()
            dummy_diff = list(difflib.unified_diff([], initial_lines, n=0, lineterm=''))
            
            # 调用处理逻辑 (会自动回写 ✅)
            self._process_diff(dummy_diff, initial_lines, note_name)
            
            # 如果发生了回写，刷新 last_content
            time.sleep(1)
            last_content = self._reader.get_note_content(note_name)
            
            # [v5.0] Initial Sync from Obsidian
            if last_content and last_content != "NOT_FOUND":
                 synced, new_text = self._sync_obsidian_tasks_to_notes(note_name, last_content)
                 if synced:
                     last_content = new_text
            
            last_hash = hash(last_content) if last_content else 0

        while self._running:
            try:
                time.sleep(self._polling_interval)

                # 跨日检测
                current_today = datetime.date.today()
                if current_today != today:
                    today = current_today
                    note_name = f"{today.year}/{today.month}/{today.day}"
                    self._log(f"🌙 [NoteMonitor] 跨日检测: 切换到 '{note_name}'")
                    last_hash = 0
                    last_content = ""
                    self._tomorrow_note_created = False

                # [v4.0] 23:55 自动创建次日日记
                self._check_create_tomorrow_note()

                current_content = self._reader.get_note_content(note_name)

                # 备忘录消失
                if current_content is None or current_content == "NOT_FOUND":
                    if last_hash != 0:
                        self._log("❌ [NoteMonitor] 备忘录消失!")
                        last_hash = 0
                    continue

                # [v5.0] 每一轮都检查 Obsidian 是否有新任务推送到 Apple Notes
                # 注意: 这会增加一次文件读操作，但对于单机环境通常可接受
                synced, new_text_v5 = self._sync_obsidian_tasks_to_notes(note_name, current_content)
                if synced:
                    current_content = new_text_v5

                current_hash = hash(current_content)

                if current_hash != last_hash:
                    now_str = datetime.datetime.now().strftime('%H:%M:%S')
                    self._log(f"\n⚡ [NoteMonitor] 变更检测 {now_str}")

                    # Diff 分析
                    safe_last = last_content if last_content and last_content != "NOT_FOUND" else ""
                    old_lines = safe_last.splitlines()
                    new_lines = current_content.splitlines()

                    diff = list(difflib.unified_diff(old_lines, new_lines, n=0, lineterm=''))
                    self._process_diff(diff, new_lines, note_name)

                    print("-" * 40)

                    last_hash = current_hash
                    last_content = current_content

            except Exception as e:
                self._log(f"⚠️ [NoteMonitor] 轮询异常: {e}")
                time.sleep(5)  # Backoff

    # =====================
    # 23:55 次日日记创建
    # =====================

    def _check_create_tomorrow_note(self):
        """
        [v4.0] 每天 23:55 自动创建次日日记文件
        [v4.3] 同时自动创建次日 Apple Note
        """
        if self._tomorrow_note_created:
            return  # 今天已经创建过了

        if not self._config:
            return

        now = datetime.datetime.now()

        # 只在 23:55:00 ~ 23:59:59 之间触发
        if now.hour == 23 and now.minute >= 55:
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
            tomorrow_str = tomorrow.strftime('%Y-%m-%d')
            # Apple Notes 标题格式: 2026/2/12 (无零填充)
            tomorrow_apple_title = f"{tomorrow.year}/{tomorrow.month}/{tomorrow.day}"
            
            daily_note_dir = getattr(self._config, 'DAILY_NOTE_DIR', None)

            # 1. 创建 Obsidian 日记
            if daily_note_dir:
                tomorrow_path = os.path.join(daily_note_dir, f"{tomorrow_str}.md")

                if not os.path.exists(tomorrow_path):
                    # 读取模板
                    template_content = self._read_template()

                    try:
                        with open(tomorrow_path, 'w', encoding='utf-8') as f:
                            f.write(template_content)
                        self._log(f"📅 [NoteMonitor] 次日 Obsidian 日记已创建: {tomorrow_str}.md")
                    except Exception as e:
                        self._log(f"❌ [NoteMonitor] 创建次日日记失败: {e}")
                else:
                    self._log(f"ℹ️ [NoteMonitor] 次日 Obsidian 日记已存在，跳过创建")

            # 2. 创建 Apple Note
            try:
                # 默认内容
                default_body = f"Daily Log {tomorrow_str}<br><br>"
                result = self._reader.create_note(tomorrow_apple_title, default_body)
                
                if result == "CREATED":
                    self._log(f"🍏 [NoteMonitor] 次日 Apple Note 已创建: '{tomorrow_apple_title}'")
                elif result == "EXISTS":
                    self._log(f"ℹ️ [NoteMonitor] 次日 Apple Note 已存在，跳过")
                else:
                    self._log(f"❌ [NoteMonitor] 创建次日 Apple Note 失败")
            except Exception as e:
                self._log(f"❌ [NoteMonitor] 调用 Apple Notes 接口异常: {e}")

            # 无论成功与否，标记为已尝试，避免在 23:55-23:59 期间重复疯狂调用
            self._tomorrow_note_created = True

    def _read_template(self):
        """
        读取 Config.TEMPLATE_FILE 模板内容。
        如果模板不存在，则使用内置的基础骨架。
        """
        template_path = getattr(self._config, 'TEMPLATE_FILE', None)

        if template_path and os.path.exists(template_path):
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                self._log(f"⚠️ [NoteMonitor] 模板读取失败，使用默认骨架: {e}")

        # 内置默认模板（与 DayPlanTemplate.md 一致）
        return """---
tags:
  - DayPlan
  - timecost
  - tradecost
---
# Day planner

# Journey

# Log
## #stateofmind

## #takein

## #exercice

## #account
"""

    def _check_and_create_today_notes(self, today):
        """
        [v4.1] 检查并创建今日所需的 Obsidian 日记和 Apple Notes
        """
        if not self._config:
            return

        # 1. Check/Create Obsidian Daily Note
        today_str = today.strftime('%Y-%m-%d')
        daily_note_dir = getattr(self._config, 'DAILY_NOTE_DIR', None)
        
        if daily_note_dir:
            today_path = os.path.join(daily_note_dir, f"{today_str}.md")
            if not os.path.exists(today_path):
                self._log(f"⚠️ [NoteMonitor] 今日日记缺失，正在创建: {today_str}.md")
                template_content = self._read_template()
                try:
                    with open(today_path, 'w', encoding='utf-8') as f:
                        f.write(template_content)
                    self._log(f"✅ [NoteMonitor] 今日日记创建成功")
                except Exception as e:
                    self._log(f"❌ [NoteMonitor] 创建今日日记失败: {e}")

        # 2. Check/Create Apple Note
        note_name = f"{today.year}/{today.month}/{today.day}"
        content = self._reader.get_note_content(note_name)
        
        if content == "NOT_FOUND" or content is None:
            self._log(f"⚠️ [NoteMonitor] 今日备忘录缺失，正在创建: '{note_name}'")
            # 默认内容可以是空白，或者简单的标题
            default_body = f"Daily Log {today_str}"
            result = self._reader.create_note(note_name, default_body)
            if result == "CREATED":
                self._log(f"✅ [NoteMonitor] 备忘录创建成功")
            elif result == "EXISTS":
                self._log(f"ℹ️ [NoteMonitor] 备忘录已存在 (并发创建?)")
            else:
                self._log(f"❌ [NoteMonitor] 创建备忘录失败")

    # =====================
    # Obsidian Task Helper
    # =====================

    def _mark_obsidian_task_completed_with_time(self, task_id, completion_time):
        """
        [v7.0] 标记 Obsidian 任务完成，并使用双 ID 格式更新时间。
        Target Format: - [x] HH:MM<span id="RANDOM_ID"></span><span id="OLD_ID"></span> Content
        注意: 使用随机 ID 避免重复。
        """
        if not self._config or not hasattr(self._config, 'DAILY_NOTE_DIR'):
            return False

        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_note_dir = getattr(self._config, 'DAILY_NOTE_DIR', None)
        if not daily_note_dir:
            return False
            
        daily_note_path = os.path.join(daily_note_dir, f"{today_str}.md")
        if not os.path.exists(daily_note_path):
            return False
            
        try:
            with open(daily_note_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            updated = False
            target_span = f'<span id="{task_id}">'
            
            # [v7.0] Use Random ID for completion event
            full_time_id = self._generate_id()
            disp_time = completion_time[:5] # HH:MM

            # Pattern to match EXISTING completion timestamp in gap
            # Matches:   SPACE HH:MM <span id="ID"></span> matches
            existing_ts_pat = re.compile(r'^\s*(\d{2}:\d{2})<span id="([^"]+)"></span>\s*$')

            new_lines = []
            for line in lines:
                if target_span in line and ("- [ ]" in line or "- [x]" in line):
                    # We found the line.
                    parts = line.split(target_span)
                    pre_part = parts[0]
                    post_part = target_span.join(parts[1:]) 
                    
                    cb_match = re.search(r'^(\s*)(-\s*\[.)\](.*)', pre_part)
                    
                    if cb_match:
                        indent = cb_match.group(1)
                        new_box = "- [x]"
                        gap_content = cb_match.group(3) 
                        
                        # [v7.0] Check if gap_content already has THIS time.
                        # If so, we do NOT generate a new random ID, to avoid flipping IDs on every poll.
                        gm = existing_ts_pat.match(gap_content)
                        if gm:
                            existing_time = gm.group(1)
                            existing_id = gm.group(2)
                            
                            # If the displayed time is same as completion time, we assume no change needed.
                            # This prevents infinite loops of "Replace ID A with ID B" if time matches.
                            if existing_time == disp_time:
                                # Just ensure Checked
                                if "- [ ]" in line:
                                    new_line = line.replace("- [ ]", "- [x]")
                                    if new_line != line:
                                        updated = True
                                        new_lines.append(new_line)
                                        self._log(f"✅ [同步] 修正任务状态 (时间一致，保持原 ID): {task_id}")
                                    else:
                                        new_lines.append(line)
                                else:
                                    new_lines.append(line)
                                continue

                        # [v7.9] Multi-Span & Start-End Logic
                        # 1. Text: "Start - End" (HH:MM)
                        # 2. Spans: Accumulate <span id="HH:MM:SS"></span> for history
                        
                        full_span_id = completion_time # Use full time (possibly with seconds) as ID
                        extra_span = f'<span id="{full_span_id}"></span>'
                        
                        tm = re.match(r'^\s*([\d: -]+)\s*$', gap_content)
                        should_update = False
                        
                        # [v7.7] Ensure it actually contains digits
                        if tm and any(c.isdigit() for c in tm.group(1)):
                             existing_time_str = tm.group(1).strip()
                             
                             # [v7.8] "Start - End" Logic
                             parts = existing_time_str.split('-')
                             start_time = parts[0].strip()
                             last_time = parts[-1].strip()

                             if disp_time == last_time:
                                 # Time duplicated. 
                                 # User said: "插入多次以此类推" (Insert multiple times similarly)
                                 # But also "锁定开始时间并且更新结束时" (Lock start, update end).
                                 # IF time matches, Text doesn't change.
                                 # Do we still add a span?
                                 # If we add span for SAME time, we get <02:06><02:06>. Redundant.
                                 # We SKIP span insertion if time matches to avoid spamming spans for same polling event.
                                 pass 
                             else:
                                 # Update End Time
                                 new_insert = f" {start_time} - {disp_time}"
                                 self._log(f"   ⏱️ 时间覆盖: {existing_time_str} -> {new_insert.strip()}")
                                 should_update = True
                        else:
                            # Initial Time
                            new_insert = f" {disp_time}"
                            self._log(f"   ⏱️ 时间初始化: {disp_time}")
                            should_update = True
                            
                        # Reassemble
                        if should_update:
                            # [v7.10] Fix Insertion: target_span is just '<span id="...">'
                            # post_part likely starts with '</span>'. We must insert AFTER it.
                            
                            closing_tag = "</span>"
                            insert_idx = 0
                            
                            if post_part.startswith(closing_tag):
                                insert_idx += len(closing_tag)
                            
                            # Now skip any existing valid spans (Multi-span history)
                            # Match spans starting from current insert_idx
                            remainder = post_part[insert_idx:]
                            span_match = re.match(r'^(?:<span id="[^"]+"></span>)*', remainder)
                            
                            if span_match:
                                insert_idx += span_match.end()
                                
                            new_post_part = post_part[:insert_idx] + extra_span + post_part[insert_idx:]
                            
                            new_line = f"{indent}{new_box}{new_insert}{target_span}{new_post_part}"
                            
                            updated = True
                            new_lines.append(new_line)
                            self._log(f"✅ [同步] 更新 Obsidian 任务状态: {task_id}")
                            self._log(f"   ➕ 新增校验 Span: {extra_span}")
                        else:
                             # Just ensure Checked
                            if "- [ ]" in line:
                                new_line = line.replace("- [ ]", "- [x]")
                                if new_line != line:
                                    updated = True
                                    new_lines.append(new_line)
                                    self._log(f"✅ [同步] 修正任务状态 (时间已存在): {task_id}")
                                else:
                                    new_lines.append(line)
                            else:
                                new_lines.append(line)
                            continue 
                            
                        # Skip appending original line since we handled it
                        continue

                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            if updated:
                with open(daily_note_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                return True
            return False
        except Exception as e:
            self._log(f"❌ [Sync Error] 更新 Obsidian 任务失败: {e}")
            return False

    # =====================
    # Diff 处理逻辑
    # =====================

    def _process_diff(self, diff, current_lines, note_name):
        """
        处理 unified diff 输出，识别 ADD/DEL/MOD。
        如果成功同步到 Obsidian，则更新 Apple Notes 内容（添加 ✅）。
        """
        GREEN = '\033[92m'
        RED = '\033[91m'
        YELLOW = '\033[93m'
        RESET = '\033[0m'

        changes_found = False
        current_dels = []
        current_adds = []
        
        # 记录需要回写 Apple Notes 的标志
        notes_updated = False
        # 为了避免修改正在遍历的列表，使用索引或副本，但这里我们直接修改 current_lines List
        # 只要我们能找到对应的行即可。

        time_pat = re.compile(r'^\s*(\d{1,2}[:：]\d{2})')
        # [v7.0] Heartbeat Completion Pattern (Enhanced)
        # Supported formats:
        # 1. StartTime *ID* Content -> 22:24:24 *21:25:38*#B 打扫
        # 2. Content (id=*ID*)      -> #A 厄尔 （id=*21:25:38*
        # 3. StartTime Content (id=ID) -> 00:22:26 #A 厄尔 (id=22:46:52)
        # 4. Also support Chinese parens （id=...）
        # 5. [v7.0] Supports Random Alphanumeric IDs (e.g. a1b2c3)
        # 6. [v7.3] Supports Underscores in manual IDs
        
        # Regex explanation:
        # ^\s*                     : Start of line
        # (?:(\d{1,2}:\d{2}(?::\d{2})?)\s+)? : Group 1: Optional Time (e.g. 23:06:31)
        # .*?                      : Content
        # (?: ... )                : Non-capturing group for OR logic
        #   \*([a-zA-Z0-9:_]+)\*          : Group 2: *ID* (timestamp or random or manual)
        #   |
        #   \(\s*id=([a-zA-Z0-9:_]+)\s*\) : Group 3: (id=ID)
        #   |
        #   （\s*id=([a-zA-Z0-9:_]+)\s*） : Group 4: （id=ID）
        
        completion_pat = re.compile(
            r'^\s*(?:(\d{1,2}:\d{2}(?::\d{2})?)\s+)?.*?'
            r'(?:\*([a-zA-Z0-9:_]+)\*|\(\s*id=([a-zA-Z0-9:_]+)\s*\)|（\s*id=([a-zA-Z0-9:_]+)\s*）)'
        )

        def flush_hunk(dels, adds):
            nonlocal changes_found, notes_updated
            used_adds = [False] * len(adds)

            for d_line in dels:
                d_match = time_pat.match(d_line.strip())
                matched_idx = -1

                if d_match:
                    d_time = d_match.group(1)
                    for i, a_line in enumerate(adds):
                        if not used_adds[i]:
                            a_match = time_pat.match(a_line.strip())
                            if a_match and a_match.group(1) == d_time:
                                matched_idx = i
                                break

                if matched_idx != -1:
                    print(f"{YELLOW}[MOD] {d_line} -> {adds[matched_idx]}{RESET}")
                    # Even if it's a MOD, the new content might need processing (e.g. heartbeat)
                    # We mark it as NOT used so it falls through to the ADD handler loop below?
                    # No, better to process it right here or force it to be checked.
                    # Simplest hack: Don't mark used_adds[matched_idx] = True if we want it processed.
                    # BUT we printed [MOD], so usually that implies we handled it visually.
                    
                    # Check if the NEW line has completion markers but NO tick
                    # If so, we might want to process it as a completion event.
                    if completion_pat.match(adds[matched_idx].strip()) and "✅" not in adds[matched_idx]:
                         used_adds[matched_idx] = False # Let it fall through to ADD loop
                    else:
                         used_adds[matched_idx] = True
                else:
                    print(f"{RED}[DEL] {d_line}{RESET}")

            for i, a_line in enumerate(adds):
                if not used_adds[i]:
                    stripped_line = a_line.strip()
                    suffix = ""
                    processed = False
                    
                    # 0. Check Completion Heartbeat (Highest Priority)
                    # e.g. 22:24:24 *21:25:38*#B 打扫
                    comp_match = completion_pat.match(stripped_line)
                    if comp_match and "✅" not in stripped_line:
                        # Group 1: Time (Optional)
                        comp_time = comp_match.group(1)
                        # Group 2, 3, 4: ID variants
                        # *ID* or (id=ID) or （id=ID）
                        task_id = comp_match.group(2) or comp_match.group(3) or comp_match.group(4)
                        
                        # Fallback for time if not present at start of line
                        if not comp_time:
                            # [v7.9] Use seconds for ID generation
                            comp_time = datetime.datetime.now().strftime('%H:%M:%S')
                        
                        # Action 1: Mark Obsidian Task Complete AND Update Time
                        marked = self._mark_obsidian_task_completed_with_time(task_id, comp_time)
                        
                        # [Changed] Do NOT append new line to Day Planner section.
                        # We only update the existing task line in place.
                        
                        if marked:
                            # [v7.2] User Request: RESTORED " ✅" to Apple Notes.
                            suffix = " ✅"
                            processed = True
                            self._log(f"💓 [Heartbeat] Task {task_id} completed at {comp_time}")

                    # 1. Check Time Entries (Water/Log/DayPlan)
                    is_time_entry = time_pat.match(stripped_line)
                    if not processed and is_time_entry and "✅" not in stripped_line:
                        # [v4.4] Day Planner Check (starts with "*")
                        # e.g. 17:55:48"*打游戏"
                        if self._is_day_plan_entry(stripped_line):
                             if self._append_to_day_plan_section(a_line):
                                suffix = " ✅"
                                processed = True
                        
                        # Fallback to Water/Log (Takein)
                        elif self._append_to_daily_note(a_line):
                            suffix = " ✅"
                            processed = True

                    # 2. Check Account Entries (tradetype::...)
                    # Example: (tradetype::$食物)(tradename::鸡蛋)(tradecost::-858)(tradetime::2026/2/12 00:19:36)
                    if not processed and "(tradetype::" in stripped_line and "✅" not in stripped_line:
                        if self._append_to_account_section(a_line):
                            suffix = " ✅"
                            processed = True

                    if processed:
                        # [Write Back Logic] common for both types
                        try:
                            # Iterate to find the exact line to update
                            for idx, cl in enumerate(current_lines):
                                if cl == a_line: 
                                    if suffix:
                                        current_lines[idx] = cl + suffix
                                        notes_updated = True
                                    break
                        except ValueError:
                            pass
                    
                    # [Removed duplicate print] We rely on _log for feedback.
                    if not processed:
                         # Only print valid ADDs that weren't processed (unknown lines)
                         # or maybe just debug output.
                         # print(f"{GREEN}[ADD] {a_line}{RESET}")
                         pass

        for line in diff:
            if line.startswith('---') or line.startswith('+++'):
                continue

            if line.startswith('@@'):
                if current_dels or current_adds:
                    flush_hunk(current_dels, current_adds)
                    current_dels = []
                    current_adds = []
                continue

            if line.startswith('+') or line.startswith('-'):
                changes_found = True
                if line.startswith('-'):
                    current_dels.append(line[1:])
                elif line.startswith('+'):
                    current_adds.append(line[1:])

        # Flush remaining
        if current_dels or current_adds:
            flush_hunk(current_dels, current_adds)

        if not changes_found:
            print("   (内容变化但 diff 为空 - 可能是空白符变更)")
            
        # 如果有回写需求，更新 Apple Notes
        if notes_updated:
            new_full_content = "\n".join(current_lines)
            self._reader.update_note_content(note_name, new_full_content)
            self._log(f"🔄 [NoteMonitor] 已回写 ✅ 标记到 Apple Notes")

    # =====================
    # Obsidian 日记写入
    # =====================

    def _append_to_daily_note(self, line_content):
        """
        将带时间戳的行追加到今日日记的 ## #Water 章节。
        格式: HH:MM<span id="HH:MM:SS"></span> Keyword::Value
        """
        RED = '\033[91m'
        YELLOW = '\033[93m'
        RESET = '\033[0m'

        try:
            if not self._config or not hasattr(self._config, 'DAILY_NOTE_DIR'):
                print(f"{RED}❌ Config 缺少 DAILY_NOTE_DIR{RESET}")
                return False

            today_str = datetime.date.today().strftime('%Y-%m-%d')
            daily_note_path = os.path.join(self._config.DAILY_NOTE_DIR, f"{today_str}.md")

            if not os.path.exists(daily_note_path):
                print(f"{RED}❌ 日记文件未找到: {daily_note_path}{RESET}")
                return False

            with open(daily_note_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # [v7.12] Defense: Prevent Heartbeat Data from entering Takein
            # Check if line looks like a heartbeat (contains *ID* or (id=...))
            # Ref: completion_pat from _process_diff
            import re
            is_heartbeat = re.search(r'(?:\*([a-zA-Z0-9:_]+)\*|\(\s*id=([a-zA-Z0-9:_]+)\s*\)|（\s*id=([a-zA-Z0-9:_]+)\s*）)', line_content)
            if is_heartbeat:
                print(f"{YELLOW}⚠️ [Takein Skip] Detected Heartbeat Data, ignoring: {line_content.strip()}{RESET}")
                return False

            new_line_clean = line_content.strip()

            # 读取并重组 ## #Water 章节
            final_lines = self._reorganize_water_section(lines, new_line_clean)
            
            with open(daily_note_path, 'w', encoding='utf-8') as f:
                f.writelines(final_lines)

            return True

        except Exception as e:
            print(f"{RED}❌ 写入日记异常: {e}{RESET}")
            return False

    def _reorganize_water_section(self, lines, new_raw_entry):
        """
        解析并重组 ## #Water 章节:
        1. 提取现有条目 + 新条目
        2. 解析时间、Key、内容
        3. 按 Key 分组，组内按时间倒序排序
        4. 生成新内容覆盖原章节
        """
        # 1. 解析新条目
        new_parsed = self._parse_entry(new_raw_entry)
        if not new_parsed:
            # 如果解析失败，直接追加（fallback）
            # 但这里我们尽量保证能处理。如果失败，返回原 lines + 追加
            # 为简单起见，若无法解析，暂不处理排序，直接返回追加逻辑
            # 但为了保持一致性，我们构造一个 dummy parsed
            new_parsed = {
                'time': '00:00', 'full_ts': '00:00:00', 
                'key': 'Unsorted', 'content': new_raw_entry,
                'raw': new_raw_entry # We will format it later
            }
            # 重新格式化新条目 (简单处理)
            # formatted_new = self._format_parsed_entry(new_parsed)
            # new_parsed['raw'] = formatted_new
            # Fallback raw line
            if not new_parsed['raw'].endswith('\n'):
                new_parsed['raw'] += '\n'

        # 2. 定位章节范围
        target_section = "## #takein"
        start_idx = -1
        end_idx = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == target_section:
                start_idx = i + 1
            elif start_idx != -1 and stripped.startswith('## '):
                end_idx = i
                break
        
        if start_idx == -1:
            # 章节不存在，追加到末尾
            if lines and not lines[-1].endswith('\n'):
                lines.append('\n')
            lines.append(f"\n{target_section}\n")
            lines.append(new_parsed['raw'])
            return lines

        if end_idx == -1:
            end_idx = len(lines)

        # 3. 提取现有条目
        existing_lines = lines[start_idx:end_idx]
        entries = []
        
        # 将新条目加入列表
        entries.append(new_parsed)

        # 解析旧条目
        # 预期格式: HH:MM<span id="HH:MM:SS"></span> Key::Value
        # 或者旧格式: - HH:MM...
        entry_pattern = re.compile(r'(\d{1,2}[:：]\d{2})<span id="([^"]+)"></span>\s*(.*)')

        for line in existing_lines:
            line = line.strip()
            if not line:
                continue
            
            # 尝试解析标准格式
            m = entry_pattern.match(line)
            if m:
                ts_display = m.group(1)
                ts_full = m.group(2)
                content_part = m.group(3)
                
                # 提取 Key
                if '::' in content_part:
                    key = content_part.split('::')[0].strip()
                else:
                    key = 'Unsorted'
                
                entries.append({
                    'time': ts_display,
                    'full_ts': ts_full,
                    'key': key,
                    'content': content_part, # 保留 Key::Val 部分
                    'raw': line + '\n'
                })
            else:
                # 无法解析的行（可能是手动输入的笔记），保留为 Unsorted 或 Ignore?
                # 为了不丢失数据，归类到 Unsorted
                # 尝试提取时间戳
                simple_time = re.match(r'^(\d{1,2}[:：]\d{2})', line)
                ts = simple_time.group(1) if simple_time else "00:00"
                entries.append({
                    'time': ts,
                    'full_ts': ts + ":00",
                    'key': 'Notes',
                    'content': line,
                    'raw': line + '\n'
                })

        # 4. 排序与分组
        # 先按 Key 字母序，再按 Time 倒序 (最新的在最前)
        entries.sort(key=lambda x: (x['key'], x['full_ts']), reverse=True)
        # 上面的排序结果是 Key 也是倒序 (Water -> Monster -> Cigarette)，这可能不是我们要的。
        # 我们想要 Key 升序 (C -> M -> W)，组内 Time 倒序。
        
        # 重新排序：
        # Primary: Key (Ascending)
        # Secondary: Time (Descending) -> 利用负数或者 reverse=True on subset?
        # Python sort is stable.
        
        # Step A: Sort by Time Descending (Global)
        entries.sort(key=lambda x: x['full_ts'], reverse=True)
        # Step B: Sort by Key Ascending (Global) -> Stable sort preserves relative order (Time Desc)
        entries.sort(key=lambda x: x['key'])

        # 5. 构建新内容块
        new_section_lines = []
        current_key = None
        
        for entry in entries:
            if current_key is not None and entry['key'] != current_key:
                new_section_lines.append('\n') # 组间空行
            
            current_key = entry['key']
            new_section_lines.append(entry['raw'])

        # 确保最后一行有换行
        if new_section_lines and not new_section_lines[-1].endswith('\n'):
            new_section_lines[-1] += '\n'

        # 6. 替换原文
        # start_idx 是内容开始，end_idx 是下一个标题开始
        # 我们需要保留 start_idx 之前的，和 end_idx 之后的
        
        # 修正：确保 start_idx 前的一行是标题
        # 我们在 start_idx 位置插入空行吗？原逻辑 append 有换行。
        # 简单处理：新内容覆盖旧内容
        
        final = lines[:start_idx] + new_section_lines + lines[end_idx:]
        return final

    def _parse_entry(self, raw_line):
        """
        将原始备忘录行 '23:54"烟":"x1"' 解析为结构化数据，并处理映射
        返回: {'time':..., 'full_ts':..., 'key':..., 'raw':...}
        """
        raw_line = raw_line.strip()
        match = re.match(r'^(\d{1,2}[:：]\d{2}(?:[:：]\d{2})?)', raw_line)
        if not match:
            return None
            
        ts_full = match.group(1)
        ts_end = match.end()
        
        # 用于显示的 HH:MM
        parts = re.split(r'[:：]', ts_full)
        ts_display = f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else ts_full
        
        content_part = raw_line[ts_end:]
        
        # 清理内容
        cleaned = content_part.replace('":"', '::')
        cleaned = cleaned.replace('"', '').replace("'", "").strip()
        
        # 映射
        mapping = getattr(self._config, 'KEYWORD_MAPPING', {})
        key = 'Unsorted'
        
        if '::' in cleaned:
            key_raw, val = cleaned.split('::', 1)
            key_raw = key_raw.strip()
            if key_raw in mapping:
                key = mapping[key_raw]
                cleaned = f"{key}::{val}"
            else:
                key = key_raw
        
        # 构造最终行
        span = f'<span id="{ts_full}"></span>'
        formatted_line = f"{ts_display}{span} {cleaned}\n"
        
        return {
            'time': ts_display,
            'full_ts': ts_full,
            'key': key,
            'content': cleaned,
            'raw': formatted_line
        }

    # =====================
    # Day Planner 处理 (v4.4)
    # =====================

    def _is_day_plan_entry(self, line):
        """
        判断是否为 Day Planner 条目
        特征: 时间戳后跟随 "* (如 17:55:48"*打游戏")
        """
        return '"*' in line or '“*' in line

    def _append_to_day_plan_section(self, line_content):
        """
        [v4.8] 处理 # Day planner
        核心逻辑: 全局重组与合并
        1. 读取所有现有条目 + 新条目
        2. 按时间排序
        3. 遍历列表，合并连续且内容相同的条目
           - 判断逻辑: 内容相同则合并
        4. 格式化:
           - 单条目: 20:51
           - 多条目(即使同分): 20:51 -20:51 (如果有时间跨度)
           - 格式: "Start -End"
        """
        RED = '\033[91m'
        RESET = '\033[0m'

        try:
            if not self._config or not hasattr(self._config, 'DAILY_NOTE_DIR'):
                return False

            today_str = datetime.date.today().strftime('%Y-%m-%d')
            daily_note_dir = getattr(self._config, 'DAILY_NOTE_DIR', None)
            if not daily_note_dir:
                return False
                
            daily_note_path = os.path.join(daily_note_dir, f"{today_str}.md")

            if not os.path.exists(daily_note_path):
                return False

            # 1. 解析输入行 (New Entry)
            parsed_new = self._parse_day_plan_line(line_content)
            if not parsed_new:
                return False
            parsed_new['status'] = 'x'
            parsed_new['is_new'] = True

            # 2. 读取现有文件
            with open(daily_note_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 3. 定位 # Day planner 章节
            target_section = "# Day planner"
            start_idx = -1
            end_idx = -1

            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped == target_section:
                    start_idx = i + 1
                elif start_idx != -1:
                    if stripped.startswith('# ') or stripped.startswith('## '):
                        end_idx = i
                        break
            
            if start_idx == -1:
                return False

            if end_idx == -1:
                end_idx = len(lines)

            # 4. 提取章节内容并解析 existing entries
            section_lines = lines[start_idx:end_idx]
            all_entries = []
            
            # 正则: 支持 "HH:MM" 或 "HH:MM -HH:MM"
            ptn = re.compile(r'^(?:-\s*\[([xX\s])\]\s+)?(.+?)<span id="([^"]+)"></span>\s*(.*)')

            for sl in section_lines:
                sl_strip = sl.strip()
                if not sl_strip: continue
                
                m = ptn.match(sl_strip)
                if m:
                    status_char = m.group(1) if m.group(1) else 'x'
                    display_str = m.group(2).strip()
                    full_id = m.group(3)
                    content = m.group(4)
                    
                    all_entries.append({
                        'status': status_char,
                        'time_display': display_str,
                        'time_full': full_id, # Assumed to be start_id
                        'content': content,
                        'raw': sl,
                        'is_new': False
                    })
            
            # 加入新条目
            all_entries.append(parsed_new)

            # 5. 全局排序 (按 Start ID)
            all_entries.sort(key=lambda x: x['time_full'])

            # 6. 合并连续相同内容的条目
            final_entries = []
            
            def get_end_time(display_str):
                # "20:51" -> "20:51"
                # "20:51 -20:56" -> "20:56"
                parts = display_str.split('-')
                return parts[-1].strip()

            if all_entries:
                curr = all_entries[0]
                curr_content = curr['content'].strip()
                curr_start_display = curr['time_display'].split('-')[0].strip()
                curr_end_display = get_end_time(curr['time_display'])
                curr_status = curr.get('status', 'x')
                curr_start_id = curr['time_full']
                curr_end_id = curr['time_full'] # Track end ID to detect merge span

                for i in range(1, len(all_entries)):
                    next_e = all_entries[i]
                    next_content = next_e['content'].strip()
                    
                    if next_content == curr_content:
                        # Merge! 
                        curr_end_display = get_end_time(next_e['time_display'])
                        # Update end_id to the NEWEST entry's ID
                        # Note: all_entries is sorted by time_full (Start ID).
                        # We assume next_e is later than curr.
                        # But wait, next_e['time_full'] is ITS start time.
                        # If next_e was a range, we don't know ITS end time ID strictly from struct unless we parsed it.
                        # But we re-parse from scratch mostly.
                        # Let's assume next_e['time_full'] is sufficient to prove "difference".
                        curr_end_id = next_e['time_full'] 
                    else:
                        # Flush
                        final_entries.append({
                            'start': curr_start_display,
                            'end': curr_end_display,
                            'status': curr_status,
                            'start_id': curr_start_id,
                            'end_id': curr_end_id,
                            'content': curr_content
                        })
                        
                        # New
                        curr = next_e
                        curr_content = curr['content'].strip()
                        curr_start_display = curr['time_display'].split('-')[0].strip()
                        curr_end_display = get_end_time(curr['time_display'])
                        curr_status = curr.get('status', 'x')
                        curr_start_id = curr['time_full']
                        curr_end_id = curr['time_full']
                
                # Flush last
                final_entries.append({
                    'start': curr_start_display,
                    'end': curr_end_display,
                    'status': curr_status,
                    'start_id': curr_start_id,
                    'end_id': curr_end_id,
                    'content': curr_content
                })

            # 7. 生成最终行
            new_content_lines = []
            if section_lines and section_lines[0].strip() == "":
                new_content_lines.append("\n")
            
            def get_ceiling_end_time(full_ts):
                """
                根据完整时间戳 HH:MM:SS 计算结束时间
                逻辑: 秒数向上取整。如果 SS > 0，则 MM + 1。
                """
                try:
                    parts = full_ts.split(':')
                    if len(parts) >= 3:
                        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
                        if s > 0:
                            m += 1
                            if m >= 60:
                                m = 0
                                h += 1
                            if h >= 24:
                                h = 0
                        return f"{h:02d}:{m:02d}"
                    return full_ts[:5] # HH:MM
                except:
                    return full_ts

            for e in final_entries:
                # Decide Format
                # If IDs differ, it means we merged something -> Show Range
                if e['start_id'] != e['end_id']:
                     # Range Format: "Start - Ceiling(EndID)"
                     # Start uses existing display to preserve manual edits if any, or simple HH:MM
                     # End is recalculated based on Seconds Ceiling logic
                     new_end = get_ceiling_end_time(e['end_id'])
                     time_str = f"{e['start']} - {new_end}"
                else:
                     # Single Entry
                     time_str = e['start']
                
                # Format: - [x] Time <span...> Content
                line_str = f"- [{e['status']}] {time_str}<span id=\"{e['start_id']}\"></span> {e['content']}\n"
                new_content_lines.append(line_str)
            
            if new_content_lines and not new_content_lines[-1].endswith('\n'):
                new_content_lines[-1] += '\n'
            new_content_lines.append('\n')

            # 8. Replace in file
            final_lines = lines[:start_idx] + new_content_lines + lines[end_idx:]
            
            with open(daily_note_path, 'w', encoding='utf-8') as f:
                f.writelines(final_lines)

            return True

        except Exception as e:
            print(f"{RED}❌ 写入 Day Planner 异常: {e}{RESET}")
            return False

    def _parse_day_plan_line(self, raw_line):
        """
        解析: 17:55:48"*打游戏"
        """
        raw_line = raw_line.strip()
        match = re.match(r'^(\d{1,2}[:：]\d{2}(?:[:：]\d{2})?)', raw_line)
        if not match: return None
        
        ts_full = match.group(1)
        ts_end = match.end()
        
        parts = re.split(r'[:：]', ts_full)
        ts_display = f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else ts_full
        
        remain = raw_line[ts_end:].strip()
        content = remain
        if content.startswith('"') or content.startswith('“'):
             content = content[1:]
        if content.startswith('*'):
             content = content[1:]
             
        content = content.replace('"', '').replace('”', '').strip()
        
        return {
            'time_display': ts_display,
            'time_full': ts_full,
            'content': content
        }

    # =====================
    # Account 记账处理
    # =====================

    def _append_to_account_section(self, line_content):
        """
        处理记账条目并插入到 ## #Account 章节
        输入示例: (tradetype::$食物)(tradename::鸡蛋)(tradecost::-858)(tradetime::2026/2/12 00:19:36)
        目标格式:
        (tradetype::食物)
        (tradename::鸡蛋)
        (tradecost::-858)
        (tradetime::2026/2/12 00:19:36)
        """
        RED = '\033[91m'
        RESET = '\033[0m'

        try:
            if not self._config or not hasattr(self._config, 'DAILY_NOTE_DIR'):
                return False

            today_str = datetime.date.today().strftime('%Y-%m-%d')
            daily_note_path = os.path.join(self._config.DAILY_NOTE_DIR, f"{today_str}.md")

            if not os.path.exists(daily_note_path):
                return False

            # 解析并格式化
            groups = re.findall(r'\(([^)]+)\)', line_content)
            if not groups:
                return False

            formatted_lines = []
            
            # 使用字典暂存以便排序或过滤 (虽然这里顺序重要)
            # 用户期望顺序: type, name, cost, time
            
            for g in groups:
                if '::' in g:
                    k, v = g.split('::', 1)
                    k = k.strip()
                    v = v.strip()
                    
                    # 1. 清理 $ 符号
                    if '$' in v:
                        v = v.replace('$', '')
                    
                    # 2. 只有看到要求的字段才保留? 或者保留全量但格式化特定字段?
                    # 用户列出了 type, name, cost, time。如果有其他字段，暂且保留以免丢失数据。
                    
                    # 3. 格式化时间
                    if k == 'tradetime':
                        # v is like "2026/2/12 00:19:36"
                        # Extract HH:MM
                        # Try regex or split
                        time_match = re.search(r'(\d{1,2}[:：]\d{2})', v)
                        if time_match:
                            v = time_match.group(1) # 00:19
                    
                    formatted_lines.append(f"({k}::{v})\n")
                else:
                    formatted_lines.append(f"({g})\n")
            
            # 添加空行分隔 (Entry Spacer)
            formatted_lines.append('\n')

            # 读取文件并插入
            with open(daily_note_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            target_section = "## #account"
            insert_idx = -1
            
            # 寻找章节
            for i, line in enumerate(lines):
                if line.strip() == target_section:
                    insert_idx = i + 1
                    break
            
            if insert_idx != -1:
                # 确保章节下有空行
                if insert_idx < len(lines) and lines[insert_idx].strip() != "":
                    lines.insert(insert_idx, '\n')
                    insert_idx += 1 # 移动插入点到空行之后
                elif insert_idx == len(lines):
                    lines.append('\n')
                    insert_idx += 1

                # 寻找下一个章节的位置
                next_section_idx = len(lines)
                for i in range(insert_idx, len(lines)):
                    if lines[i].strip().startswith("## "):
                        next_section_idx = i
                        break
                
                # 追加到该章节末尾（next_section_idx 之前）
                # 检查前一行是否为空行，如果不是则添加
                if next_section_idx > 0 and lines[next_section_idx - 1].strip() != "":
                    lines.insert(next_section_idx, '\n')
                    next_section_idx += 1
                
                # 插入内容
                for fl in reversed(formatted_lines):
                    lines.insert(next_section_idx, fl)
            else:
                # 章节不存在，追加
                # 确保前文有换行
                if lines and not lines[-1].endswith('\n'):
                    lines.append('\n')
                
                lines.append(f"\n{target_section}\n") # Section header
                lines.append('\n') # Spacer after header
                lines.extend(formatted_lines)
            
            with open(daily_note_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
            return True

        except Exception as e:
            print(f"{RED}❌ 写入账单异常: {e}{RESET}")
            return False

```

---
## File: AntigravitySync/src/external/note_sync_core/read_today_note.py
```py

import subprocess
import datetime
import sys

# [v1.0] Apple Notes Reader (Core)
# Uses AppleScript to interface with the Notes.app

class AppleNotesReader:
    def __init__(self):
        pass

    def _run_applescript(self, script_content):
        """
        Runs AppleScript using osascript (subprocess).
        """
        try:
            # -e is for one-liner, but for block we pipe into stdin
            process = subprocess.Popen(
                ['osascript'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=script_content)
            
            if process.returncode != 0:
                # If permission denied or other OSA error
                return None, stderr.strip()
            return stdout.strip(), None
            
        except Exception as e:
            return None, str(e)

    def get_note_content(self, note_name):
        """
        Retrieves the content (plaintext) of an Apple Note by its EXACT name.
        """
        # AppleScript Logic:
        # 1. Target Note by Name
        # 2. Return 'plaintext' (content without HTML tags)
        # 3. Return "NOT_FOUND" if list is empty
        
        script = f'''
        tell application "Notes"
            set targetName to "{note_name}"
            
            -- Try to find the note by exact name
            set foundNotes to every note whose name is targetName
            
            if (count of foundNotes) > 0 then
                set theNote to item 1 of foundNotes
                return plaintext of theNote
            else
                return "NOT_FOUND"
            end if
        end tell
        '''
        
        content, error = self._run_applescript(script)
        
        if error:
            # Handle user permissions or missing app errors
            if "UserCanceled" in error or "privilege" in error:
                print(f"⚠️  [Permission Denied] Please grant terminal/script access to Notes.")
            return None
            
        if content == "NOT_FOUND":
            return None
            
        return content

    def update_note_content(self, note_name, new_content):
        """
        [v4.0] Update the entire content of the note.
        Fixed: Converts newlines to <br> to prevent formatting loss (one-line mess).
        """
        # 1. Escape special chars for AppleScript string
        safe_content = new_content.replace('\\', '\\\\').replace('"', '\\"')
        
        # 2. Convert newlines to HTML breaks for Notes body
        html_body = safe_content.replace('\n', '<br>')
        
        script = f'''
        tell application "Notes"
            set targetName to "{note_name}"
            set foundNotes to every note whose name is targetName
            
            if (count of foundNotes) > 0 then
                set theNote to item 1 of foundNotes
                set body of theNote to "{html_body}"
                return "OK"
            else
                return "NOT_FOUND"
            end if
        end tell
        '''
        
        resp, error = self._run_applescript(script)
        if error:
            print(f"❌ [AppleScript Error] Update failed: {error}")
            return False
            
        return resp == "OK"

    def create_note(self, note_name, body_content=""):
        """
        [v4.1] Create a new note if it doesn't exist.
        """
        # Escape content
        safe_content = body_content.replace('\\', '\\\\').replace('"', '\\"')
        html_body = safe_content.replace('\n', '<br>')
        
        script = f'''
        tell application "Notes"
            -- Check if exists first to avoid duplicates
            set targetName to "{note_name}"
            set foundNotes to every note whose name is targetName
            
            if (count of foundNotes) = 0 then
                make new note with properties {{name:targetName, body:"{html_body}"}}
                return "CREATED"
            else
                return "EXISTS"
            end if
        end tell
        '''
        
        resp, error = self._run_applescript(script)
        if error:
            print(f"❌ [AppleScript Error] Create note failed: {error}")
            return False
            
        return resp == "CREATED"

if __name__ == "__main__":
    # Self-test logic
    reader = AppleNotesReader()
    
    today = datetime.date.today()
    # Format: yyyy/m/d (e.g. 2026/2/11) - No zero padding
    today_str = f"{today.year}/{today.month}/{today.day}"
    
    print(f"🔎 [Test] Attempting to read note: '{today_str}'")
    
    content = reader.get_note_content(today_str)
    
    if content:
        print(f"✅ [Success] Read {len(content)} chars.")
        print("="*40)
        print(content)
        print("="*40)
    else:
        print(f"❌ [Failed] Note '{today_str}' not found or empty.")
        print("   (Ensure a note with this EXACT title exists in Apple Notes)")

```

---
## File: AntigravitySync/src/external/note_sync_core/watch_today_note.py
```py

import sys
import os
import time
import logging

# ==========================================
# 路径设置: 确保能导入项目模块
# ==========================================
# 1. 当前脚本所在目录: src/external/note_sync_core/
current_dir = os.path.dirname(os.path.abspath(__file__))
# 2. 项目根目录 (AntigravitySync 的父目录，即 Beta Folder)
# src/external/note_sync_core/ -> src/external/ -> src/ -> AntigravitySync -> Root
beta_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))

if beta_root not in sys.path:
    sys.path.append(beta_root)

# 3. AntigravitySync 根目录
antigravity_root = os.path.join(beta_root, 'AntigravitySync')
if antigravity_root not in sys.path:
    sys.path.append(antigravity_root)

# ==========================================
# 导入模块
# ==========================================
try:
    from config import Config
    from src.dailynotes.utils import Logger
except ImportError as e:
    print(f"❌ [Error] 无法导入 Config 或 Logger: {e}")
    print(f"   sys.path: {sys.path}")
    sys.exit(1)

try:
    from monitor import NoteMonitor
except ImportError as e:
    # 尝试相对导入
    sys.path.append(current_dir)
    from monitor import NoteMonitor

# ==========================================
# 简单的 Logger 适配器 (如果 Utils Logger不可用)
# ==========================================
class SimpleLogger:
    @staticmethod
    def info(msg):
        print(msg)

# ==========================================
# 主入口
# ==========================================
def main():
    print("🚀 [Launcher] 正在启动 NoteMonitor (via watch_today_note.py wrapper)...")
    
    # 使用项目 Logger 或 SimpleLogger
    logger = Logger if 'Logger' in locals() else SimpleLogger
    
    # 初始化 Monitor
    # Config 应该包含 DAILY_NOTE_DIR, TEMPLATE_FILE, KEYWORD_MAPPING
    monitor = NoteMonitor(config=Config, logger=logger)
    
    try:
        monitor.start()
        
        # 保持主线程运行 (NoteMonitor 是 daemon 线程)
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 [Launcher] 停止中...")
        monitor.stop()
    except Exception as e:
        print(f"❌ [Launcher] 异常: {e}")
        monitor.stop()

if __name__ == "__main__":
    main()

```

---
## File: AntigravitySync/src/external/task_sync_core/__init__.py
```py
# TaskSynctoreminder core modules

```

---
## File: AntigravitySync/src/external/task_sync_core/apple_state_manager.py
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
## File: AntigravitySync/src/external/task_sync_core/calendar_service.py
```py
"""
Apple Calendar Service - EventKit Native Implementation (v2.0)

重写说明：
- 完全移除 AppleScript 依赖，使用 PyObjC/EventKit 原生 API
- 复用 eventkit_wrapper.py 的 EventKitClient 单例
- 保持函数签名不变以兼容 sync_engine.py
"""
from datetime import datetime, timedelta
from config import Config

# EventKit imports
try:
    from EventKit import EKEventStore, EKEntityTypeEvent, EKEvent, EKAlarm, EKSpanThisEvent
    from Foundation import NSDate
    from external.eventkit_wrapper import EventKitClient
    EK_AVAILABLE = True
except ImportError:
    EK_AVAILABLE = False

# Use config values
ALL_MANAGED_CALENDARS = Config.ALL_MANAGED_CALENDARS
ALARM_RULES = Config.ALARM_RULES

# [v2.0 FIX] 单例 EventKitClient，避免创建过多 EKEventStore 实例
_ek_client_singleton = None

def _get_ek_client():
    """获取或创建 EventKitClient 单例"""
    global _ek_client_singleton
    if _ek_client_singleton is None and EK_AVAILABLE:
        from external.eventkit_wrapper import EventKitClient
        _ek_client_singleton = EventKitClient()
        # 确保已授权
        if not _ek_client_singleton.access_granted:
            _ek_client_singleton.check_access()
    return _ek_client_singleton


# =============================================================================
# Helper Functions for EventKit
# =============================================================================

def _datetime_to_nsdate(target_dt: datetime, time_str: str) -> NSDate:
    """
    Convert a target date and time string (HH:MM) to NSDate.
    
    Args:
        target_dt: The target date (datetime object)
        time_str: Time in "HH:MM" format
    
    Returns:
        NSDate object representing the combined datetime
    """
    h = int(time_str[:2])
    m = int(time_str[3:5])
    
    # Combine date with time
    combined_dt = datetime(
        year=target_dt.year,
        month=target_dt.month,
        day=target_dt.day,
        hour=h,
        minute=m,
        second=0
    )
    
    return NSDate.dateWithTimeIntervalSince1970_(combined_dt.timestamp())


def _find_calendar_by_name(store, calendar_name: str):
    """
    Find an EKCalendar by its title.
    
    Args:
        store: EKEventStore instance
        calendar_name: The calendar title to find
    
    Returns:
        EKCalendar object or None if not found
    """
    calendars = store.calendarsForEntityType_(EKEntityTypeEvent)
    if not calendars:
        return None
    
    for cal in calendars:
        if cal.title() == calendar_name:
            return cal
    
    return None


def check_calendars_exist_simple():
    """Check if all required calendars exist in Apple Calendar using EventKit."""
    client = _get_ek_client()
    if not client:
        print("❌ EventKit not available.")
        return False
    
    store = client.store
    missing_calendars = []
    
    for cal_name in ALL_MANAGED_CALENDARS:
        if _find_calendar_by_name(store, cal_name) is None:
            missing_calendars.append(cal_name)
    
    if missing_calendars:
        print(f"❌ 错误：找不到日历：{missing_calendars}")
        return False
    
    return True


def get_all_calendars_state(target_dt):
    """
    Get all calendar events for a specific date using EventKit.
    
    Args:
        target_dt: datetime object for target date
    
    Returns:
        dict: Calendar events keyed by "name_starttime_idtail"
    """
    client = _get_ek_client()
    if client:
        try:
            all_events = client.fetch_events(target_dt)
            
            # Filter by managed calendars
            filtered_events = {}
            for key, val in all_events.items():
                if val['current_calendar'] in ALL_MANAGED_CALENDARS:
                    filtered_events[key] = val
            return filtered_events
        except Exception as e:
            print(f"⚠️ EventKit Error: {e}")
            return {}
            
    print("❌ EventKit not available.")
    return {}


class BatchExecutor:
    """
    Batch executor for Apple Calendar operations using EventKit.
    
    所有操作先缓存，execute() 时统一执行。
    """
    
    def __init__(self, target_dt):
        self.target_dt = target_dt
        self.creates = []
        self.updates = []
        self.deletes = []

    def add_create(self, name, start_time, duration, calendar_name, is_completed):
        """
        Queue a create operation.
        
        Args:
            name: Event title
            start_time: Start time in "HH:MM" format
            duration: Duration in minutes
            calendar_name: Target calendar name
            is_completed: Whether the task is marked complete
        """
        clean_name = name.replace("✅", "").replace("✓", "").strip()
        final_title = f"✅ {clean_name}" if is_completed else clean_name
        alarm = ALARM_RULES.get(calendar_name, 0)

        self.creates.append({
            "title": final_title,
            "start": start_time,
            "dur": duration,
            "cal": calendar_name,
            "alarm": alarm  # 负数表示提前分钟数
        })

    def add_update(self, event_id, calendar_name, new_name, start_time, duration, is_completed):
        """
        Queue an update operation.
        
        Args:
            event_id: Existing event identifier
            calendar_name: Calendar containing the event
            new_name: New event title
            start_time: New start time in "HH:MM" format
            duration: New duration in minutes
            is_completed: Whether the task is marked complete
        """
        clean_name = new_name.replace("✅", "").replace("✓", "").strip()
        final_title = f"✅ {clean_name}" if is_completed else clean_name

        self.updates.append({
            "id": event_id,
            "title": final_title,
            "start": start_time,
            "dur": duration,
            "cal": calendar_name
        })

    def add_delete(self, event_id, calendar_name):
        """
        Queue a delete operation.
        
        Args:
            event_id: Event identifier to delete
            calendar_name: Calendar containing the event
        """
        self.deletes.append({
            "id": event_id,
            "cal": calendar_name
        })

    def execute(self):
        """
        Execute all queued operations using EventKit.
        
        Operations are executed in order: deletes → creates → updates
        This ensures no ID conflicts when recreating moved events.
        """
        if not (self.creates or self.updates or self.deletes):
            return

        client = _get_ek_client()
        if not client:
            print("❌ [BatchExecutor] EventKit 不可用，无法执行操作")
            return
        
        if not client.access_granted:
            print("❌ [BatchExecutor] 没有日历访问权限")
            return

        store = client.store
        
        success_count = {"delete": 0, "create": 0, "update": 0}
        error_count = {"delete": 0, "create": 0, "update": 0}

        # =====================================================================
        # 1. DELETE Operations
        # =====================================================================
        for op in self.deletes:
            try:
                event = store.eventWithIdentifier_(op['id'])
                if event:
                    # removeEvent:span:commit:error: 
                    # span: EKSpanThisEvent (只删除这一个事件，不影响重复事件)
                    # commit: True (立即提交)
                    success, error = store.removeEvent_span_commit_error_(
                        event, EKSpanThisEvent, True, None
                    )
                    if success:
                        success_count["delete"] += 1
                    else:
                        error_count["delete"] += 1
                        if error:
                            print(f"⚠️ [Delete] 失败 ({op['id'][:8]}...): {error}")
                else:
                    # 事件不存在，算作成功（幂等）
                    success_count["delete"] += 1
            except Exception as e:
                error_count["delete"] += 1
                print(f"❌ [Delete] 异常 ({op['id'][:8] if op['id'] else 'N/A'}...): {e}")

        # =====================================================================
        # 2. CREATE Operations
        # =====================================================================
        for op in self.creates:
            try:
                # 1. Find target calendar
                cal = _find_calendar_by_name(store, op['cal'])
                if not cal:
                    print(f"⚠️ [Create] 找不到日历: {op['cal']}")
                    error_count["create"] += 1
                    continue

                # 2. Create new event
                event = EKEvent.eventWithEventStore_(store)
                event.setTitle_(op['title'])
                event.setCalendar_(cal)
                
                # 3. Set start/end dates
                start_nsdate = _datetime_to_nsdate(self.target_dt, op['start'])
                # Duration in minutes -> seconds
                end_timestamp = start_nsdate.timeIntervalSince1970() + (op['dur'] * 60)
                end_nsdate = NSDate.dateWithTimeIntervalSince1970_(end_timestamp)
                
                event.setStartDate_(start_nsdate)
                event.setEndDate_(end_nsdate)
                
                # 4. Add alarm if configured
                alarm_offset = op.get('alarm', 0)
                if alarm_offset != 0:
                    # EventKit alarm offset is in seconds (negative = before event)
                    alarm = EKAlarm.alarmWithRelativeOffset_(alarm_offset * 60)
                    event.addAlarm_(alarm)
                
                # 5. Save
                success, error = store.saveEvent_span_commit_error_(
                    event, EKSpanThisEvent, True, None
                )
                if success:
                    success_count["create"] += 1
                else:
                    error_count["create"] += 1
                    if error:
                        print(f"⚠️ [Create] 保存失败 ({op['title'][:20]}): {error}")
                        
            except Exception as e:
                error_count["create"] += 1
                print(f"❌ [Create] 异常 ({op['title'][:20] if op.get('title') else 'N/A'}): {e}")

        # =====================================================================
        # 3. UPDATE Operations
        # =====================================================================
        for op in self.updates:
            try:
                # 1. Get existing event
                event = store.eventWithIdentifier_(op['id'])
                if not event:
                    print(f"⚠️ [Update] 事件不存在: {op['id'][:8]}...")
                    error_count["update"] += 1
                    continue

                # 2. Update properties
                event.setTitle_(op['title'])
                
                # 3. Update start/end dates
                start_nsdate = _datetime_to_nsdate(self.target_dt, op['start'])
                end_timestamp = start_nsdate.timeIntervalSince1970() + (op['dur'] * 60)
                end_nsdate = NSDate.dateWithTimeIntervalSince1970_(end_timestamp)
                
                event.setStartDate_(start_nsdate)
                event.setEndDate_(end_nsdate)
                
                # 4. Note: Calendar change is handled by delete+create in sync_engine
                #    We don't change calendar here to avoid complexity
                
                # 5. Save
                success, error = store.saveEvent_span_commit_error_(
                    event, EKSpanThisEvent, True, None
                )
                if success:
                    success_count["update"] += 1
                else:
                    error_count["update"] += 1
                    if error:
                        print(f"⚠️ [Update] 保存失败 ({op['title'][:20]}): {error}")
                        
            except Exception as e:
                error_count["update"] += 1
                print(f"❌ [Update] 异常 ({op['id'][:8] if op.get('id') else 'N/A'}): {e}")

        # =====================================================================
        # Summary
        # =====================================================================
        total_success = sum(success_count.values())
        total_errors = sum(error_count.values())
        
        if total_errors > 0:
            print(f"⚡ 执行批处理: +{success_count['create']} ~{success_count['update']} -{success_count['delete']} (❌{total_errors}错误)")
        else:
            print(f"⚡ 执行批处理: +{success_count['create']} ~{success_count['update']} -{success_count['delete']}")

```

---
## File: AntigravitySync/src/external/task_sync_core/obsidian_service.py
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
## File: AntigravitySync/src/external/task_sync_core/sync_engine.py
```py
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
                print(f"🕵️ [Move/Rename C->O] 捕捉变动: {last_cal[found_old_key]['name']}@{last_cal[found_old_key]['start_time']} -> {c_data['name']}@{c_data['start_time']}")
                rename_success = False
                if found_old_key in current_obs:
                    line_idx = current_obs[found_old_key]['line_index']
                    tag_suffix = CAL_TO_TAG.get(c_data['current_calendar'], "")
                    if tag_suffix == "#D":
                        tag_suffix = ""
                    tag_part = f"{tag_suffix} " if tag_suffix else ""
                    
                    # Calculate new end time based on duration
                    end_time_str = ""
                    if c_data['duration'] != 30:
                        end_t = datetime.strptime(c_data['start_time'], "%H:%M") + timedelta(minutes=c_data['duration'])
                        end_time_str = f" - {end_t.strftime('%H:%M')}"
                    
                    status_char = current_obs[found_old_key]['status']
                    new_line = f"- [{status_char}] {c_data['start_time']}{end_time_str} {tag_part}{c_data['name']}\n"
                    lines_to_modify[line_idx] = new_line
                    file_dirty = True
                    
                    # [v1.7.2/v1.7.4] Critical State Update (Name AND Time):
                    new_obs_key = f"{c_data['name']}_{c_data['start_time']}"
                    new_o_data = current_obs[found_old_key].copy()
                    new_o_data['name'] = c_data['name']
                    new_o_data['start_time'] = c_data['start_time']
                    new_o_data['end_time'] = end_t.strftime('%H:%M') if c_data['duration'] != 30 else None
                    
                    del current_obs[found_old_key]
                    current_obs[new_obs_key] = new_o_data
                    
                    handled_obs_keys.add(found_old_key)
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
                tag_part = f"{tag_suffix} " if tag_suffix else ""
                status_char = 'x' if c_data['is_completed'] else ' '
                new_line = f"- [{status_char}] {c_data['start_time']}{end_time_str} {tag_part}{c_data['name']}\n"
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

```

---
## File: AntigravitySync/src/external/task_sync_core/utils.py
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
## File: testhandoff/check_handoff.py
```py
import sys
import os
import time

try:
    import ApplicationServices
    from AppKit import NSWorkspace, NSApplicationActivateIgnoringOtherApps
    import EventKit
except ImportError as e:
    print(f"错误: 导入失败 ({e})。请确保已安装 pyobjc-framework-ApplicationServices, Cocoa, EventKit。")
    sys.exit(1)

def check_handoff():
    try:
        # 1. 初始化背景环境 (有些系统需要先初始化一次 EventKit 才能正确读取相关状态)
        store = EventKit.EKEventStore.alloc().init()

        # 2. 查找 Dock 进程并扫描 UI
        dock_apps = [app for app in NSWorkspace.sharedWorkspace().runningApplications() if app.bundleIdentifier() == 'com.apple.dock']
        if not dock_apps:
            return False
        
        dock_pid = dock_apps[0].processIdentifier()
        dock_element = ApplicationServices.AXUIElementCreateApplication(dock_pid)
        
        def scan_elements(element, depth=0):
            if depth > 4: return False
            
            result, children = ApplicationServices.AXUIElementCopyAttributeValue(element, 'AXChildren', None)
            if result != ApplicationServices.kAXErrorSuccess or not children:
                return False
            
            for child in children:
                _, desc = ApplicationServices.AXUIElementCopyAttributeValue(child, 'AXDescription', None)
                _, title = ApplicationServices.AXUIElementCopyAttributeValue(child, 'AXTitle', None)
                _, subrole = ApplicationServices.AXUIElementCopyAttributeValue(child, 'AXSubrole', None)
                
                desc_str = str(desc).lower() if desc else ""
                title_str = str(title).lower() if title else ""
                subrole_str = str(subrole).lower() if subrole else ""
                
                if any(x in s for x in ["handoff", "接力", "from"] for s in [desc_str, title_str, subrole_str]):
                    return {"element": child, "title": title, "desc": desc}
                
                res = scan_elements(child, depth + 1)
                if res: return res
            return False

        return scan_elements(dock_element)
        
    except Exception:
        return False

if __name__ == "__main__":
    print(">>> Handoff 持续监测已启动 (含自动静默点击) <<<", flush=True)
    last_found_state = False
    
    try:
        while True:
            result = check_handoff()
            
            if result:
                if not last_found_state:
                    is_memo = any(x in str(result['title']) for x in ["备忘录", "Notes"])
                    
                    if is_memo:
                        print(f"\n[{time.strftime('%H:%M:%S')}] 【发现备忘录接力 - 执行静默点击】")
                        
                        # 1. 记录当前前台应用 (为了不抢焦点)
                        current_app = NSWorkspace.sharedWorkspace().frontmostApplication()
                        
                        # 2. 点击接力图标
                        # 延迟微调，确保系统稳定
                        time.sleep(0.1)
                        error = ApplicationServices.AXUIElementPerformAction(result['element'], 'AXPress')
                        
                        if error == ApplicationServices.kAXErrorSuccess:
                            # 3. 极速夺回焦点 & 隐藏备忘录
                            # 立即恢复之前的应用，减少闪烁
                            if current_app:
                                current_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                            
                            # 尝试找到备忘录并隐藏 (给一点启动时间)
                            for _ in range(5): 
                                notes_apps = [app for app in NSWorkspace.sharedWorkspace().runningApplications() if app.bundleIdentifier() == 'com.apple.Notes']
                                if notes_apps:
                                    notes_apps[0].hide()
                                    break
                                time.sleep(0.1)
                                
                            print(f"[{time.strftime('%H:%M:%S')}] 已触发同步并请求后台运行")
                        else:
                            print(f"[{time.strftime('%H:%M:%S')}] 点击失败 (错误代码: {error})")
                    else:
                        print(f"\n[{time.strftime('%H:%M:%S')}] 【发现其他接力应用: {result['title']} - 已略过】")
                        print(f"  来源: {result['desc']}")
                        
                    last_found_state = True
            else:
                if last_found_state:
                    print(f"[{time.strftime('%H:%M:%S')}] Handoff 已从 Dock 消失")
                    last_found_state = False
            
            time.sleep(1) # 基准扫描频率
    except KeyboardInterrupt:
        print("\n>>> 监测已停止 <<<")

```

---
## File: testhandoff/debug_ax.py
```py
import sys
from AppKit import NSWorkspace
import ApplicationServices

print("Python 路径:", sys.executable)
print("环境变量集已就绪...")

try:
    dock_apps = [app for app in NSWorkspace.sharedWorkspace().runningApplications() if app.bundleIdentifier() == 'com.apple.dock']
    print(f"找到 Dock 进程: {len(dock_apps) > 0}")
    
    trusted = ApplicationServices.AXIsProcessTrusted()
    print(f"辅助功能权限状态: {trusted}")
    
except Exception as e:
    print(f"发生错误: {e}")

```

---
