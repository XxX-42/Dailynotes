"""
LyubishchevSync Test Suite - test_registry.py
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

LYUBISHCHEV_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(LYUBISHCHEV_DIR, 'src')
for path in [LYUBISHCHEV_DIR, SRC_DIR]:
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
