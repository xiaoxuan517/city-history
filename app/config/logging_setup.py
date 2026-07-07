from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config.settings import settings

APP_LOGGER_NAME = "app"
MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3


def setup_logging() -> Path:
    app_logger = logging.getLogger(APP_LOGGER_NAME)
    if getattr(app_logger, "_rag_logging_configured", False):
        for handler in app_logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                return Path(handler.baseFilename)
        return Path(settings.log_dir) / settings.log_file_name

    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / settings.log_file_name

    level = getattr(logging, settings.log_level, logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    app_logger.setLevel(level)
    app_logger.addHandler(file_handler)
    app_logger.propagate = False
    app_logger._rag_logging_configured = True  # type: ignore[attr-defined]

    return log_path
