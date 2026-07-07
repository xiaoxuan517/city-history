from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from app.config.settings import Settings, settings

logger = logging.getLogger(__name__)


def _resolve_sqlite_path(path: str) -> Path:
    resolved = Path(path).expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def build_checkpointer(config: Settings = settings) -> Any:
    if config.checkpointer_type == "memory":
        logger.info("初始化内存会话状态。checkpointer=memory")
        return InMemorySaver()

    sqlite_path = _resolve_sqlite_path(config.checkpointer_sqlite_path)
    conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    logger.info("初始化 SQLite 会话状态。path=%s", sqlite_path)
    return checkpointer
