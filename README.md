# LyubishchevSync

LyubishchevSync 是一个面向 macOS 的 Obsidian 日程与任务同步工具。它监听 Vault 中的 Markdown 变化，在项目文件、Daily Note、Apple Calendar 和 Apple Notes 之间执行格式化与双向同步。

> 该项目会修改 Markdown 文件和 Apple Calendar 事件。首次运行请使用测试 Vault 和专用 Calendar，确认同步结果后再连接正式数据。

## 主要功能

- 监听 Obsidian Vault 的 Markdown 创建、修改和移动事件。
- 在项目文件和 Daily Note 之间同步任务、Block ID、状态和反向链接。
- 格式化 Daily Note 的 Deployment、Thinking、Takein、Exercice 和 Economic 区域。
- Thinking 为用户维护的两列面板，格式化不再自动生成八列 ICE 表格，也不清空手写行；旧 ICE 权重和自动日历路由默认关闭。
- 根据 `#A` ～ `#D` 标签将任务映射到四个 Apple Calendar。
- 使用 EventKit 事件 ID 和指纹进行 Calendar 增量同步。
- 正确处理最后一个事件被删除、跨日移动和冷启动补偿。
- 从 Apple Notes 读取今日记录，并同步到 Obsidian Daily Note。
- 将 Apple Notes 图片导出到 Vault，并把图片嵌入追加到其上方数据行末尾。
- 提供 macOS 菜单栏状态、重启和日志入口。

### 项目任务区位置

项目任务区新建在正文末尾：`----------` 紧接在 `# Tasks` 上方，区末不再放分隔线。
正文与上方分隔线之间固定保留 10 个空行（11 个换行符）；旧任务区在下一次正常同步写入时迁移到尾部，
保留日期、ID、回链、子任务和手写内容。YAML 与代码块中的示例不参与识别。
旧式尾部分隔线继续兼容；区域在旧式 `----------`、下一个一级标题或文件末尾结束。多个任务区或未闭合代码块会中止同步，
不会被当作任务删除。启动扫描只读取，不批量迁移。

写入前原笔记备份到 Vault 外的 `~/Library/Application Support/LyubishchevSync/task-section-backups/`，
可用 `LYUBISHCHEV_TASK_BACKUP_DIR` 修改；备份失败或原文件发生并发变化时取消写入与状态推进。
写入还校验任务区外正文不变，并用线程锁／跨进程文件锁串行化程序自身的写入。
这些锁不约束 Obsidian 等外部编辑器：尚未保存的输入与校验到替换之间的极短竞态仍无法完全排除；
编辑同步任务或执行大量输入时可使用菜单栏“暂停 sync”，完成并保存后再继续。

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

### Apple Notes 图片

今日备忘录中的图片会保存到 `【ATTACHMENT】/AppleNotes/YYYY-MM-DD/`。图片按照 Notes HTML
中的正文顺序绑定到上方最近的非空数据行，并以 `![[...|L|200]]` 形式写入 Obsidian 行末。
附件 ID、哈希和绑定行记录在 Daily Note 目录的 `.apple_notes_attachment_state.json` 中；从
Notes 删除的图片会移动到 `【ATTACHMENT】/AppleNotes/.orphaned/`，不会立即删除。

当前 macOS Notes 的 AppleScript `set body` 在实机测试中会移除正文里的图片并重建附件。
因此含附件的备忘录采用安全模式：允许读取和导出图片、允许写入 Obsidian，但禁止整篇
`body` 回写和自动同名合并。纯文本备忘录保持原有双向写入行为。原始 HTML 恢复副本保存在
Daily Note 目录的 `.apple_notes_recovery/`。

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
