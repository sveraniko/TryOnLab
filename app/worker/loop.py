from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import Job
from app.db.session import AsyncSessionLocal
from app.providers.base import ProviderError
from app.providers.registry import ProviderRegistry
from app.services.job_status import set_job_status
from app.services.storage import StorageBackend
from app.worker.executor import execute_job
from app.worker.locks import release_lock, renew_lock

logger = logging.getLogger(__name__)


async def _lock_heartbeat(
    *, redis: Redis, key: str, token: str, lease_seconds: int, renew_interval_seconds: int
) -> None:
    while True:
        await asyncio.sleep(renew_interval_seconds)
        renewed = await renew_lock(redis, key=key, token=token, lease_seconds=lease_seconds)
        if not renewed:
            logger.warning('Lost job lock during heartbeat renewal', extra={'lock_key': key})
            return


async def run_worker_loop(
    redis: Redis,
    settings: Settings,
    storage: StorageBackend,
    registry: ProviderRegistry,
    shutdown_event: asyncio.Event,
) -> None:
    while not shutdown_event.is_set():
        item = await redis.blpop(settings.job_queue_key, timeout=5)
        if item is None:
            continue

        _, raw_job_id = item
        try:
            job_id = uuid.UUID(raw_job_id)
        except ValueError:
            logger.warning('Skipping invalid job id from queue', extra={'job_id': raw_job_id})
            continue

        lock_key = f'lock:job:{job_id}'
        lock_token = uuid.uuid4().hex
        lock_taken = await redis.set(
            lock_key,
            lock_token,
            nx=True,
            ex=settings.worker_lock_lease_seconds,
        )
        if not lock_taken:
            continue

        heartbeat_task = asyncio.create_task(
            _lock_heartbeat(
                redis=redis,
                key=lock_key,
                token=lock_token,
                lease_seconds=settings.worker_lock_lease_seconds,
                renew_interval_seconds=settings.worker_lock_renew_interval_seconds,
            )
        )

        try:
            await _process_job(redis=redis, settings=settings, storage=storage, registry=registry, job_id=job_id)
        finally:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
            await release_lock(redis, key=lock_key, token=lock_token)


async def _process_job(
    redis: Redis,
    settings: Settings,
    storage: StorageBackend,
    registry: ProviderRegistry,
    job_id: uuid.UUID,
) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.scalar(select(Job).where(Job.id == job_id))
        if job is None:
            logger.warning('Job from queue not found in DB', extra={'job_id': str(job_id)})
            return

        logger.info('Job state transition', extra={'job_id': str(job.id), 'provider': job.provider, 'type': job.type, 'attempt': job.attempts, 'from_status': job.status, 'to_status': 'running'})
        now = datetime.now(UTC)
        job.status = 'running'
        job.started_at = now
        job.progress = 5 if job.type == 'tryon_image' else 10
        await session.commit()
        await set_job_status(redis, job.id, status='running', progress=job.progress, ttl=settings.job_status_ttl_seconds)

        async def _on_progress(progress: int) -> None:
            normalized = max(0, min(100, progress))
            if job.progress == normalized:
                return
            job.progress = normalized
            await session.commit()
            await set_job_status(
                redis,
                job.id,
                status='running',
                progress=normalized,
                ttl=settings.job_status_ttl_seconds,
            )

        try:
            await execute_job(session, storage, job, registry, on_progress=_on_progress)
            job.status = 'done'
            job.progress = 100
            job.error_code = None
            job.error_message = None
            job.finished_at = datetime.now(UTC)
            await session.commit()
            logger.info('Job state transition', extra={'job_id': str(job.id), 'provider': job.provider, 'type': job.type, 'attempt': job.attempts, 'from_status': 'running', 'to_status': 'done'})
            await set_job_status(redis, job.id, status='done', progress=100, ttl=settings.job_status_ttl_seconds)
        except ProviderError as exc:
            job.status = 'failed'
            job.error_code = exc.code
            job.error_message = exc.message
            job.is_retryable = exc.retryable
            job.finished_at = datetime.now(UTC)
            await session.commit()
            logger.warning('Job failed with provider error', extra={'job_id': str(job.id), 'provider': job.provider, 'type': job.type, 'attempt': job.attempts, 'error_code': exc.code, 'is_retryable': exc.retryable})
            await set_job_status(redis, job.id, status='failed', progress=job.progress or 1, ttl=settings.job_status_ttl_seconds)
        except Exception:
            logger.exception('Unhandled exception during job processing', extra={'job_id': str(job.id)})
            job.status = 'failed'
            job.error_code = 'internal'
            job.error_message = 'Unhandled worker error'
            job.is_retryable = False
            job.finished_at = datetime.now(UTC)
            await session.commit()
            logger.error('Job failed with internal error', extra={'job_id': str(job.id), 'provider': job.provider, 'type': job.type, 'attempt': job.attempts, 'error_code': 'internal', 'is_retryable': False})
            await set_job_status(redis, job.id, status='failed', progress=job.progress or 1, ttl=settings.job_status_ttl_seconds)
