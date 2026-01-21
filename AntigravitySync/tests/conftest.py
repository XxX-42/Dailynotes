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
