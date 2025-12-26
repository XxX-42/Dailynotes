import os
import unicodedata
from config import Config
from ..utils import FileUtils
from .parsing import parse_yaml_tags

def scan_projects():
    project_map = {}
    project_path_map = {}
    file_path_map = {}
    
    # 1. 强制全量递归扫描
    for root, dirs, files in os.walk(Config.ROOT_DIR):
        # 排除常规忽略目录
        dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
        if FileUtils.is_excluded(root): continue

        main_files = []
        for f in files:
            if f.endswith('.md'):
                path = os.path.join(root, f)
                stem = unicodedata.normalize('NFC', os.path.splitext(f)[0])
                file_path_map[stem] = path # 记录所有文件路径
                
                # 检查 main 标签 (需要读取文件)
                if 'main' in parse_yaml_tags(FileUtils.read_file(path) or []):
                    main_files.append(f)

        # 只要当前目录有 main 文件，就注册为项目（不管父级是否也是项目）
        if len(main_files) >= 1:
            # Sort by mtime DESC, then filename ASC
            # We want the LATEST modified.
            def get_sort_key(fname):
                fpath = os.path.join(root, fname)
                mtime = os.path.getmtime(fpath)
                return (-mtime, fname)
            
            main_files.sort(key=get_sort_key)
            selected_main = main_files[0]
            
            p_name = unicodedata.normalize('NFC', os.path.splitext(selected_main)[0])
            project_map[root] = p_name
            project_path_map[p_name] = os.path.join(root, selected_main)
            
    return project_map, project_path_map, file_path_map
