import os
import unicodedata
from config import Config
from ..utils import FileUtils
from .parsing import parse_yaml_tags

def scan_projects():
    project_map = {}
    project_path_map = {}
    file_path_map = {}

    # 遍历整个目录树，不做早期截断，支持嵌套项目
    for root, dirs, files in os.walk(Config.ROOT_DIR):
        # 1. 过滤排除目录 (保持原有的 exclude 逻辑)
        dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
        if FileUtils.is_excluded(root): continue

        main_files = []
        for f in files:
            if f.endswith('.md'):
                path = os.path.join(root, f)
                f_name = unicodedata.normalize('NFC', os.path.splitext(f)[0])
                file_path_map[f_name] = path

                # 识别含有 'main' 标签的文件
                # 注意：这里我们读取文件内容来查找 tags: [main]
                if 'main' in parse_yaml_tags(FileUtils.read_file(path) or []):
                    main_files.append(f)

        # 2. 如果当前目录恰好包含唯一的 main 文件，则认定为一个项目节点
        # 即使父目录也是项目，这里也会被记录，从而支持嵌套结构
        if len(main_files) == 1:
            p_name = unicodedata.normalize('NFC', os.path.splitext(main_files[0])[0])
            project_map[root] = p_name
            project_path_map[p_name] = os.path.join(root, main_files[0])
            
    return project_map, project_path_map, file_path_map
