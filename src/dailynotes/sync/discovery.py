import os
import unicodedata
from config import Config
from ..utils import FileUtils
from .parsing import parse_yaml_tags

def scan_projects():
    project_map = {}
    project_path_map = {}
    file_path_map = {}

    # 预处理：标准化聚合目录路径，避免不同系统的斜杠差异
    forced_dirs = [os.path.normpath(p) for p in Config.FORCED_AGGREGATION_DIRS]

    for root, dirs, files in os.walk(Config.ROOT_DIR):
        dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
        if FileUtils.is_excluded(root): continue

        main_files = []
        for f in files:
            if f.endswith('.md'):
                path = os.path.join(root, f)
                f_name = unicodedata.normalize('NFC', os.path.splitext(f)[0])
                file_path_map[f_name] = path

                # 依然读取 tags，保持文件级别的识别能力
                if 'main' in parse_yaml_tags(FileUtils.read_file(path) or []):
                    main_files.append(f)

        # === [核心修改 START] ===
        is_shadowed = False
        norm_root = os.path.normpath(root)

        for parent_dir in forced_dirs:
            if norm_root.startswith(parent_dir) and len(norm_root) > len(parent_dir):
                rel_path = norm_root[len(parent_dir):]
                if rel_path.startswith(os.sep):
                    is_shadowed = True
                    break

        if is_shadowed:
            continue
        # === [核心修改 END] ===

        if len(main_files) == 1:
            p_name = unicodedata.normalize('NFC', os.path.splitext(main_files[0])[0])
            project_map[root] = p_name
            project_path_map[p_name] = os.path.join(root, main_files[0])
            
    return project_map, project_path_map, file_path_map
