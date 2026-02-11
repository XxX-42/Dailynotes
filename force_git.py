
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
