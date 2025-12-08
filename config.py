import os

class Config:
    # --- 路径配置 (请确认路径准确) ---
    ROOT_DIR = r'/Users/user999/Documents/【Liang_project】/远程仓库2/'

    EXCLUDE_DIRS = [
        r'/Users/user999/Documents/【Liang_project】/远程仓库2/【ATTACHMENT】',
        r'/Users/user999/Documents/【Liang_project】/远程仓库2/.trash',
    ]

    DAILY_NOTE_DIR = r'/Users/user999/Documents/【Liang_project】/远程仓库2/【ATTACHMENT】/【DAILYNOTE】/'

    # 状态文件 (黑匣子) 与 锁文件
    STATE_FILE = os.path.join(DAILY_NOTE_DIR, ".sync_state.json")
    LOCK_FILE = os.path.join(DAILY_NOTE_DIR, ".fusion_sync_lock")

    # --- 行为参数 ---
    TICK_INTERVAL = 2
    # 防抖时间：5 秒
    TYPING_COOLDOWN_SECONDS = 6
    IMAGE_PARAM_SUFFIX = "|L|200"
    DEBUG_MODE = True

    # --- 范围限制 ---
    # 仅在这些标题下的内容会被每日笔记同步处理
    DAILY_NOTE_SECTIONS = ['# Day planner', '# Journey']
    
    # 仅在这些 Callout 中的内容会被项目文件同步处理
    SOURCE_FILE_CALLOUTS = ['> [!note] Tasks', '> [!note]- Tasks', '> [!note]+ Tasks']
