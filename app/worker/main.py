from __future__ import annotations

import asyncio
import logging
import signal

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import engine
from app.providers import build_default_registry
from app.services.storage import create_storage
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
        await run_worker_loop(
            redis=redis,
            settings=settings,
            storage=storage,
            registry=registry,
            shutdown_event=shutdown_event,
        )
    finally:
        await redis.aclose()
        await engine.dispose()
        logger.info('Worker stopped')


def main() -> None:
    asyncio.run(_run())


if __name__ == '__main__':
    main()
