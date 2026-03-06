from __future__ import annotations

from enum import StrEnum

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.keyboards import back_keyboard, home_keyboard


class Screen(StrEnum):
    HOME = 'home'
    PRODUCT = 'product'
    USER_PHOTO_MENU = 'user_photo_menu'
    USER_PHOTO_LIST = 'user_photo_list'
    USER_PHOTO_UPLOAD = 'user_photo_upload'
    FIT = 'fit'
    MEASUREMENTS = 'measurements'
    GENERATE = 'generate'
    VIDEO_MENU = 'video_menu'
    SETTINGS = 'settings'
    PROVIDER = 'provider'
    HISTORY = 'history'
    PURGE_CONFIRM = 'purge_confirm'


def render(screen: Screen, context: dict) -> tuple[str, InlineKeyboardMarkup]:
    if screen == Screen.HOME:
        me = context.get('me', {})
        provider = me.get('provider', '—')
        video = '✅' if context.get('provider_video') else '❌'
        active = me.get('active_user_photo_id')
        stored = me.get('stored_user_photos_count', 0)
        product_ok = '✅' if context.get('product_file_id') else '❌'
        fit = context.get('fit_pref') or '—'
        ms = '✅' if context.get('measurements_json') else '—'
        can_generate = bool(context.get('product_file_id') and active)
        text = (
            '🧪 TryOnLab • Dashboard\n\n'
            f'🧠 Provider: {provider} (video {video})\n'
            f'👤 User photo: {"✅" if active else "❌"} active ({active or "—"}) | stored: {stored}\n'
            f'🧥 Product photo: {product_ok} 1/1\n'
            f'🎯 Fit: {fit}\n'
            f'📏 Measurements: {ms}\n'
            f'🧾 Last image job: {context.get("last_image_status", "—")} | last video: {context.get("last_video_status", "—")}\n\n'
            f'Generate: {"available ✅" if can_generate else "disabled ❌"}'
        )
        return text, home_keyboard(can_generate=can_generate)

    if screen == Screen.PRODUCT:
        ok = '✅ 1/1' if context.get('product_file_id') else '❌ 0/1'
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='🗑️ Очистить товар', callback_data='product:clear'), InlineKeyboardButton(text='🔁 Заменить', callback_data='nav:product')],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
            ]
        )
        return f'🧥 Товар • Загрузка\n\nПришли 1 фото товара в этот чат.\n\nТекущий статус: {ok}', kb

    if screen == Screen.USER_PHOTO_MENU:
        me = context.get('me', {})
        text = (
            '👤 Моё фото\n\n'
            f'Active: {me.get("active_user_photo_id") or "—"}\n'
            f'Stored: {me.get("stored_user_photos_count", 0)}\n\n'
            'Выбери сохранённое или загрузи новое.'
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='✅ Выбрать из сохранённых', callback_data='nav:user_photo_list'), InlineKeyboardButton(text='⬆️ Загрузить новое', callback_data='nav:user_photo_upload')],
                [InlineKeyboardButton(text='🗑️ Удалить active', callback_data='userphoto:delete_active'), InlineKeyboardButton(text='🧨 Удалить все', callback_data='userphoto:delete_all')],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
            ]
        )
        return text, kb

    if screen == Screen.USER_PHOTO_LIST:
        items = context.get('photo_items', [])
        active = context.get('me', {}).get('active_user_photo_id')
        rows = []
        current_row = []
        for item in items:
            label = f'#{item["id"]}{" ✅" if item["id"] == active else ""}'
            current_row.append(InlineKeyboardButton(text=label, callback_data=f'userphoto:select:{item["id"]}'))
            if len(current_row) == 3:
                rows.append(current_row)
                current_row = []
        if current_row:
            rows.append(current_row)
        rows.append([InlineKeyboardButton(text='⬅️', callback_data='photos:prev'), InlineKeyboardButton(text='➡️', callback_data='photos:next')])
        rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:userphoto')])
        return '👤 Моё фото • Список', InlineKeyboardMarkup(inline_keyboard=rows)

    if screen == Screen.USER_PHOTO_UPLOAD:
        return (
            '👤 Моё фото • Загрузка\n\nПришли фото человека.\nПосле успеха я удалю сообщение с фото (best-effort).',
            back_keyboard('userphoto'),
        )

    if screen == Screen.FIT:
        fit = context.get('fit_pref')
        def mark(v: str) -> str:
            return f'{v.title()} {"✅" if fit == v else ""}'.strip()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=mark('slim'), callback_data='fit:slim'), InlineKeyboardButton(text=mark('regular'), callback_data='fit:regular'), InlineKeyboardButton(text=mark('oversize'), callback_data='fit:oversize')],
            [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
        ])
        return '🎯 Посадка (fit)\n\nВыбери посадку:', kb

    if screen == Screen.MEASUREMENTS:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✍️ Ввести', callback_data='measure:input'), InlineKeyboardButton(text='⛔ Пропустить', callback_data='measure:skip')],
            [InlineKeyboardButton(text='🗑️ Очистить', callback_data='measure:clear')],
            [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
        ])
        return '📏 Параметры (optional)\n\nФормат: chest=92, waist=74, hips=98, height_cm=176', kb

    if screen == Screen.GENERATE:
        progress = context.get('progress', 0)
        bar_full = max(0, min(10, progress // 10))
        bar = '█' * bar_full + '░' * (10 - bar_full)
        rows = [[InlineKeyboardButton(text='🧾 История', callback_data='nav:history'), InlineKeyboardButton(text='⚙️ Настройки', callback_data='nav:settings')]]
        if context.get('job_status') == 'done':
            rows.insert(0, [InlineKeyboardButton(text='🔁 Retry', callback_data='gen:retry'), InlineKeyboardButton(text='🎬 Видео', callback_data='nav:video')])
        rows.append([InlineKeyboardButton(text='⬅️ Dashboard', callback_data='nav:home')])
        text = f'⚡ Генерация\n\nStatus: {context.get("job_status", "queued")} {progress}%\n[{bar}]'
        return text, InlineKeyboardMarkup(inline_keyboard=rows)

    if screen == Screen.VIDEO_MENU:
        rows = [[InlineKeyboardButton(text=str(i), callback_data=f'video:{i}') for i in range(1, 6)], [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:generate')]]
        return '🎬 Видео • Presets', InlineKeyboardMarkup(inline_keyboard=rows)

    if screen == Screen.SETTINGS:
        me = context.get('me', {})
        text = f'⚙️ Настройки\n\n🧠 Provider: {me.get("provider", "—")}\n📦 Storage: {context.get("storage_backend", "—")}\n🧹 Retention jobs: {context.get("retention_hours", "—")}h'
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🧠 Provider', callback_data='nav:provider')],
            [InlineKeyboardButton(text='🗑️ Удалить мои данные', callback_data='settings:purge')],
            [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
        ])
        return text, kb

    if screen == Screen.PROVIDER:
        rows = [[InlineKeyboardButton(text=f'{"✅ " if p["current"] else ""}{p["name"]}', callback_data=f'provider:{p["name"]}') for p in context.get('providers', [])]]
        rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:settings')])
        return '🧠 Провайдер', InlineKeyboardMarkup(inline_keyboard=rows)

    if screen == Screen.PURGE_CONFIRM:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='✅ Да', callback_data='purge:yes'), InlineKeyboardButton(text='❌ Нет', callback_data='purge:no')]
            ]
        )
        return 'Точно удалить все данные? Это удалит сохранённые фото и историю задач.', kb

    if screen == Screen.HISTORY:
        items = context.get('history_items', [])
        lines = ['🧾 История', '']
        rows = []
        row = []
        for item in items:
            lines.append(f'#{item["job_id"][:8]} {item["type"]} {item["status"]} ({item["provider"]})')
            row.append(InlineKeyboardButton(text=item['job_id'][:4], callback_data=f'history:job:{item["job_id"]}'))
            if len(row) == 3:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([InlineKeyboardButton(text='⬅️', callback_data='history:prev'), InlineKeyboardButton(text='➡️', callback_data='history:next')])
        rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')])
        return '\n'.join(lines), InlineKeyboardMarkup(inline_keyboard=rows)

    return 'Unknown screen', back_keyboard('home')
