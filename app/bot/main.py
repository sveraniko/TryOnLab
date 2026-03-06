import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.bot.router import router
from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError('TELEGRAM_BOT_TOKEN is required to run bot service')

    bot = Bot(token=settings.telegram_bot_token)
    storage = RedisStorage(redis=Redis.from_url(settings.redis_url, decode_responses=True))
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    logger.info('Bot polling started', extra={'env': settings.app_env})
    await dp.start_polling(bot, settings=settings)


if __name__ == '__main__':
    asyncio.run(main())
