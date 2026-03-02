#!/usr/bin/env python3
"""
独立运行 NoteMonitor 的测试脚本
直接启动 Apple Notes 监听，完整输出所有调试日志

用法:
  python run_note_monitor.py
"""
import sys
import os
import time
import datetime

# ==========================================
# 路径设置
# ==========================================
# 当前脚本: src/external/note_sync_core/run_note_monitor.py
# 回溯到:   LyubishchevSync/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))          # note_sync_core/
LYUBISHCHEV_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))  # LyubishchevSync/
os.chdir(LYUBISHCHEV_ROOT)
sys.path.insert(0, os.path.join(LYUBISHCHEV_ROOT, 'src'))
sys.path.insert(0, LYUBISHCHEV_ROOT)
sys.path.insert(0, SCRIPT_DIR)

# ==========================================
# 导入
# ==========================================
from config import Config
from monitor import NoteMonitor

# ==========================================
# 彩色日志工具
# ==========================================
class ColorLogger:
    """带颜色和时间戳的控制台日志"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def info(msg):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        print(f"{ColorLogger.GREEN}[{ts}]{ColorLogger.RESET} {msg}")

    @staticmethod
    def header(msg):
        print(f"\n{ColorLogger.BOLD}{ColorLogger.CYAN}{'='*60}")
        print(f"  {msg}")
        print(f"{'='*60}{ColorLogger.RESET}\n")

# ==========================================
# 启动前诊断
# ==========================================
def run_diagnostics():
    """启动前检查环境"""
    from reader import AppleNotesReader

    logger = ColorLogger
    logger.header("🔬 NoteMonitor 独立运行 - 启动前诊断")

    # 1. 检查 Config
    daily_dir = getattr(Config, 'DAILY_NOTE_DIR', None)
    logger.info(f"📁 DAILY_NOTE_DIR: {daily_dir}")
    if daily_dir and os.path.exists(daily_dir):
        logger.info(f"   ✅ 目录存在")
    else:
        logger.info(f"   ❌ 目录不存在!")
        return False

    # 2. 检查今日日记
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    today_file = os.path.join(daily_dir, f"{today_str}.md")
    if os.path.exists(today_file):
        with open(today_file, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.info(f"📄 今日日记 ({today_str}.md): {len(content)} chars")
    else:
        logger.info(f"⚠️  今日日记不存在: {today_file}")

    # 3. 检查 Apple Notes 读取
    reader = AppleNotesReader()
    today = datetime.date.today()
    note_name = f"{today.year}/{today.month}/{today.day}"
    logger.info(f"🍎 尝试读取备忘录: '{note_name}'...")

    note_content = reader.get_note_content(note_name)
    if note_content and note_content != "NOT_FOUND":
        logger.info(f"   ✅ 备忘录内容: {len(note_content)} chars, Hash: {hash(note_content)}")
        lines = note_content.splitlines()
        logger.info(f"   📋 行数: {len(lines)}")
        for i, line in enumerate(lines):
            logger.info(f"   [{i:2d}] {line}")
    else:
        logger.info(f"   ❌ 备忘录未找到!")
        return False

    # 4. 检查 TaskRegistry
    try:
        from dailynotes.sync.task_registry import get_registry
        reg = get_registry()
        if reg.is_initialized():
            logger.info(f"📦 TaskRegistry: ✅ 已初始化")
        else:
            logger.info(f"📦 TaskRegistry: ⚠️ 未初始化 (心跳可能无法跨文件寻址)")
    except Exception as e:
        logger.info(f"📦 TaskRegistry: ❌ 不可用 ({e})")

    logger.info("")
    return True

# ==========================================
# 主入口
# ==========================================
def main():
    logger = ColorLogger

    # 诊断
    ok = run_diagnostics()
    if not ok:
        logger.info("❌ 诊断失败，无法启动")
        sys.exit(1)

    # 启动 NoteMonitor
    logger.header("🚀 启动 NoteMonitor (Ctrl+C 停止)")
    monitor = NoteMonitor(config=Config, logger=logger)

    try:
        monitor.start()
        logger.info("✅ NoteMonitor 已在后台运行 (daemon 线程)")
        logger.info("💡 现在去 Apple Notes 编辑备忘录，观察终端输出...")
        logger.info("")

        # 保持主线程运行
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print(f"\n{ColorLogger.YELLOW}🛑 正在停止...{ColorLogger.RESET}")
        monitor.stop()
        print(f"{ColorLogger.GREEN}✅ 已停止{ColorLogger.RESET}")
    except Exception as e:
        print(f"{ColorLogger.RED}❌ 异常: {e}{ColorLogger.RESET}")
        import traceback
        traceback.print_exc()
        monitor.stop()

if __name__ == "__main__":
    main()
