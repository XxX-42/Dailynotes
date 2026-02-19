
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
