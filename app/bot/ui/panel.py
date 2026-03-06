from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup


async def try_delete(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest:
        return


async def safe_edit_panel(
    bot: Bot,
    *,
    chat_id: int,
    panel_message_id: int,
    text: str,
    keyboard: InlineKeyboardMarkup,
) -> None:
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=panel_message_id, text=text, reply_markup=keyboard)
    except TelegramBadRequest as exc:
        if 'message is not modified' in str(exc).lower():
            return
        raise


def render_progress_bar(progress: int) -> str:
    safe_progress = max(0, min(100, progress))
    full = safe_progress // 10
    return f"[{'█' * full}{'░' * (10 - full)}] {safe_progress}%"


async def ensure_panel(bot: Bot, *, chat_id: int, panel_message_id: int | None, fallback_text: str) -> int:
    if panel_message_id:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=panel_message_id, text=fallback_text)
            return panel_message_id
        except TelegramBadRequest:
            pass

    msg = await bot.send_message(chat_id=chat_id, text=fallback_text)
    return msg.message_id
