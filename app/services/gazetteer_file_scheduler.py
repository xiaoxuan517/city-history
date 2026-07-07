from __future__ import annotations

import asyncio
import logging

from app.config.settings import settings
from app.services.gazetteer_file_service import sync_gazetteer_files_once

logger = logging.getLogger(__name__)


async def run_gazetteer_file_sync_loop() -> None:
    while True:
        try:
            synced_count = await asyncio.to_thread(sync_gazetteer_files_once)
            logger.info("县志文件同步完成。synced_count=%s", synced_count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("县志文件同步失败。")

        await asyncio.sleep(settings.gazetteer_file_sync_interval_seconds)
