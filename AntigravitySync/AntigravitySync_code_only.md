# Project Architecture: AntigravitySync

## Directory Tree (Filtered)
```text
AntigravitySync/
├── AntigravitySync_code_only.md
├── aggregate.py
├── config.py
├── main.py
├── src
│   ├── dailynotes
│   │   ├── __init__.py
│   │   ├── format_core.py
│   │   ├── manager.py
│   │   ├── state_manager.py
│   │   ├── sync
│   │   │   ├── __init__.py
│   │   │   ├── discovery.py
│   │   │   ├── engine.py
│   │   │   ├── parsing.py
│   │   │   ├── rendering.py
│   │   │   └── task_registry.py
│   │   └── utils.py
│   └── external
│       ├── __init__.py
│       ├── apple_sync_adapter.py
│       ├── calendar_db_watchdog.py
│       ├── calendar_monitor.py
│       ├── eventkit_wrapper.py
│       ├── log_sentinel.py
│       └── task_sync_core
│           ├── __init__.py
│           ├── apple_state_manager.py
│           ├── calendar_service.py
│           ├── obsidian_service.py
│           ├── sync_engine.py
│           └── utils.py
├── test.python
└── tests
    ├── __init__.py
    ├── conftest.py
    ├── test_parsing.py
    └── test_registry.py
```

---

## File: config.py
```py
import os


class Config:
    VERSION = "v1.8.2 (Clean Architecture)"    # [2026-01-21] Removed ingestion.py redundancy
    
    # ==========================
    # 1. 基础路径配置 (来自 Dailynotes)
    # ==========================
    VAULT_ROOT = r'/Users/user999/Documents/【Liang_project】/远程仓库1'
    REL_ATTACHMENT_DIR = r'【ATTACHMENT】'
    REL_TEMPLATE_FILE = r'【002_Infobox】/Templates/DayPlanTemplate.md'

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
    TICK_INTERVAL = 3
    TYPING_COOLDOWN_SECONDS = 6
    IMAGE_PARAM_SUFFIX = "|L|200"
    DEBUG_MODE = True
    
    # [NEW] Tick-based scheduling parameters
    DAY_START = -1   # -1 = 昨天
    DAY_END = 90     # [v1.5.1] 释放野兽：指数算法完全可以支撑这个范围
    COMPLETE_TASKS_SYNC_INTERVAL = 60  # [v1.3] 全量扫描从每 30 秒降为每 3 分钟
    
    # [v1.4] 事件驱动模式参数
    EVENT_DEBOUNCE_SECONDS = 0.5   # 事件触发防抖时间（秒）
    
    # [v1.5] 指数动态调度参数
    # 公式: I(d) = EXP_BASE * exp(EXP_COEFF * d) + EXP_OFFSET
    # d=0 时约 300 秒 (5分钟), d=30 时约 348 秒 (5.8分钟)
    DYNAMIC_SYNC_MAX_INTERVAL = 3600  # 强制上限 1 小时
    EXP_BASE = 240      # 基础系数
    EXP_COEFF = 0.0068  # 指数系数
    EXP_OFFSET = 60     # 偏移量
    
    # [v1.7] 日历数据库监听参数 (macOS)
    CALENDAR_WATCH_PATH = os.path.expanduser("~/Library/Calendars")
    CALENDAR_DEBOUNCE_SECONDS = 2.0  # 日历写入非常频繁，需要较大防抖


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

    Logger.info(f"=== Antigravity Sync {Config.VERSION} (Exponential Dynamic Scheduling) ===")
    Logger.info(f"路径: {Config.ROOT_DIR}")
    Logger.info(f"模式: Watchdog (Vault & Calendar) + 指数动态调度")
    Logger.info(f"调度公式: I(d) = {Config.EXP_BASE} * exp({Config.EXP_COEFF} * d) + {Config.EXP_OFFSET}")
    
    # [P2 FIX] Validate template file at startup
    if os.path.exists(Config.TEMPLATE_FILE):
        Logger.info(f"模板: ✅ {Config.REL_TEMPLATE_FILE}")
    else:
        Logger.info(f"⚠️ 模板文件不存在: {Config.REL_TEMPLATE_FILE} (将使用基础骨架)")
    
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
## File: test.python
```python
import os
import subprocess
import sys
from pathlib import Path

def check_and_guide_fda():
    # 1. 定义检测目标：日历数据库（受 FDA 保护）
    # 兼容旧版和现代 macOS (Group Containers)
    potential_paths = [
        Path.home() / "Library/Calendars/Calendar.sqlitedb",
        Path.home() / "Library/Group Containers/group.com.apple.calendar/Calendar.sqlitedb"
    ]
    
    print("--- 正在检测 '完全磁盘访问权限 (FDA)' ---")
    
    found_any = False
    for calendar_db in potential_paths:
        if not calendar_db.exists():
            continue
        
        found_any = True
        # 2. 尝试执行低级读取测试
        try:
            # 尝试打开文件句柄进行读取
            with open(calendar_db, 'rb') as f:
                f.read(10)
            print(f" [状态] 正常：已通过 {calendar_db.name} 验证完全磁盘访问权限。")
            return True
        except PermissionError:
            print(f" [警告] 权限缺失：访问 {calendar_db.name} 被拦截。")
        except Exception as e:
            print(f" [错误] 检测 {calendar_db.name} 时发生未知异常: {e}")

    if not found_any:
        print(" [提示] 无法找到日历数据库路径，可能日历从未启动或路径变动。")
        # 尝试检查 Messages 数据库作为兜底
        messages_db = Path.home() / "Library/Messages/chat.db"
        if messages_db.exists():
            try:
                with open(messages_db, 'rb') as f:
                    f.read(10)
                print(" [状态] 正常：已通过 Messages 数据库验证完全磁盘访问权限。")
                return True
            except PermissionError:
                print(" [警告] 权限缺失：Messages 数据库访问被拦截。")
    

    # 3. 如果检测失败，启动引导逻辑
    print("\n--- 引导修复步骤 ---")
    print("1. 系统设置窗口即将打开。")
    print("2. 请在列表中找到并勾选你的终端 (Terminal / iTerm2) 或 IDE (VS Code)。")
    print(f"3. 如果列表中没有，请点击 '+' 号添加：{sys.executable}")
    print("4. 修改后需要重启终端才能生效。")

    # 4. 自动化指令：直接跳转到隐私与安全性 -> 完全磁盘访问权限
    # 该 URL Schema 适用于 macOS Ventura (13.0) 及更高版本
    url = "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_AllFiles"
    subprocess.run(["open", url])
    
    return False

if __name__ == "__main__":
    if not check_and_guide_fda():
        sys.exit(1)
    else:
        print("权限验证通过，可以继续执行同步逻辑。")
```

---
## File: tests/__init__.py
```py
"""
AntigravitySync Test Suite
"""

```

---
## File: tests/conftest.py
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
## File: tests/test_parsing.py
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
## File: tests/test_registry.py
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
## File: src/dailynotes/__init__.py
```py
import sys
import os

# Ensure config can be imported from root if not already
# This is a fallback in case sys.path is messed up, but main.py should handle it.

```

---
## File: src/dailynotes/format_core.py
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
## File: src/dailynotes/manager.py
```py
"""
Fusion Manager - Antigravity Architecture v1.5
Event-Driven Sync Engine with Exponential Dynamic Scheduling.

Key Features:
- [v1.4] Event-Driven: Uses watchdog to monitor file changes
- [v1.4] Self-Write Detection: Ignores events triggered by script's own writes
- [v1.5] Exponential Scheduling: I(d) = 240 * exp(0.0068 * d) + 60
- Content-Hash Self-Awareness: Uses content identity instead of mtime
"""
import os
import sys
import re
import math
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

# watchdog 导入（带降级处理）
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    # 提供空基类以避免继承错误
    class FileSystemEventHandler:
        pass
    Logger.error_once("watchdog_import", "⚠️ watchdog 库未安装，将使用轮询模式")


class ObsidianEventHandler(FileSystemEventHandler):
    """
    [v1.6] 文件变更事件处理器 - 支持原子写入
    监听 Obsidian Vault 中的 .md 文件变动，触发同步逻辑。
    
    关键修复：Obsidian 使用"原子写入"模式保存文件：
    1. 写入临时文件 (e.g., .md.tmp)
    2. 重命名临时文件覆盖目标文件 (rename/move)
    
    因此必须同时监听 on_modified 和 on_moved 事件。
    """
    
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self._last_event_time = {}  # 防抖追踪: {filepath: timestamp}
    
    def _process_event(self, filepath, event_type):
        """
        统一的事件处理逻辑（供 on_modified 和 on_moved 调用）
        
        Args:
            filepath: 目标文件路径
            event_type: 事件类型字符串 ("MODIFIED" 或 "MOVED")
        """
        # [过滤] 仅处理 .md 文件
        if not filepath.endswith('.md'):
            return
        
        # [过滤] 排除目录检查
        if FileUtils.is_excluded(filepath):
            return

        # [底层日志] 立即输出，这是调试的关键
        Logger.info(f"🔎 [Watchdog] 捕获底层事件 ({event_type}): {os.path.basename(filepath)}")
        
        # [防抖] 避免短时间内重复触发
        now = time.time()
        last_time = self._last_event_time.get(filepath, 0)
        if now - last_time < Config.EVENT_DEBOUNCE_SECONDS:
            Logger.debug(f"[Event] 防抖跳过: {os.path.basename(filepath)}")
            return
        self._last_event_time[filepath] = now
        
        # [哈希自省] 检测是否为脚本自身的写入
        try:
            content = FileUtils.read_content(filepath)
            if content is None:
                return
            
            content_hash = FileUtils.calculate_hash(content)
            
            # 如果这是脚本自己的写入，立即丢弃事件
            if FileUtils.is_system_write(content_hash):
                Logger.debug(f"[Event] 忽略自写入事件: {os.path.basename(filepath)}")
                return
            
            # [触发] 用户编辑事件，触发同步
            Logger.info(f"📝 [Event] 检测到用户变更: {os.path.basename(filepath)}")
            self.manager.on_file_changed(filepath)
            
        except Exception as e:
            Logger.error_once(f"event_err_{filepath}", f"事件处理异常: {e}")
    
    def on_modified(self, event):
        """处理文件修改事件（传统编辑器直接写入）"""
        if event.is_directory:
            return
        self._process_event(event.src_path, "MODIFIED")
    
    def on_moved(self, event):
        """
        处理文件移动/重命名事件（原子写入的核心）
        
        Obsidian 保存流程：
        1. 写入 .md.tmp 临时文件
        2. rename(".md.tmp", ".md") 覆盖目标
        
        关键：必须使用 dest_path (重命名后的目标路径)
        """
        if event.is_directory:
            return
        # 注意：使用 dest_path，这是重命名后的新文件名
        self._process_event(event.dest_path, "MOVED")





class FusionManager:
    """
    Unified sync manager implementing Antigravity Architecture.
    
    Core Logic:
    - 主权在内 (Sovereignty Inside): Dailynotes runs first
    - 脏标志阻断 (Dirty Flag): If internal modified, skip external
    - [v1.4] 事件驱动 (Event-Driven): watchdog 监听文件变更
    - [v1.5] 指数动态调度 (Exponential Scheduling): 非线性日期冷却
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
        
        # [NEW] Track the date when tomorrow's note was last created (to avoid duplicates)
        self._tomorrow_note_created_date = None
        
        # [v1.4] Observer 实例
        self._observer = None
        self._ek_client = None
        if EK_AVAILABLE:
            try:
                self._ek_client = EventKitClient()
            except Exception as e:
                Logger.error_once("ek_init_fail", f"EventKitClient init failed: {e}")
                self._ek_client = None
        self._running = False
        
        # [v1.5] 动态调度状态：记录每个日期的上次同步时间戳
        self._last_full_sync_registry = {}  # {date_str: timestamp}
        
        # [v1.8] Lazy initialization flag for TaskRegistry
        self._registry_warmup_done = False

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
        """
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{today_str}.md")

        if os.path.exists(daily_path):
            content = FileUtils.read_content(daily_path)
            if content:
                content_hash = FileUtils.calculate_hash(content)
                if FileUtils.check_system_write(content_hash):
                    return False

            mtime = FileUtils.get_mtime(daily_path)
            if time.time() - mtime < 60:
                return True

        return False

    def check_today_changed(self) -> bool:
        """
        Check if today's diary content has changed since last check.
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
            self.today_last_hash = current_hash
            return False
        
        if current_hash != self.today_last_hash:
            self.today_last_hash = current_hash
            return True
        
        return False

    def _maybe_create_tomorrow_note(self):
        """
        [NEW] Auto-create tomorrow's diary at 23:30.
        """
        now = datetime.datetime.now()
        today_str = now.strftime('%Y-%m-%d')
        
        if self._tomorrow_note_created_date == today_str:
            return
        
        if now.hour != 23 or now.minute < 30:
            return
        
        tomorrow = now.date() + datetime.timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        tomorrow_path = os.path.join(Config.DAILY_NOTE_DIR, f"{tomorrow_str}.md")
        
        if os.path.exists(tomorrow_path):
            Logger.info(f"📅 [预创建] 明天的日记已存在，跳过: {tomorrow_str}.md")
            self._tomorrow_note_created_date = today_str
            return
        
        if os.path.exists(Config.TEMPLATE_FILE):
            try:
                tmpl_lines = FileUtils.read_file(Config.TEMPLATE_FILE)
                if tmpl_lines:
                    Logger.info(f"📅 [预创建] 23:30 定时任务 - 从模板创建明天的日记: {tomorrow_str}.md")
                    FileUtils.write_file(tomorrow_path, tmpl_lines)
                    self._tomorrow_note_created_date = today_str
            except Exception as e:
                Logger.error_once(f"pre_create_fail_{tomorrow_str}", f"预创建明天日记失败: {e}")
        else:
            Logger.info(f"📅 [预创建] 未找到模版，创建基础骨架: {tomorrow_str}.md")
            base_scaffold = ["# Day planner\n", "\n", "# Journey\n", "\n"]
            FileUtils.write_file(tomorrow_path, base_scaffold)
            self._tomorrow_note_created_date = today_str

    def get_date_range(self) -> list:
        """
        Generate date strings from DAY_START to DAY_END relative to today.
        """
        today = datetime.date.today()
        dates = []
        for delta in range(Config.DAY_START, Config.DAY_END + 1):
            target_date = today + datetime.timedelta(days=delta)
            date_str = target_date.strftime('%Y-%m-%d')
            if date_str >= Config.SYNC_START_DATE:
                dates.append(date_str)
        return dates

    def process_single_date(self, date_str, is_event_trigger=False):
        """
        Process a single date: internal sync + formatting + Apple sync.
        Returns detailed result dict.
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
                # [v1.5.2] 允许事件驱动绕过防抖冷却
                idle_duration = time.time() - FileUtils.get_mtime(daily_path)
                if not is_event_trigger and idle_duration < Config.TYPING_COOLDOWN_SECONDS:
                    results["skipped"] = True
                    return results

        # --- [PRIORITY 1] Obsidian Internal Processing ---
        if is_event_trigger or self.check_debounce(daily_path) or not os.path.exists(daily_path):
            try:
                # [v1.8] Use registry's O(1) lookup instead of full scan
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
        elif os.path.exists(daily_path) and (is_event_trigger or self.check_debounce(daily_path)):
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
        [v1.8 REFACTORED] 事件驱动入口：文件变更时调用
        
        改进内容:
        - 日记文件: 直接触发该日期的同步
        - 项目文件: 使用 process_file_event 增量更新，只同步受影响的日期
        """
        filename = os.path.basename(filepath)
        
        # [v1.8] Lazy warmup: ensure registry is initialized on first event
        if not self._registry_warmup_done:
            Logger.info("🔄 [Manager] Warming up TaskRegistry...")
            self.sync_core.initialize_registry()
            self._registry_warmup_done = True
        
        # 尝试从文件名提取日期 (格式: YYYY-MM-DD.md)
        date_match = re.match(r'^(\d{4}-\d{2}-\d{2})\.md$', filename)
        
        if date_match:
            # 这是一个日记文件 - 直接触发该日期同步
            date_str = date_match.group(1)
            Logger.info(f"   🔄 [Sync] 触发日期同步: {date_str}")
            self.process_single_date(date_str, is_event_trigger=True)
        else:
            # [v1.8] 项目文件 - 使用增量同步
            # 只扫描这ONE个文件，然后只同步受影响的日期
            affected_dates = self.sync_core.process_file_event(filepath)
            
            if affected_dates:
                Logger.info(f"   🔄 [Sync] 项目文件变更，影响 {len(affected_dates)} 个日期")
                for date_str in affected_dates:
                    self.process_single_date(date_str, is_event_trigger=True)
            else:
                # Fallback: 如果文件中没有任务，仍然同步今天
                today_str = datetime.date.today().strftime('%Y-%m-%d')
                Logger.info(f"   🔄 [Sync] 项目文件变更（无任务），触发今日同步")
                self.process_single_date(today_str, is_event_trigger=True)

    def trigger_immediate_sync_for_today(self):
        """
        [v1.7] 由日历事件触发的立即同步
        """
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        Logger.info(f"   🔄 [Sync] Calendar 变动触发今日同步: {today_str}")
        self.process_single_date(today_str, is_event_trigger=True)

    def _on_calendar_push_event(self):
        """
        [v1.9] Callback for Distributed Notification (Zero Latency).
        Runs in a background thread.
        """
        Logger.info(f"⚡ [Distributed] 检测到系统日历数据库物理变更！")
        self.trigger_immediate_sync_for_today()

    def _calculate_dynamic_interval(self, date_str) -> float:
        """
        [v1.5] 计算指定日期的动态同步间隔
        公式: I(d) = EXP_BASE * exp(EXP_COEFF * d) + EXP_OFFSET
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD)
        Returns:
            同步间隔（秒）
        """
        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            today = datetime.date.today()
            d = abs((target_date - today).days)  # 距离今天的天数
            
            # [v1.8.3] Privacy-aware Fast Polling for Today
            # 由于 macOS TCC 权限限制，Watchdog 可能无法监听到日历数据库变化
            # 对“今天”强制使用 30 秒的快速轮询，确保近似实时的体验
            if d == 0:
                return 30.0
            
            # 指数拟合公式
            interval = Config.EXP_BASE * math.exp(Config.EXP_COEFF * d) + Config.EXP_OFFSET
            
            # 限制在最大值以内
            return min(interval, Config.DYNAMIC_SYNC_MAX_INTERVAL)
        except Exception:
            return Config.EXP_BASE + Config.EXP_OFFSET  # 默认 300 秒

    def _do_smart_cleanup(self):
        """
        [v1.5] 智能巡检：根据日期距离动态调度同步
        近距离日期高频扫描，远距离日期低频扫描
        """
        # 修复全局格式问题（每次巡检都执行，轻量级操作）
        FormatCore.fix_broken_tab_bullets_global()
        
        # 检查是否需要预创建明天的日记
        self._maybe_create_tomorrow_note()
        
        # 遍历日期范围，根据冷却时间决定是否同步
        now = time.time()
        date_range = self.get_date_range()
        
        # [v1.5.1] 清理过期记录，防止内存缓慢泄漏
        active_dates = set(date_range)
        for recorded_date in list(self._last_full_sync_registry.keys()):
            if recorded_date not in active_dates:
                del self._last_full_sync_registry[recorded_date]
        
        for date_str in date_range:
            last_sync = self._last_full_sync_registry.get(date_str, 0)
            interval = self._calculate_dynamic_interval(date_str)
            
            if now - last_sync >= interval:
                # 冷却时间已到，执行同步
                self.process_single_date(date_str)
                self._last_full_sync_registry[date_str] = now

    def _print_countdown(self):
        """
        [v1.5.2] 实时输出下一次大检测的倒计时
        在同一行更新秒数，使用回车符覆盖
        """
        now = time.time()
        date_range = self.get_date_range()
        
        min_countdown = float('inf')
        next_date = None
        
        for date_str in date_range:
            last_sync = self._last_full_sync_registry.get(date_str, 0)
            interval = self._calculate_dynamic_interval(date_str)
            remaining = interval - (now - last_sync)
            
            if remaining > 0 and remaining < min_countdown:
                min_countdown = remaining
                next_date = date_str
        
        if next_date and min_countdown < float('inf'):
            countdown_str = f"⏱️  下次检测 [{next_date}]: {int(min_countdown):>4}s"
            # 使用 \r 回到行首，覆盖原内容
            sys.stdout.write(f"\r{countdown_str}  ")
            sys.stdout.flush()
            # 标记倒计时行正在显示，让 Logger 知道需要先清行
            Logger._countdown_active = True

    def run(self):
        """
        [v1.5] 事件驱动主循环
        混合动力模式：watchdog 事件 + 指数动态调度
        """
        def _term_handler(signum, frame):
            self._running = False
            raise SystemExit("Received SIGTERM")

        signal.signal(signal.SIGTERM, _term_handler)
        self._running = True

        Logger.info(f"🚀 事件驱动引擎启动: Watchdog (Vault & Calendar) + 指数动态调度")
        Logger.info(f"   调度公式: I(d) = {Config.EXP_BASE} * exp({Config.EXP_COEFF} * d) + {Config.EXP_OFFSET}")
        Logger.info(f"   冷却上限: {Config.DYNAMIC_SYNC_MAX_INTERVAL}s | 事件防抖: {Config.EVENT_DEBOUNCE_SECONDS}s")
        Logger.info(f"   日期范围: DAY_START={Config.DAY_START} ~ DAY_END={Config.DAY_END}")

        # 初始化 watchdog Observer
        if WATCHDOG_AVAILABLE:
            try:
                self._observer = Observer()
                event_handler = ObsidianEventHandler(self)
                
                # 监听 Vault 根目录
                self._observer.schedule(event_handler, Config.VAULT_ROOT, recursive=True)
                self._observer.start()
                Logger.info(f"👁️ [Watchdog] 开始监听: {Config.VAULT_ROOT}")
            except Exception as e:
                Logger.error_once("observer_init", f"Watchdog 初始化失败: {e}")
                self._observer = None
            
            # [v1.7] Start Calendar Observer
            # [v2.0] EventKit 监听
            if self._ek_client:
                try:
                    Logger.info("📅 [Watchdog] 启动 EventKit 监听...")
                    self._ek_client.start_watching(self._on_calendar_push_event)
                except Exception as e:
                    Logger.error_once("cal_ek_fail", f"无法启动日历监听: {e}")
            else:
                Logger.info("⚠️ [Watchdog] EventKit 客户端不可用，将使用纯轮询。")

        else:
            Logger.info("⚠️ [Watchdog] 不可用，使用纯轮询模式")

        # 启动时执行一次智能巡检
        self._do_smart_cleanup()

        # 主循环
        try:
            while self._running:
                # 计算并显示下一次同步倒计时
                self._print_countdown()
                
                # 让出 CPU 资源
                time.sleep(1)
                
                # 每秒执行智能巡检（轻量级时间戳比对）
                self._do_smart_cleanup()
                
        except KeyboardInterrupt:
            Logger.info("\n⏹️ 收到中断信号...")
        finally:
            # 优雅停止 Observer
            if self._observer:
                Logger.info("🛑 [Watchdog] 停止监听 Vault...")
                self._observer.stop()
                self._observer.join(timeout=3)
            
            # [v2.0] 停止日历监听
            if self._ek_client:
                 Logger.info("🛑 [Watchdog] 停止监听 Calendar...")
                 self._ek_client.stop_watching()
            

            
            self.sm.save()
            Logger.info("✅ 状态已保存，引擎已停止")


```

---
## File: src/dailynotes/state_manager.py
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
## File: src/dailynotes/utils.py
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
## File: src/dailynotes/sync/__init__.py
```py
from .engine import SyncCore
from .task_registry import TaskRegistry, get_registry

```

---
## File: src/dailynotes/sync/discovery.py
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
## File: src/dailynotes/sync/engine.py
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
## File: src/dailynotes/sync/parsing.py
```py
import re
import unicodedata

# [P3 FIX] Pre-compiled regex patterns for performance
_RE_QUOTE_PREFIX = re.compile(r'^>\s?')
_RE_STATUS_INDENT = re.compile(r'^[\s>]*-\s*\[.\]')
_RE_TIME_RANGE = re.compile(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}')
_RE_TIME_SINGLE = re.compile(r'\d{1,2}:\d{2}')
_RE_BLOCK_ID = re.compile(r'\^[a-zA-Z0-9]{6,}\s*$')
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
        id_m = re.search(r'\^([a-zA-Z0-9]{6,7})\s*$', line)
        bid = id_m.group(1) if id_m else None
        
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
## File: src/dailynotes/sync/rendering.py
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
## File: src/dailynotes/sync/task_registry.py
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
## File: src/external/__init__.py
```py
# External sync modules

```

---
## File: src/external/apple_sync_adapter.py
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
## File: src/external/calendar_db_watchdog.py
```py
import os
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class CalendarDbHandler(FileSystemEventHandler):
    """
    监听日历 SQLite 数据库文件的物理变更
    """
    def __init__(self, callback):
        self.callback = callback
        self._timer = None
        self._debounce_interval = 2.0  # 2秒防抖

    def _trigger_callback(self):
        """实际执行回调"""
        if self.callback:
            self.callback()

    def on_modified(self, event):
        if event.is_directory:
            return
            
        filename = os.path.basename(event.src_path)
        
        # 忽略临时文件
        if ".tmp" in filename:
            return

        # 只关注核心数据库文件 (包括 WAL 日志模式)
        if filename in ["Calendar.sqlitedb", "Calendar.sqlitedb-wal"]:
            # Debounce 机制: 每次触发都重置计时器
            if self._timer:
                self._timer.cancel()
            
            self._timer = threading.Timer(self._debounce_interval, self._trigger_callback)
            self._timer.start()

def start_calendar_db_watchdog(callback):
    path = os.path.expanduser("~/Library/Calendars")
    
    # 容错：如果目录不存在，无法监听
    if not os.path.exists(path):
        print(f"⚠️ [Watchdog] 路径不存在，跳过监听: {path}")
        return None

    handler = CalendarDbHandler(callback)
    observer = Observer()
    # 递归监听，以防数据库文件位于子目录中
    observer.schedule(handler, path, recursive=True)
    observer.start()
    
    print("👁️ [Watchdog] 已挂载日历数据库物理监听 (SQLite)")
    return observer

```

---
## File: src/external/calendar_monitor.py
```py
import threading
import objc
from Foundation import NSObject, NSDistributedNotificationCenter
from PyObjCTools import AppHelper

class DistributedObserver(NSObject):
    """
    [Zero-Latency] System-wide Calendar Database Observer.
    Listens for 'com.apple.calendar.database.changed' distributed notification.
    """
    
    def initWithCallback_(self, callback):
        self = objc.super(DistributedObserver, self).init()
        if self is None:
            return None
        self.callback = callback
        return self
    
    def startListening(self):
        # Register for the hidden system broadcast
        NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self,
            "onCalendarChanged:",
            "com.apple.calendar.database.changed",
            None
        )
        print("📡 [Distributed] 成功挂载系统级日历变更广播 (零延迟模式)")
        
    def stopListening(self):
        NSDistributedNotificationCenter.defaultCenter().removeObserver_(self)
        
    def onCalendarChanged_(self, notification):
        """
        Callback triggered by the kernel/distributed center.
        """
        # Triggers immediately on database write
        if self.callback:
            self.callback()

def start_calendar_watchdog(on_change_callback):
    """
    Starts the Distributed Notification Observer in a background thread.
    """
    def _run_loop(callback):
        pool = objc.autorelease_pool()
        with pool:
            observer = DistributedObserver.alloc().initWithCallback_(callback)
            observer.startListening()
            
            try:
                # Install interrupt=False to allow main thread signals
                AppHelper.runConsoleEventLoop(installInterrupt=False)
            except Exception as e:
                print(f"⚠️ [Distributed] RunLoop Error: {e}")
            finally:
                if observer:
                    observer.stopListening()

    t = threading.Thread(target=_run_loop, args=(on_change_callback,), daemon=True, name="DistributedCalMonitor")
    t.start()
    return t

```

---
## File: src/external/eventkit_wrapper.py
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
        开启后台线程监听日历变更。
        """
        if not self.access_granted:
            # 尝试自动获取权限
            if not self.check_access():
                print("🚫 无法启动监听：没有日历访问权限。")
                return

        if self._observer:
            print("⚠️ 监听器已在运行。")
            return

        def run_loop():
            # 在后台线程创建和运行 Observer
            self._observer = CalendarObserver.alloc().initWithCallback_(callback)
            self._observer.startObserving()
            
            # 启动 RunLoop，这将阻塞线程直到 stopEventLoop 被调用
            # 必须使用 runConsoleEventLoop 以便支持 RunLoop 机制
            try:
                AppHelper.runConsoleEventLoop()
            except Exception as e:
                print(f"⚠️ [RunLoop] 异常退出: {e}")
            finally:
                print("🏁 [RunLoop] 线程结束")

        self._thread = threading.Thread(target=run_loop, name="EventKitMonitor", daemon=True)
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
            
        for event in events:
            try:
                title = event.title() or "无标题"
                # 处理完成状态标识（根据现有逻辑保持一致）
                is_completed = any(title.startswith(prefix) for prefix in ["✅", "✓"])
                clean_name = title.lstrip("✅✓").strip()
                
                # 获取唯一 ID
                key = f"{clean_name}_{event.eventIdentifier()}"
                
                result[key] = {
                    'name': clean_name,
                    'id': event.eventIdentifier(),
                    'is_completed': is_completed,
                    'raw_name': title
                }
            except Exception as e:
                print(f"⚠️ 处理事件失败: {e}")
                continue
            
        return result

if __name__ == "__main__":
    # 简单的测试桩
    print("🚀 测试 EventKitClient...")
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
## File: src/external/log_sentinel.py
```py
import subprocess
import threading
import time
import signal
import os

class LogSentinel:
    """
    Broad-Spectrum Calendar Change Detector (Shotgun Mode).
    Monitors all non-debug CalendarAgent logs to reliably detect changes.
    """
    
    def __init__(self, callback):
        self.callback = callback
        self.process = None
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        """Spawns the log monitoring daemon thread."""
        if self.thread and self.thread.is_alive():
            return
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._monitor_logs, daemon=True, name="LogSentinelOps")
        self.thread.start()

    def stop(self):
        """Stops the subprocess and the monitoring thread."""
        self.stop_event.set()
        if self.process:
            try:
                os.kill(self.process.pid, signal.SIGTERM)
            except Exception:
                pass
            self.process = None

    def _monitor_logs(self):
        # [修改点 1] 移除具体的 Message 过滤，只看进程名
        # type != debug 用于过滤掉过于频繁的调试信息，只看默认和错误信息
        cmd = [
            "/usr/bin/log", "stream",
            "--style", "syslog",
            "--predicate", 'process == "CalendarAgent" && type != debug'
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1
            )

            print("🕵️ [LogSentinel] 哨兵已启动 (广谱监听模式)...")

            # [修改点 2] 引入冷却时间，防止日志刷屏导致触发太多
            last_trigger_time = 0
            COOLDOWN = 1.0  # 1秒内只触发一次

            while not self.stop_event.is_set():
                line = self.process.stdout.readline()
                if not line:
                    if self.process.poll() is not None:
                        break
                    continue
                
                # [调试用] 打印出来看看你的系统到底输出了什么日志
                # print(f"捕获日志: {line.strip()}") 

                # 只要有日志输出，就说明 CalendarAgent 在工作
                # 我们可以做一个简单的反向过滤，忽略掉 "Fetching" (读取) 这种操作
                if "Fetching" in line or "Reading" in line:
                    continue

                current_time = time.time()
                if current_time - last_trigger_time > COOLDOWN:
                    print(f"⚡ [LogSentinel] 捕获活动，触发同步！")
                    if self.callback:
                        self.callback()
                    last_trigger_time = current_time
                    
        except Exception as e:
            print(f"⚠️ [LogSentinel] 监听失败: {e}")
        finally:
            self.stop()

def start_log_sentinel(callback):
    """Helper to start the sentinel quickly."""
    sentinel = LogSentinel(callback)
    sentinel.start()
    return sentinel

```

---
## File: src/external/task_sync_core/__init__.py
```py
# TaskSynctoreminder core modules

```

---
## File: src/external/task_sync_core/apple_state_manager.py
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
## File: src/external/task_sync_core/calendar_service.py
```py
"""
Apple Calendar Service - Adapted for unified config.
"""
from datetime import datetime, timedelta
from config import Config
from .utils import escape_as_text, run_applescript
try:
    from external.eventkit_wrapper import EventKitClient
    EK_AVAILABLE = True
except ImportError:
    EK_AVAILABLE = False

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
    Get all calendar events for a specific date using EventKit (if available) or AppleScript fallback.
    
    Args:
        target_dt: datetime object for target date
    
    Returns:
        dict: Calendar events keyed by "name_starttime"
    """
    if EK_AVAILABLE:
        try:
            client = EventKitClient()
            all_events = client.fetch_events(target_dt)
            
            # Filter by managed calendars
            filtered_events = {}
            for key, val in all_events.items():
                if val['current_calendar'] in ALL_MANAGED_CALENDARS:
                    filtered_events[key] = val
            return filtered_events
        except Exception as e:
            print(f"⚠️ EventKit Error: {e}")
            # Fallback or return empty?
            # User objective is "Replace". 
            # I will return empty or throw if strict, but let's stick to returning empty on failure 
            # to avoid crashing main loop, or maybe rely on error logging.
            return {}
            
    # Legacy AppleScript implementation removed as per objective "Replace the current..."
    # If EK not available, we can't do much if we removed the code.
    # But for safety, maybe I should have kept the old code as fallback?
    # User said "Replace the current... mechanism". So I will remove it.
    print("❌ EventKit not available.")
    return {}


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
## File: src/external/task_sync_core/obsidian_service.py
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
## File: src/external/task_sync_core/sync_engine.py
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
                print(f"🗑️ [O->C] 触发日历删除: {key}")
                batch.add_delete(c_data['id'], c_data['current_calendar'])
                handled_cal_keys.add(key)

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
            
            # [v1.7.2] Snapshot Consistency: Add to current_obs so snapshot saves it
            new_key = key # key is already name_time
            # Construct minimal data for snapshot
            current_obs[new_key] = {
                'name': c_data['name'],
                'start_time': c_data['start_time'],
                'end_time': end_t.strftime('%H:%M') if c_data['duration'] != 30 else None,
                'target_calendar': c_data['current_calendar'],
                'tag': tag_suffix,
                'status': status_char,
                'line_index': -1 # Placeholder, won't be used next run (re-parsed)
            }

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
                
                # [v1.7.2] Snapshot Consistency: Update current_obs
                current_obs[key]['target_calendar'] = c_data['current_calendar']
                current_obs[key]['tag'] = tag_suffix
                current_obs[key]['status'] = status_char
                current_obs[key]['end_time'] = end_t.strftime('%H:%M') if c_data['duration'] != 30 else None

    for key in last_cal:
        if key not in current_cal and key not in handled_obs_keys:
            if key in current_obs:
                line_idx = current_obs[key]['line_index']
                print(f"✂️ [C->O] 检测到日历端删除 (同步删除本地): {current_obs[key]['name']}")
                lines_to_delete_indices.append(line_idx)
                file_dirty = True
                
                # [v1.7.2] Snapshot Consistency: Remove from current_obs
                del current_obs[key]

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
## File: src/external/task_sync_core/utils.py
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
