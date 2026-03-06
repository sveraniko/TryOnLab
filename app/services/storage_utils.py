from __future__ import annotations

import logging

from app.services.storage import StorageBackend

logger = logging.getLogger(__name__)


async def safe_delete(storage: StorageBackend, key: str | None) -> None:
    if not key:
        return
    try:
        await storage.delete(key)
    except Exception:
        logger.warning('Failed to delete storage key', extra={'storage_key': key}, exc_info=True)
