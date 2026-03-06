from __future__ import annotations

import asyncio
import logging
import signal

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal, engine
from app.providers import build_default_registry
from app.services.storage import create_storage
from app.worker.cleanup import cleanup_expired_jobs
from app.worker.loop import run_worker_loop

logger = logging.getLogger(__name__)


async def _run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _trigger_shutdown() -> None:
        logger.info('Worker shutdown signal received')
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _trigger_shutdown)

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    storage = create_storage(settings)
    registry = build_default_registry(storage, settings)

    try:
        logger.info('Worker started')
        async def _cleanup_loop() -> None:
            while not shutdown_event.is_set():
                try:
                    async with AsyncSessionLocal() as session:
                        cleaned = await cleanup_expired_jobs(session=session, redis=redis, storage=storage, limit=100)
                    if cleaned:
                        logger.info('Cleanup expired jobs completed', extra={'cleaned_jobs': cleaned})
                except Exception:
                    logger.exception('Cleanup loop failed')
                await asyncio.sleep(settings.cleanup_interval_seconds)

        worker_task = asyncio.create_task(
            run_worker_loop(
                redis=redis,
                settings=settings,
                storage=storage,
                registry=registry,
                shutdown_event=shutdown_event,
            )
        )
        cleanup_task = asyncio.create_task(_cleanup_loop())
        await asyncio.wait({worker_task, cleanup_task}, return_when=asyncio.FIRST_EXCEPTION)

        for task in (worker_task, cleanup_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(worker_task, cleanup_task, return_exceptions=True)
    finally:
        await redis.aclose()
        await engine.dispose()
        logger.info('Worker stopped')


def main() -> None:
    asyncio.run(_run())


if __name__ == '__main__':
    main()
