from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

HAS_SQLALCHEMY = True

try:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
except ModuleNotFoundError:  # pragma: no cover - lightweight test env fallback
    HAS_SQLALCHEMY = False
    AsyncSession = object  # type: ignore[assignment,misc]

    def select(*_args, **_kwargs):
        return None

from app.services.storage import StorageBackend

try:
    from app.db.models import Job
except ModuleNotFoundError:  # pragma: no cover - lightweight test env fallback
    class Job:  # type: ignore[no-redef]
        expires_at = None
        status = None

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


async def safe_delete(storage: StorageBackend, key: str | None) -> None:
    if not key:
        return
    try:
        await storage.delete(key)
    except Exception:
        logger.warning('Failed to delete storage key', extra={'storage_key': key}, exc_info=True)


async def cleanup_expired_jobs(
    *,
    session: AsyncSession,
    redis: 'Redis',
    storage: StorageBackend,
    limit: int = 100,
) -> int:
    now = datetime.now(timezone.utc)
    if HAS_SQLALCHEMY:
        query = (
            select(Job)
            .where(
                Job.expires_at.is_not(None),
                Job.expires_at < now,
                Job.status.in_(['done', 'failed']),
                Job.status != 'expired',
            )
            .order_by(Job.expires_at.asc())
            .limit(limit)
        )
    else:
        query = None

    jobs = list(await session.scalars(query))

    if not jobs:
        return 0

    for job in jobs:
        await safe_delete(storage, job.product_media_key)
        await safe_delete(storage, job.user_media_key)
        await safe_delete(storage, job.result_image_key)
        await safe_delete(storage, job.result_video_key)
        job.status = 'expired'
        await redis.delete(f'job:{job.id}:status')

    await session.commit()
    return len(jobs)
