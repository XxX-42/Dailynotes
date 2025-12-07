import os
import shutil
import time
from config import Config # Import to see current state if needed

# 1. Paths
WRONG_DIR = r'/Users/user999/Documents/【Liang_project】/远程仓库2/【DAILYNOTE】'
CORRECT_DIR = r'/Users/user999/Documents/【Liang_project】/远程仓库2/【ATTACHMENT】/【DAILYNOTE】'

# 2. Delete Wrong Directory
if os.path.exists(WRONG_DIR):
    print(f"Deleting incorrect directory: {WRONG_DIR}")
    shutil.rmtree(WRONG_DIR)
else:
    print("Incorrect directory does not exist (Clean).")

# 3. Update config.py
config_path = 'config.py'
with open(config_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'DAILY_NOTE_DIR =' in line:
        # Update to the correct path including 【ATTACHMENT】
        new_lines.append(f"    DAILY_NOTE_DIR = r'{CORRECT_DIR}/'\n")
    else:
        new_lines.append(line)

with open(config_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("config.py updated with correct DAILY_NOTE_DIR.")

# 4. Ensure Correct Directory Exists
if not os.path.exists(CORRECT_DIR):
    os.makedirs(CORRECT_DIR)
    print(f"Created correct directory: {CORRECT_DIR}")
