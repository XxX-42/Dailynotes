import sys
import os

def check_identity():
    print(f"--- Environment Identity ---")
    binary = sys.executable
    print(f"Current Binary: {binary}")
    
    # Resolve symlinks to the actual executable
    real_path = os.path.realpath(binary)
    print(f"REAL PATH FOR FDA: {real_path}")
    
    if "CommandLineTools" in real_path:
        print("❌ STATUS: System Python (Permissions will fail).")
    elif "homebrew" in real_path:
        print("✅ STATUS: Homebrew Python (Good for FDA).")
    
    print(f"\n--- Directory Accessibility ---")
    cal_path = os.path.expanduser("~/Library/Calendars")
    try:
        contents = os.listdir(cal_path)
        print(f"ListDir items: {len(contents)}")
        probe = os.path.join(cal_path, "Calendar Cache")
        if os.path.exists(probe):
            print(f"✅ PROBE SUCCESS: 'Calendar Cache' exists. Path is accessible.")
        else:
            print(f"⚠️ PROBE FAILURE: Folder is masked or inaccessible.")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    check_identity()
