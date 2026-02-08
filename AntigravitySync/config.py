import os


class Config:
    VERSION = "v3.0.0 (Chronos Mode)"    # [2026-01-22] Pure event-driven, no polling
    
    # ==========================
    # 1. 基础路径配置 (来自 Dailynotes)
    # ==========================
    VAULT_ROOT = r'/Users/user999/Documents/【Liang_project】/远程仓库1'
    REL_ATTACHMENT_DIR = r'【ATTACHMENT】'
    REL_TEMPLATE_FILE = r'【002_Infobox】/Templates/DayPlanTemplate.md'

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
    TYPING_COOLDOWN_SECONDS = 6
    IMAGE_PARAM_SUFFIX = "|L|200"
    DEBUG_MODE = True
    
    # [v3.7] Debug 日期范围模式
    # 设为 1 时进入调试模式，日记范围只对今天的日记有效（加速测试）
    DEBUG_TODAY_ONLY = 0
    
    # [v1.4] 事件驱动模式参数
    EVENT_DEBOUNCE_SECONDS = 0.5   # 事件触发防抖时间（秒）
    
    # [v3.6] 变更来源感知延迟
    # 根据检测到的变更来源，在执行格式化/同步前等待不同时间
    CHANGE_SOURCE_TYPING_DELAY = 6.0   # 用户打字：短延迟，减少打断感
    CHANGE_SOURCE_SYNC_DELAY = 11.0    # 后台同步：长延迟，等待批量同步稳定
    
    # [v3.0] Chronos Mode - 全事件驱动架构
    CHRONOS_SYNC_WINDOW_DAYS = 30      # 日历变更时同步的窗口大小（前后各15天）
    CHRONOS_FULL_RANGE_PAST_DAYS = 1   # 全量同步：过去N天 (前天+昨天)
    CHRONOS_FULL_RANGE_FUTURE_YEARS = 10  # 全量同步：未来N年
    CHRONOS_EVENTKIT_BATCH_DAYS = 1460  # EventKit批次大小（约4年，系统限制）
    CHRONOS_LOOP_INTERVAL = 60.0       # 主循环间隔（秒）
    
    # [v2.0+] 指数动态调度参数
    # 调度公式: I(d) = EXP_BASE * exp(EXP_COEFF * d) + EXP_OFFSET
    # d 为距今天数，I(d) 为同步间隔（秒）
    EXP_BASE = 60.0       # 基础间隔（秒）
    EXP_COEFF = 0.1       # 指数系数（正值表示越旧越慢）
    EXP_OFFSET = 30.0     # 偏移量/最小间隔（秒）
    
    # [v2.0] EventKit Sync
    # No file watching required for calendar
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
