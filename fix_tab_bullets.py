import os
import re
from config import Config

def fix_tab_bullets():
    target_dir = Config.DAILY_NOTE_DIR
    # 正则解释：
    # ^(\t+)  : 行首，一个或多个制表符（组 1）
    # -       : 连字符
    # (?![ \t]) : 空格或制表符的否定前瞻。
    #             （替换用户建议的 (?!\s) 以确保匹配 EOL 处的 \n）
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
            
            # 替换逻辑：r'\1- ' 意味着 "组 1 (制表符) + 连字符 + 空格"
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
