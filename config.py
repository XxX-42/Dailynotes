import os


class Config:
    # --- [核心] 仓库根目录 (换电脑/位置只需改这一行) ---
    VAULT_ROOT = r'/Users/user999/Documents/【Liang_project】/远程仓库1'

    # --- [相对] 子路径配置 ---
    REL_ATTACHMENT_DIR = r'【ATTACHMENT】'

    # 模版文件 (相对于根目录)
    REL_TEMPLATE_FILE = r'DayPlanTemplate.md'

    # --- [自动生成] 绝对路径 ---
    # 注意：在类定义中直接引用变量是合法的，但不能放在列表推导式里

    # 1. 日记目录
    # 拼接: Root / Attachment / DailyNote
    DAILY_NOTE_DIR = os.path.join(VAULT_ROOT, REL_ATTACHMENT_DIR, r'【DAILYNOTE】')

    # 2. 模版文件
    TEMPLATE_FILE = os.path.join(VAULT_ROOT, REL_TEMPLATE_FILE)

    # 3. 排除目录 (Fix: 显式拼接，避开列表推导式作用域问题)
    EXCLUDE_DIRS = [
        os.path.join(VAULT_ROOT, REL_ATTACHMENT_DIR),
        os.path.join(VAULT_ROOT, r'.trash'),
    ]

    # --- [软排除] 仅归档，不同步 (NEW) ---
    # 系统会索引这些目录，允许任务归档进去，但不会主动扫描里面的任务同步回日记
    SYNC_IGNORE_DIRS = [
        os.path.join(VAULT_ROOT, r'「」InfoBox/「InfoManage」Updating OBlifeos/【Templates】')
    ]

    # --- [NEW] 强制聚合/黑洞目录 ---
    # 定义：在此目录下的所有子文件夹，即使包含 Main 标签文件，也会被忽略项目属性。
    # 结果：其内部产生的所有流浪任务，都会强制向上冒泡，归档到此目录本身的 Main 文件中。
    FORCED_AGGREGATION_DIRS = [
        os.path.join(VAULT_ROOT, r'「」InfoBox/「InfoManage」Updating OBlifeos/【Templates】')
    ]

    # 兼容旧代码的别名
    ROOT_DIR = VAULT_ROOT

    # 状态文件与锁文件
    STATE_FILE = os.path.join(DAILY_NOTE_DIR, ".sync_state.json")
    LOCK_FILE = os.path.join(DAILY_NOTE_DIR, ".fusion_sync_lock")

    # --- [战略] 时间门控 ---
    SYNC_START_DATE = "2025-12-08"

    # --- 行为参数 ---
    TICK_INTERVAL = 2
    TYPING_COOLDOWN_SECONDS = 6
    IMAGE_PARAM_SUFFIX = "|L|200"
    DEBUG_MODE = True

    # --- 范围限制 ---
    DAILY_NOTE_SECTIONS = ['# Day planner', '# Journey']
    SOURCE_FILE_CALLOUTS = ['> [!note] Tasks', '> [!note]- Tasks', '> [!note]+ Tasks']