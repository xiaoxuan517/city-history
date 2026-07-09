from __future__ import annotations

import asyncio
import logging

from app.config.settings import settings
from app.services.old_picture_service import sync_old_pictures_once

logger = logging.getLogger(__name__)


async def run_old_picture_sync_loop() -> None:
    while True:
        try:
            synced_count = await asyncio.to_thread(sync_old_pictures_once)
            logger.info("历史图片同步完成。synced_count=%s", synced_count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("历史图片同步失败。")

        await asyncio.sleep(settings.old_picture_sync_interval_seconds)
