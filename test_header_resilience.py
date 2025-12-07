import sys
import os
import re
sys.path.append(os.getcwd())
from sync_core import SyncCore
from utils import Logger

# Mock State Manager
class MockSM:
    pass

class MockLogger:
    @staticmethod
    def info(msg, tag=None): print(f"[INFO] {msg}")
    @staticmethod
    def error_once(key, msg): print(f"[ERROR] {msg}")

def run_test():
    print("=== VIOLENT HEADER RESILIENCE TEST ===")
    sync = SyncCore(MockSM())
    
    test_cases = [
        {
            "name": "Standard Header",
            "lines": [
                "- Task 1\n",
                "  - Child 1\n",
                "# Header\n",
                "- Task 2\n"
            ],
            "expected_len": 2
        },
        {
            "name": "Indented Header (Should Break)",
            "lines": [
                "- Task 1\n",
                "  - Child 1\n",
                "  # Indented Header\n", 
                "- Task 2\n"
            ],
            "expected_len": 2 # Should stop at header, even if indented
        },
        {
            "name": "Quoted Header",
            "lines": [
                "> - Task 1\n",
                ">   - Child 1\n",
                "> # Quoted Header\n"
            ],
            "expected_len": 2
        },
        {
            "name": "Deeply Indented Quoted Header",
            "lines": [
                "> - Task 1\n",
                ">   - Child 1\n",
                ">     - Child 2\n",
                ">       # Deep Header\n"
            ],
            "expected_len": 3
        },
        {
            "name": "Header with Trailing Space",
            "lines": [
                "- Task 1\n",
                "# Header   \n"
            ],
            "expected_len": 1
        },
        {
            "name": "Mixed Quote/Indent Header",
            "lines": [
                "> - Task 1\n",
                ">   # Header\n"
            ],
            "expected_len": 1
        }
    ]

    failures = 0
    for i, case in enumerate(test_cases):
        print(f"\n[Case {i+1}] {case['name']}")
        print("Input:")
        for l in case['lines']: print(repr(l))
        
        block, length = sync.capture_block(case['lines'], 0)
        
        print(f"Captured ({length} lines):")
        for l in block: print(repr(l))
        
        # Check if header is in block
        header_in_block = any('#' in re.sub(r'^[>\s]+', '', l) for l in block if l.strip())
        
        if length != case['expected_len']:
            print(f"FAIL: Expected length {case['expected_len']}, got {length}")
            failures += 1
        elif header_in_block:
             # Double check: if the line itself WAS the header line
             # We want to ensure the LAST line is NOT the header
             last_line = block[-1]
             clean_last = re.sub(r'^[>\s]+', '', last_line)
             if clean_last.startswith('#'):
                 print(f"FAIL: Header swallowed into block: {repr(last_line)}")
                 failures += 1
             else:
                 print("PASS")
        else:
            print("PASS")

    if failures == 0:
        print("\n=== ALL TESTS PASSED ===")
        sys.exit(0)
    else:
        print(f"\n=== {failures} TESTS FAILED ===")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
