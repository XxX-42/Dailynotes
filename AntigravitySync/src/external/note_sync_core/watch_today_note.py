
import sys
import os
import time
import logging

# ==========================================
# 路径设置: 确保能导入项目模块
# ==========================================
# 1. 当前脚本所在目录: src/external/note_sync_core/
current_dir = os.path.dirname(os.path.abspath(__file__))
# 2. 项目根目录 (AntigravitySync 的父目录，即 Beta Folder)
# src/external/note_sync_core/ -> src/external/ -> src/ -> AntigravitySync -> Root
beta_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))

if beta_root not in sys.path:
    sys.path.append(beta_root)

# 3. AntigravitySync 根目录
antigravity_root = os.path.join(beta_root, 'AntigravitySync')
if antigravity_root not in sys.path:
    sys.path.append(antigravity_root)

# ==========================================
# 导入模块
# ==========================================
try:
    from config import Config
    from src.dailynotes.utils import Logger
except ImportError as e:
    print(f"❌ [Error] 无法导入 Config 或 Logger: {e}")
    print(f"   sys.path: {sys.path}")
    sys.exit(1)

try:
    from monitor import NoteMonitor
except ImportError as e:
    # 尝试相对导入
    sys.path.append(current_dir)
    from monitor import NoteMonitor

# ==========================================
# 简单的 Logger 适配器 (如果 Utils Logger不可用)
# ==========================================
class SimpleLogger:
    @staticmethod
    def info(msg):
        print(msg)

# ==========================================
# 主入口
# ==========================================
def main():
    print("🚀 [Launcher] 正在启动 NoteMonitor (via watch_today_note.py wrapper)...")
    
    # 使用项目 Logger 或 SimpleLogger
    logger = Logger if 'Logger' in locals() else SimpleLogger
    
    # 初始化 Monitor
    # Config 应该包含 DAILY_NOTE_DIR, TEMPLATE_FILE, KEYWORD_MAPPING
    monitor = NoteMonitor(config=Config, logger=logger)
    
    try:
        monitor.start()
        
        # 保持主线程运行 (NoteMonitor 是 daemon 线程)
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 [Launcher] 停止中...")
        monitor.stop()
    except Exception as e:
        print(f"❌ [Launcher] 异常: {e}")
        monitor.stop()

if __name__ == "__main__":
    main()
