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
        ["git", "add", "LyubishchevSync/config.py", "LyubishchevSync/src/dailynotes/format_core.py", "LyubishchevSync/src/dailynotes/sync/rendering.py"],
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
