from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _mk(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def home_keyboard(can_generate: bool) -> InlineKeyboardMarkup:
    gen = InlineKeyboardButton(text='⚡ Генерировать' if can_generate else '⚡ Генерировать (недоступно)', callback_data='gen:image')
    return _mk(
        [
            [InlineKeyboardButton(text='🧥 Товар', callback_data='nav:product'), InlineKeyboardButton(text='👤 Моё фото', callback_data='nav:userphoto')],
            [InlineKeyboardButton(text='🎯 Посадка', callback_data='nav:fit'), InlineKeyboardButton(text='📏 Параметры', callback_data='nav:measurements')],
            [gen],
            [
                InlineKeyboardButton(text='🧾 История', callback_data='nav:history'),
                InlineKeyboardButton(text='⚙️ Настройки', callback_data='nav:settings'),
                InlineKeyboardButton(text='🧼 Сброс сессии', callback_data='session:reset'),
            ],
        ]
    )


def back_keyboard(target: str = 'home') -> InlineKeyboardMarkup:
    return _mk([[InlineKeyboardButton(text='⬅️ Назад', callback_data=f'nav:{target}')]])
