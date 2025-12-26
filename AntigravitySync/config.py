import os


class Config:
    VERSION = "v1.2"    # [2025-12-26] Tick-Based + Archive Link Fix + Multi-Main
    
    # ==========================
    # 1. 基础路径配置 (来自 Dailynotes)
    # ==========================
    VAULT_ROOT = r'/Users/user999/Documents/【Liang_project】/远程仓库1'
    REL_ATTACHMENT_DIR = r'【ATTACHMENT】'
    REL_TEMPLATE_FILE = r'DayPlanTemplate.md'

    # 自动拼接
    DAILY_NOTE_DIR = os.path.join(VAULT_ROOT, REL_ATTACHMENT_DIR, r'【DAILYNOTE】')
    TEMPLATE_FILE = os.path.join(VAULT_ROOT, REL_TEMPLATE_FILE)

    # 排除项
    EXCLUDE_DIRS = [
        os.path.join(VAULT_ROOT, REL_ATTACHMENT_DIR),
        os.path.join(VAULT_ROOT, r'.trash'),
    ]
    SYNC_IGNORE_DIRS = [
        os.path.join(VAULT_ROOT, r'「」InfoBox/「InfoManage」Updating OBlifeos/【Templates】')
    ]
    FORCED_AGGREGATION_DIRS = SYNC_IGNORE_DIRS

    # 兼容性别名
    ROOT_DIR = VAULT_ROOT
    STATE_FILE = os.path.join(DAILY_NOTE_DIR, ".sync_state.json")
    LOCK_FILE = os.path.join(DAILY_NOTE_DIR, ".fusion_sync_lock")

    # 运行参数
    SYNC_START_DATE = "2025-12-08"
    TICK_INTERVAL = 2
    TYPING_COOLDOWN_SECONDS = 6
    IMAGE_PARAM_SUFFIX = "|L|200"
    DEBUG_MODE = True
    
    # [NEW] Tick-based scheduling parameters
    DAY_START = -1  # -1 = 昨天
    DAY_END = 6     # 6 = 未来6天
    COMPLETE_TASKS_SYNC_INTERVAL = 5  # 每5个tick执行一次全量扫描


    # 范围限制
    DAILY_NOTE_SECTIONS = ['# Day planner', '# Journey']
    SOURCE_FILE_CALLOUTS = ['> [!note] Tasks', '> [!note]- Tasks', '> [!note]+ Tasks']

    # ==========================
    # 2. Apple Sync 配置 (来自 TaskSynctoreminder)
    # ==========================
    APPLE_SYNC_STATE_FILE = os.path.join(DAILY_NOTE_DIR, ".apple_sync_state.json")

    # 默认日历
    REMINDERS_LIST_NAME = "不重要不紧急"

    # 标签映射
    TAG_MAPPINGS = [
        {"tag": "#A", "calendar": "重要紧急"},
        {"tag": "#B", "calendar": "重要不紧急"},
        {"tag": "#C", "calendar": "紧急不重要"},
        {"tag": "#D", "calendar": "不重要不紧急"}
    ]

    # 警报规则
    ALARM_RULES = {
        "重要紧急": -30,
        "重要不紧急": -5,
        "紧急不重要": 0,
        "不重要不紧急": 0,
        REMINDERS_LIST_NAME: 0
    }

    # 派生常量 (来自 TaskSynctoreminder/constants.py)
    CAL_TO_TAG = {m["calendar"]: m["tag"] for m in TAG_MAPPINGS}
    ALL_MANAGED_CALENDARS = [m["calendar"] for m in TAG_MAPPINGS]
    if REMINDERS_LIST_NAME not in ALL_MANAGED_CALENDARS:
        ALL_MANAGED_CALENDARS.append(REMINDERS_LIST_NAME)

    # 安全分隔符
    DELIMITER_FIELD = "|#|"
    DELIMITER_ROW = "^@^"
