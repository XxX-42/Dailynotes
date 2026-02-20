project_path_map = {
    "测试项目": "/Users/user999/Documents/【Liang_project】/远程仓库1/测试文件.md",
    "另一个项目": "/Users/user999/Documents/【Liang_project】/远程仓库1/项目/main.md"
}

filepaths = [
    "/Users/user999/Documents/【Liang_project】/远程仓库1/测试文件.md",
    "/Users/user999/Documents/【Liang_project】/远程仓库1/未知文件.md"
]

for filepath in filepaths:
    self_project_name = None
    for p_name, p_path in project_path_map.items():
        if p_path == filepath:
            self_project_name = p_name
            break
            
    print(f"File: {filepath} -> Self Project: {self_project_name}")
