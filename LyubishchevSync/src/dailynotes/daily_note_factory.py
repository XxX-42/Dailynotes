from __future__ import annotations

import os

from config import Config
from .utils import FileUtils, Logger


def _base_scaffold():
    return [
        "---\n",
        "tags:\n",
        "  - DayPlan\n",
        "  - timecost\n",
        "  - tradecost\n",
        "---\n",
        Config.DEPLOYMENT_HEADER + "\n",
        "\n",
        Config.THINKING_HEADER + "\n",
        "\n",
        "| id  |     |\n",
        "| --- | --- |\n",
        "\n",
        Config.TAKEIN_HEADER + "\n",
        "\n",
        Config.EXERCICE_HEADER + "\n",
        "\n",
        Config.ECONOMIC_HEADER + "\n",
        "\n",
    ]


def ensure_daily_note(date_str: str, reason: str = "sync") -> str:
    """Create a daily note exactly once and never overwrite an existing file."""
    daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{date_str}.md")
    if os.path.exists(daily_path):
        return "ALREADY_EXISTS"

    os.makedirs(Config.DAILY_NOTE_DIR, exist_ok=True)
    content = None
    if os.path.exists(Config.TEMPLATE_FILE):
        content = FileUtils.read_file(Config.TEMPLATE_FILE)
    if not content:
        content = _base_scaffold()
        Logger.info(
            f"   ⚠️ 未找到可用模板 ({Config.REL_TEMPLATE_FILE})，使用基础骨架: {date_str}.md"
        )

    result = FileUtils.create_file_if_absent(daily_path, content)
    if result == "CREATED":
        Logger.info(f"   📄 [DailyNote] 已创建: {date_str}.md (reason={reason})")
    return result
