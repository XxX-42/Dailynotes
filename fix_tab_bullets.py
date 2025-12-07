import os
import re
from config import Config

def fix_tab_bullets():
    target_dir = Config.DAILY_NOTE_DIR
    # Regex Explanation:
    # ^(\t+)  : Start of line, one or more Tabs (Group 1)
    # -       : Hyphen
    # (?![ \t]) : Negative lookahead for Space or Tab. 
    #             (Replaces user suggestion (?!\s) to ensure it matches \n at EOL)
    pattern = re.compile(r'^(\t+)-(?![ \t])', re.MULTILINE)
    
    fixed_count = 0
    
    if not os.path.exists(target_dir):
        print(f"Directory not found: {target_dir}")
        return

    for filename in os.listdir(target_dir):
        if not filename.endswith('.md'):
            continue
            
        filepath = os.path.join(target_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Sub logic: r'\1- ' means "Group 1 (Tabs) + Hyphen + Space"
            new_content = pattern.sub(r'\1- ', content)
            
            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"[FIXED] {filename}")
                fixed_count += 1
                
        except Exception as e:
            print(f"[ERROR] Failed to process {filename}: {e}")

    print(f"Total fixed files: {fixed_count}")

if __name__ == "__main__":
    fix_tab_bullets()
