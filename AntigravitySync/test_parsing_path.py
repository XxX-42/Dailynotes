import sys
import os

# add src to path so we can import
sys.path.append(os.path.join(os.getcwd(), 'src'))
from dailynotes.sync.parsing import extract_routing_info

# Simulate a file_path_map where the file '测试' is registered
file_path_map = {
    '测试': '/Users/user999/Documents/【Liang_project】/远程仓库1/项目/测试.md'
}

line1 = '- [x] 10:22 - 14:37<span id="xxx"></span> #B [[测试/测试|测试]]'
target_path, raw_link = extract_routing_info(line1, file_path_map)

print(f"Target Path for [[测试/测试|测试]]: {target_path}")
print(f"Raw Link: {raw_link}")

