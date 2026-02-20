import sys
import os

sys.path.append(os.path.join(os.getcwd(), 'src'))
from dailynotes.utils import FileUtils
from config import Config

path = "/Users/user999/Documents/【Liang_project】/远程仓库1/测试/测试.md"
print(f"Is {path} excluded? -> {FileUtils.is_excluded(path)}")
print(f"Is /Users/user999/Documents/【Liang_project】/远程仓库1/测试 excluded? -> {FileUtils.is_excluded(os.path.dirname(path))}")

