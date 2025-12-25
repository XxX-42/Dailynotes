import os

# 1. 定义忽略名单 (文件夹或特定文件)
IGNORE_LIST = {
    '.git', '.github', '__pycache__', 'node_modules', '.venv', '.vscode',
    '.DS_Store', 'dist', 'build', 'venv', 'env', 'obsidian'
}

def generate_tree(root_dir, current_dir, prefix=""):
    """递归生成项目目录结构树"""
    tree_str = ""
    items = sorted(os.listdir(current_dir))
    # 过滤忽略项
    items = [i for i in items if i not in IGNORE_LIST and not i.endswith('.md')]
    
    for i, item in enumerate(items):
        path = os.path.join(current_dir, item)
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "
        
        tree_str += f"{prefix}{connector}{item}\n"
        
        if os.path.isdir(path):
            extension_prefix = "    " if is_last else "│   "
            tree_str += generate_tree(root_dir, path, prefix + extension_prefix)
    return tree_str

def aggregate_project():
    # 获取当前工作目录及目录名
    current_dir = os.path.dirname(os.path.abspath(__file__))
    folder_name = os.path.basename(current_dir)
    output_filename = f"{folder_name}.md"
    output_path = os.path.join(current_dir, output_filename)

    with open(output_path, 'w', encoding='utf-8') as outfile:
        # 写入标题和项目树
        outfile.write(f"# Project Architecture: {folder_name}\n\n")
        outfile.write("## Directory Tree\n```text\n")
        outfile.write(f"{folder_name}/\n")
        outfile.write(generate_tree(current_dir, current_dir))
        outfile.write("```\n\n---\n\n")

        # 递归遍历文件内容
        for root, dirs, files in os.walk(current_dir):
            # 关键：原地修改 dirs 列表，以便 os.walk 跳过忽略的目录
            dirs[:] = [d for d in dirs if d not in IGNORE_LIST]
            
            for file in sorted(files):
                # 跳过脚本自身、生成的输出文件以及其他忽略文件
                if file == os.path.basename(__file__) or file == output_filename or file in IGNORE_LIST:
                    continue
                
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, current_dir)

                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        content = infile.read()
                        
                        ext = os.path.splitext(file)[1][1:] or "text"
                        outfile.write(f"## File: {relative_path}\n")
                        outfile.write(f"```{ext}\n")
                        outfile.write(content)
                        outfile.write(f"\n```\n\n---\n")
                        print(f"[SUCCESS] Aggregated: {relative_path}")
                except (UnicodeDecodeError, PermissionError):
                    print(f"[SKIPPED] Non-text or restricted: {relative_path}")

    print(f"\n[DONE] 结果已保存至: {output_filename}")

if __name__ == "__main__":
    aggregate_project()