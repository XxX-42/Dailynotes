# Obsidian Dailynote Sync Daemon (v5.5)

本项目是一个专门用于 Obsidian 的双向同步守护进程，旨在实现「日记 (Daily Note)」与「项目源文件 (Source Files)」之间的任务无缝流转。它能够自动识别日记中的任务并同步到对应的项目文件，反之亦然，同时保持严格的格式规范。

## 核心功能

*   **双向同步**: Daily Note <-> Source File。
*   **格式自愈**: 强制执行严格的 Callout 格式 (`> [!note]- Tasks`)。
*   **智能清洗**: 自动清除空行、空列表项、幽灵引用符 (`> -`)。
*   **自动注册**: 在 Callout 中直接书写 `> - [ ] 任务`，会自动生成 ID 并转换为标准格式。
*   **多进程安全**: 内置文件锁和信号处理，防止多实例冲突。

## 文件结构说明

### `main.py`
**入口文件**。
*   负责启动守护进程。
*   处理进程锁逻辑（`ProcessLock`），确保系统中只有一个实例运行。
*   监听系统信号（如 `SIGKILL`）以安全退出。
*   实例化 `FusionManager` 并调用 `run()` 开始循环。

### `manager.py`
**调度管理器** (`FusionManager`)。
*   控制主循环 (`run`)。
*   管理扫描周期 (`TICK_INTERVAL`)。
*   协调 `SyncCore` 执行具体的扫描和同步任务 (`process_all_dates`)。
*   通过 `StateManager` 维护内存中的任务状态哈希，决策是否需要写文件。

### `sync_core.py`
**核心同步逻辑** (`SyncCore`)。
*   **格式化引擎**: 包含 `format_line`, `inject_into_callout` 等核心排版函数。
*   **清洗逻辑**: 实现了 `aggressive_callout_clean` (正则粉碎机) 和 `normalize_raw_tasks` (自动注册)。
*   **同步执行**: `process_date` 方法负责具体的读取、比对、合并和写入操作。
*   **文件操作**: 处理 Source File 头部 Callout 的注入、合并和清理。

### `state_manager.py`
**状态管理** (`StateManager`)。
*   维护内存中的任务指纹库 (`daily_data`, `source_data`)。
*   计算任务 Hash (`Config.hash_task`)，以此判断任务内容是否发生实质变更，避免无效写入。
*   提供增删改查（CRUD）接口供 `SyncCore` 调用。

### `utils.py`
**工具库**。
*   `Logger`: 提供带颜色高亮的控制台日志输出。
*   `FileUtils`: 封装安全的文件读写操作，处理编码问题。
*   `ProcessLock`: 基于 `fcntl` 的文件锁实现，用于进程互斥。

### `config.py`
**配置文件**。
*   定义全局常量：`ROOT_DIR` (仓库路径), `daily_header`, `source_header`。
*   配置运行参数：`TICK_INTERVAL` (扫描频率), `DEBUG_MODE`。

### `Dailynote.py` (Legacy)
**旧版单文件脚本**。
*   这是重构前的原始代码，保留作为参考备份。目前项目运行依赖 `main.py` 及上述模块化文件，不直接运行此文件。

## 运行方式

在 `Dailynote` 目录下并在激活的 Python 环境中运行：

```bash
python main.py
```

程序启动后会自动接管旧进程（如有），并开始每 3 秒扫描一次日记变动。
