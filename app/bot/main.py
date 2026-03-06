import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

router = Router()


@router.message(Command('start'))
async def start_handler(message: Message) -> None:
    await message.answer('Panel stub: TryOnLab (PR-00)')


@router.message(Command('help'))
async def help_handler(message: Message) -> None:
    await message.answer('Доступные команды: /start, /help')


async def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError('TELEGRAM_BOT_TOKEN is required to run bot service')

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    logger.info('Bot polling started', extra={'env': settings.app_env})
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
