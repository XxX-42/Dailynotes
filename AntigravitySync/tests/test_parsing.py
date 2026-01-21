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
