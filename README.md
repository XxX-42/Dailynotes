# LyubishchevSync

LyubishchevSync 是一个面向 macOS 的 Obsidian 日程与任务同步工具。它监听 Vault 中的 Markdown 变化，在项目文件、Daily Note、Apple Calendar 和 Apple Notes 之间执行格式化与双向同步。

> 该项目会修改 Markdown 文件和 Apple Calendar 事件。首次运行请使用测试 Vault 和专用 Calendar，确认同步结果后再连接正式数据。

## 主要功能

- 监听 Obsidian Vault 的 Markdown 创建、修改和移动事件。
- 在项目文件和 Daily Note 之间同步任务、Block ID、状态和反向链接。
- 格式化 Daily Note 的 Deployment、Thinking、Takein、Exercice 和 Economic 区域。
- 根据 `#A` ～ `#D` 标签将任务映射到四个 Apple Calendar。
- 使用 EventKit 事件 ID 和指纹进行 Calendar 增量同步。
- 正确处理最后一个事件被删除、跨日移动和冷启动补偿。
- 从 Apple Notes 读取今日记录，并同步到 Obsidian Daily Note。
- 提供 macOS 菜单栏状态、重启和日志入口。

## 架构

```text
main.py / gui_main.py
        │
        ▼
FusionManager
        ├── Watchdog 文件事件
        ├── EventKit Calendar 通知
        ├── SyncCore + TaskRegistry
        │       ├── parsing.py
        │       └── rendering.py
        ├── FormatCore
        ├── CalendarSyncPlanner
        │       └── CalendarEventIndex
        └── AppleSyncAdapter
                └── EventKit 双向同步引擎

Apple Notes 由独立 NoteMonitor 子进程处理。
```

核心目录：

```text
LyubishchevSync/
├── config.py
├── main.py
├── gui_main.py
└── src/
    ├── dailynotes/
    │   ├── manager.py
    │   ├── format_core.py
    │   ├── calendar_sync_planner.py
    │   ├── calendar_event_index.py
    │   └── sync/
    └── external/
        ├── eventkit_wrapper.py
        ├── note_sync_core/
        └── task_sync_core/
```

## 系统要求

- macOS
- Python 3.9 或更高版本
- Obsidian Vault
- Apple Calendar 和 Apple Notes 自动化权限

核心 Python 依赖：

```text
rumps==0.4.0
watchdog==6.0.0
pyobjc-core==11.1
pyobjc-framework-Cocoa==11.1
pyobjc-framework-EventKit==11.1
```

## 安装

```bash
python3 -m venv .venv_runtime
source .venv_runtime/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  rumps==0.4.0 \
  watchdog==6.0.0 \
  pyobjc-core==11.1 \
  pyobjc-framework-Cocoa==11.1 \
  pyobjc-framework-EventKit==11.1
```

macOS 首次运行时可能会请求 Calendar、Reminders、Notes 和辅助功能权限。如果权限被拒绝，请在“系统设置 → 隐私与安全性”中检查运行 Python 的终端或应用。

## 配置

建议通过环境变量选择 Vault 和 Daily Note 目录：

```bash
export LYUBISHCHEV_VAULT_ROOT="/path/to/vault"
export LYUBISHCHEV_DAILY_NOTE_DIR="/path/to/vault/00_Archive/2_DailyNote"
```

本项目的测试 Vault 配置示例：

```bash
export LYUBISHCHEV_VAULT_ROOT="/Users/jiajia/Documents/Documents/Obsidian/测试仓库/00_Archive"
export LYUBISHCHEV_DAILY_NOTE_DIR="/Users/jiajia/Documents/Documents/Obsidian/测试仓库/00_Archive/2_DailyNote"
```

其他主要配置位于 `LyubishchevSync/config.py`：

- `REL_TEMPLATE_FILE`：Daily Note 模板相对路径。
- `SYNC_START_DATE`：允许同步的最早日期。
- `TAG_MAPPINGS`：Obsidian 标签到 Apple Calendar 的映射。
- `ALARM_RULES`：各 Calendar 的提醒偏移。
- `CHRONOS_SYNC_WINDOW_DAYS`：Calendar 近期快速通道天数。
- `CHRONOS_FULL_RANGE_FUTURE_YEARS`：完整 EventKit 索引的未来年限。

默认受管 Calendar：

| Obsidian 标签 | Apple Calendar |
|---|---|
| `#A` | 重要紧急 |
| `#B` | 重要不紧急 |
| `#C` | 紧急不重要 |
| `#D` | 不重要不紧急 |

## 运行

菜单栏模式：

```bash
source .venv_runtime/bin/activate
python -u LyubishchevSync/gui_main.py
```

终端模式：

```bash
source .venv_runtime/bin/activate
python -u LyubishchevSync/main.py
```

日志默认输出到终端。本地启动脚本可将菜单栏日志重定向到：

```text
/tmp/LyubishchevSync_startup.log
```

## Calendar 增量同步

EventKit 的变更通知不包含具体事件或日期。LyubishchevSync 使用两层策略：

1. 近期快速通道扫描前各 15 天，仅提前执行可以安全证明的新增和窗口内修改。
2. 完整索引比较检测删除、跨窗口移动和远期变化。

冷启动处理日期集合为：

```text
Calendar 当前事件日期
∪ Obsidian 当前任务日期
∪ 历史同步快照日期
```

如果 EventKit 查询不完整、事件缺少稳定 ID，或 Calendar 批处理部分失败，系统不会执行删除推断，也不会推进同步快照和事件索引。

## 状态文件

状态文件位于 Daily Note 目录：

| 文件 | 用途 |
|---|---|
| `.sync_state.json` | Obsidian 任务指纹和路径状态 |
| `.apple_sync_state.json` | Obsidian/Calendar 双向同步快照 |
| `.calendar_event_index.json` | EventKit ID、日期和事件指纹 |
| `.fusion_sync_lock` | 主进程锁 |
| `.note_monitor.lock` | Apple Notes 监听进程锁 |
| `.modification_audit.json` | 最近文件写入审计记录 |

不建议在程序运行时手动修改这些文件。

## 测试

```bash
export LYUBISHCHEV_VAULT_ROOT="/Users/jiajia/Documents/Documents/Obsidian/测试仓库/00_Archive"
export LYUBISHCHEV_DAILY_NOTE_DIR="/Users/jiajia/Documents/Documents/Obsidian/测试仓库/00_Archive/2_DailyNote"
export PYTHONPATH="LyubishchevSync/src:LyubishchevSync"

.venv_runtime/bin/python -m unittest discover -s tests -v
.venv_runtime/bin/python -m compileall -q LyubishchevSync tests
```

当前回归测试覆盖：

- 删除某天最后一个 Calendar 事件。
- Calendar 事件跨日移动。
- 30 天快速窗口的安全边界。
- Calendar、Obsidian 与历史快照的冷启动并集。
- EventKit 查询不完整时禁止推进索引。
- Calendar 通知防抖。
- Daily Note 原子创建与不覆盖保证。

## 安全建议

- 为 LyubishchevSync 使用专用 Apple Calendar，不要将受管 Calendar 与普通个人日程混用。
- 在开启正式双向同步前备份 Vault 和 Calendar。
- 修改 `TAG_MAPPINGS`、`SYNC_START_DATE` 或 Daily Note 模板后，先在测试 Vault 中验证。
- 不要将包含完整笔记快照的 `.modification_audit.json` 提交到公开仓库。

## 当前限制

- 仅支持 macOS 的 EventKit、Apple Notes 和菜单栏能力。
- Apple Reminders 同步仍为实验性功能，尚未完成稳定的全量双向创建、修改和删除。
- Calendar 通知本身不提供变化日期，因此为了不遗漏远期变化，完整索引校验仍会读取配置范围内的 EventKit 事件。
