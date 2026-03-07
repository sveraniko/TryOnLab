from __future__ import annotations

from enum import StrEnum

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.keyboards import back_keyboard, home_keyboard


class Screen(StrEnum):
    HOME = 'home'
    PRODUCT = 'product'
    PRODUCT_SCOPE = 'product_scope'
    USER_PHOTO_MENU = 'user_photo_menu'
    USER_PHOTO_LIST = 'user_photo_list'
    USER_PHOTO_UPLOAD = 'user_photo_upload'
    FIT = 'fit'
    MODE = 'mode'
    SCOPE = 'scope'
    MEASUREMENTS = 'measurements'
    GENERATE = 'generate'
    VIDEO_MENU = 'video_menu'
    SETTINGS = 'settings'
    PROVIDER = 'provider'
    HISTORY = 'history'
    PURGE_CONFIRM = 'purge_confirm'
    LOOK_HOME = 'look_home'
    LOOK_ADD_ITEM = 'look_add_item'
    LOOK_ITEM_SCOPE_SELECT = 'look_item_scope_select'
    LOOK_CONFIRM_APPLY = 'look_confirm_apply'
    LOOK_MONITOR = 'look_monitor'
    LOOK_VIDEO_MENU = 'look_video_menu'


def render(screen: Screen, context: dict) -> tuple[str, InlineKeyboardMarkup]:
    if screen == Screen.HOME:
        me = context.get('me', {})
        provider = me.get('provider', '—')
        video = '✅' if context.get('provider_video') else '❌'
        active = me.get('active_user_photo_id')
        stored = me.get('stored_user_photos_count', 0)
        product_clean_ok = bool(context.get('product_clean_file_id') or context.get('product_file_id'))
        product_fit_ok = bool(context.get('product_fit_file_id'))
        fit = context.get('fit_pref') or '—'
        ms = '✅' if context.get('measurements_json') else '—'
        mode = (context.get('gen_mode') or 'strict').title()
        mode_icon = '🔒' if (context.get('gen_mode') or 'strict') == 'strict' else '✨'
        scope = (context.get('edit_scope') or 'full').title()
        can_generate = bool((product_clean_ok or product_fit_ok) and active)
        last_image_status = context.get('last_image_status', '—')
        has_last_image = last_image_status == 'done' and bool(context.get('last_image_job_id'))
        lower_hint = '\n💡 Lower + Patch = experimental' if (context.get('edit_scope') or '').lower() == 'lower' else ''
        text = (
            '🧪 TryOnLab • Dashboard\n\n'
            f'🧠 Provider: {provider} (video {video})\n'
            f'👤 User photo: {"✅" if active else "❌"} active ({active or "—"}) | stored: {stored}\n'
            f'🧥 Product refs: clean {"✅" if product_clean_ok else "❌"} | fit {"✅" if product_fit_ok else "❌"}\n'
            f'🧩 Mode: {mode} {mode_icon}\n'
            f'🎛️ Scope: {scope}\n'
            f'🎯 Fit: {fit}\n'
            f'📏 Measurements: {ms}\n'
            f'🧾 Last image job: {last_image_status} | last video: {context.get("last_video_status", "—")}\n\n'
            f'Generate: {"available ✅" if can_generate else "disabled ❌"}'
            f'{lower_hint}'
        )
        return text, home_keyboard(can_generate=can_generate, has_last_image=has_last_image)

    if screen == Screen.PRODUCT:
        clean_ok = '✅' if (context.get('product_clean_file_id') or context.get('product_file_id')) else '❌'
        fit_ok = '✅' if context.get('product_fit_file_id') else '❌'
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='🧩 Clean ref', callback_data='product:upload_clean')],
                [InlineKeyboardButton(text='👗 Fit ref', callback_data='product:upload_fit')],
                [InlineKeyboardButton(text='🗑️ Очистить всё', callback_data='product:clear')],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
            ]
        )
        return (
            '🧥 Товар • Референсы\n\n'
            '🧩 Clean ref = вещь отдельно.\n'
            '👗 Fit ref = вещь на модели / в образе.\n\n'
            f'Clean ref: {clean_ok}\n'
            f'Fit ref: {fit_ok}\n\n'
            '💡 Для сложного низа fit ref часто даёт лучший силуэт.',
            kb,
        )

    if screen == Screen.PRODUCT_SCOPE:
        current = (context.get('edit_scope') or 'full').lower()

        def label(name: str) -> str:
            return f'{name.title()} {"✅" if current == name else ""}'.strip()

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=label('upper'), callback_data='scope:set:upper'), InlineKeyboardButton(text=label('lower'), callback_data='scope:set:lower')],
                [InlineKeyboardButton(text=label('feet'), callback_data='scope:set:feet'), InlineKeyboardButton(text=label('full'), callback_data='scope:set:full')],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
            ]
        )
        return '🧥 Для чего этот товар?\n\nВыбери зону редактирования для этого товара:', kb

    if screen == Screen.MODE:
        mode = (context.get('gen_mode') or 'strict').lower()
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f'Strict 🔒{" ✅" if mode == "strict" else ""}', callback_data='mode:set:strict')],
                [InlineKeyboardButton(text=f'Creative ✨{" ✅" if mode == "creative" else ""}', callback_data='mode:set:creative')],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
            ]
        )
        return '🧩 Режим генерации\n\nStrict: меняем только выбранную зону.\nCreative: можно стилизовать образ вокруг вещи.', kb

    if screen == Screen.SCOPE:
        current = (context.get('edit_scope') or 'full').lower()

        def label(name: str) -> str:
            return f'{name.title()} {"✅" if current == name else ""}'.strip()

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=label('upper'), callback_data='scope:set:upper'), InlineKeyboardButton(text=label('lower'), callback_data='scope:set:lower')],
                [InlineKeyboardButton(text=label('feet'), callback_data='scope:set:feet'), InlineKeyboardButton(text=label('full'), callback_data='scope:set:full')],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
            ]
        )
        hint = '\n\n💡 Lower + Patch = experimental.' if current == 'lower' else ''
        return f'🎛️ Зона редактирования\n\nВыбери область: Upper / Lower / Feet / Full.{hint}', kb

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
                [InlineKeyboardButton(text='📚 Выбрать из сохранённых', callback_data='nav:user_photo_list')],
                [InlineKeyboardButton(text='⬆️ Загрузить новое', callback_data='nav:user_photo_upload')],
                [InlineKeyboardButton(text='🗑️ Удалить активное', callback_data='userphoto:delete_active')],
                [InlineKeyboardButton(text='🧹 Удалить все', callback_data='userphoto:delete_all')],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
            ]
        )
        return text, kb

    if screen == Screen.USER_PHOTO_LIST:
        items = context.get('photo_items', [])
        active = context.get('me', {}).get('active_user_photo_id')
        rows = []
        item_patch_mode = context.get('look_item_patch_mode')
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

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=mark('slim'), callback_data='fit:slim'),
                    InlineKeyboardButton(text=mark('regular'), callback_data='fit:regular'),
                    InlineKeyboardButton(text=mark('oversize'), callback_data='fit:oversize'),
                ],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
            ]
        )
        return '🎯 Посадка (fit)\n\nВыбери посадку:', kb

    if screen == Screen.MEASUREMENTS:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='✍️ Ввести', callback_data='measure:input'), InlineKeyboardButton(text='⛔ Пропустить', callback_data='measure:skip')],
                [InlineKeyboardButton(text='🗑️ Очистить', callback_data='measure:clear')],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
            ]
        )
        return '📏 Параметры (optional)\n\nФормат: chest=92, waist=74, hips=98, height_cm=176', kb

    if screen == Screen.GENERATE:
        progress = context.get('progress', 0)
        monitor_error = context.get('monitor_error')
        bar_full = max(0, min(10, progress // 10))
        bar = '█' * bar_full + '░' * (10 - bar_full)
        rows = [[InlineKeyboardButton(text='🧾 История', callback_data='nav:history'), InlineKeyboardButton(text='⚙️ Настройки', callback_data='nav:settings')]]
        if context.get('job_status') == 'done':
            rows.insert(0, [InlineKeyboardButton(text='🔁 Retry', callback_data='gen:retry'), InlineKeyboardButton(text='🎬 Видео', callback_data='nav:video')])
        rows.append([InlineKeyboardButton(text='⬅️ Dashboard', callback_data='nav:home')])
        text = f'⚡ Генерация\n\nStatus: {context.get("job_status", "queued")} {progress}%\n[{bar}]'
        if monitor_error:
            text = f'{text}\n\n{monitor_error}'
        return text, InlineKeyboardMarkup(inline_keyboard=rows)

    if screen == Screen.VIDEO_MENU:
        rows = [[InlineKeyboardButton(text=str(i), callback_data=f'video:{i}') for i in range(1, 6)], [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:generate')]]
        return '🎬 Видео • Presets', InlineKeyboardMarkup(inline_keyboard=rows)

    if screen == Screen.SETTINGS:
        me = context.get('me', {})
        text = f'⚙️ Настройки\n\n🧠 Provider: {me.get("provider", "—")}\n📦 Storage: {context.get("storage_backend", "—")}\n🧹 Retention jobs: {context.get("retention_hours", "—")}h'
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='🧠 Provider', callback_data='nav:provider')],
                [InlineKeyboardButton(text='🗑️ Удалить мои данные', callback_data='settings:purge')],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')],
            ]
        )
        return text, kb

    if screen == Screen.PROVIDER:
        rows = [[InlineKeyboardButton(text=f'{"✅ " if p["current"] else ""}{p["name"]}', callback_data=f'provider:{p["name"]}') for p in context.get('providers', [])]]
        rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:settings')])
        return '🧠 Провайдер', InlineKeyboardMarkup(inline_keyboard=rows)

    if screen == Screen.PURGE_CONFIRM:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Да', callback_data='purge:yes'), InlineKeyboardButton(text='❌ Нет', callback_data='purge:no')]])
        return 'Точно удалить все данные? Это удалит сохранённые фото и историю задач.', kb

    if screen == Screen.HISTORY:
        items = context.get('history_items', [])
        lines = ['🧾 История', '']
        rows = []
        item_patch_mode = context.get('look_item_patch_mode')
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

    if screen == Screen.LOOK_HOME:
        mode = (context.get('gen_mode') or 'strict').title()
        scope = (context.get('edit_scope') or 'full').title()
        steps = int(context.get('look_steps') or 0)
        has_base = bool(context.get('look_base_job_id'))
        look_active = bool(context.get('look_active'))
        patch_mode = bool(context.get('look_patch_mode', True))
        text = (
            '🧩 Конструктор лука\n\n'
            f'Look status: {"active ✅" if look_active else "—"}\n'
            f'Steps: {steps}\n'
            f'Base image: {"✅" if has_base else "❌"}\n'
            f'Patch mode: {"✅" if patch_mode else "❌"}\n'
            f'Mode/Scope: {mode} / {scope}\n'
            '💡 Lower item: patch experimental'
        )
        kb_rows = [[InlineKeyboardButton(text='🩹 Patch mode', callback_data='look:patch_toggle')], [InlineKeyboardButton(text='➕ Добавить предмет', callback_data='look:add_item')]]
        if steps > 0:
            kb_rows.append([InlineKeyboardButton(text='↩️ Undo', callback_data='look:undo')])
        kb_rows.append([InlineKeyboardButton(text='🧼 Сбросить лук', callback_data='look:reset')])
        if has_base:
            kb_rows.append([InlineKeyboardButton(text='🎬 Видео из текущего лука', callback_data='look:video_menu')])
        kb_rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='nav:home')])
        return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)

    if screen == Screen.LOOK_ADD_ITEM:
        has_clean = bool(context.get('look_item_clean_file_id') or context.get('look_item_product_file_id'))
        has_fit = bool(context.get('look_item_fit_file_id'))
        rows = [
            [InlineKeyboardButton(text='🧩 Clean ref', callback_data='look:item_upload_clean')],
            [InlineKeyboardButton(text='👗 Fit ref', callback_data='look:item_upload_fit')],
        ]
        if has_clean or has_fit:
            rows.append([InlineKeyboardButton(text='⚡ Продолжить', callback_data='look:item_continue')])
        rows.extend(
            [
                [InlineKeyboardButton(text='🗑️ Очистить item', callback_data='look:item_clear')],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='look:cancel_add')],
            ]
        )
        if context.get('product_clean_file_id') or context.get('product_file_id'):
            rows.insert(0, [InlineKeyboardButton(text='♻️ Взять Clean ref из PRODUCT', callback_data='look:use_session_product')])
        return (
            '🧩 Конструктор лука • Добавить предмет\n\n'
            f'Clean ref: {"✅" if has_clean else "❌"}\n'
            f'Fit ref: {"✅" if has_fit else "❌"}\n\n'
            'Загрузи clean, fit или оба.',
            InlineKeyboardMarkup(inline_keyboard=rows),
        )

    if screen == Screen.LOOK_ITEM_SCOPE_SELECT:
        current = (context.get('look_item_scope') or '').lower()

        def s_label(name: str) -> str:
            return f'{name.title()} {"✅" if current == name else ""}'.strip()

        rows = [
            [InlineKeyboardButton(text=s_label('upper'), callback_data='look:item_scope:upper'), InlineKeyboardButton(text=s_label('lower'), callback_data='look:item_scope:lower')],
            [InlineKeyboardButton(text=s_label('feet'), callback_data='look:item_scope:feet'), InlineKeyboardButton(text=s_label('full'), callback_data='look:item_scope:full')],
            [InlineKeyboardButton(text='⬅️ Назад', callback_data='look:back_add')],
        ]
        hint = ''
        if current == 'lower':
            hint = '\n\n💡 Patch mode for lower garments is experimental.'
        elif (context.get('gen_mode') or 'strict') == 'strict' and current == 'upper':
            hint = '\n\n💡 Strict + Upper = безопасно.'
        return f'🧩 Для чего этот товар?\n\nВыбери, куда относится предмет, чтобы правильно надеть{hint}', InlineKeyboardMarkup(inline_keyboard=rows)

    if screen == Screen.LOOK_CONFIRM_APPLY:
        mode = (context.get('gen_mode') or 'strict').title()
        scope = (context.get('look_item_scope') or '—').title()
        provider = context.get('me', {}).get('provider', '—')
        steps = int(context.get('look_steps') or 0)
        has_item = bool(context.get('look_item_clean_file_id') or context.get('look_item_product_file_id') or context.get('look_item_fit_file_id'))
        rows = []
        item_patch_mode = context.get('look_item_patch_mode')
        if has_item and scope != '—':
            rows.append([InlineKeyboardButton(text='⚡ Применить', callback_data='look:apply')])
        rows.append([InlineKeyboardButton(text='🔁 Заменить предмет', callback_data='look:replace_item')])
        rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='look:home')])
        return (
            '🧩 Применить шаг\n\n'
            'Готов применить предмет к текущей базе лука?\n'
            f'Mode: {mode}\n'
            f'Scope: {scope}\n'
            f'Steps: {steps}\n'
            f'Provider: {provider}\n'
            f'Patch: {"ON ✅" if item_patch_mode else "OFF ❌"}',
            InlineKeyboardMarkup(inline_keyboard=rows),
        )

    if screen == Screen.LOOK_MONITOR:
        progress = context.get('progress', 0)
        bar_full = max(0, min(10, progress // 10))
        bar = '█' * bar_full + '░' * (10 - bar_full)
        job_id = context.get('polling_job_id') or '—'
        status = context.get('job_status', 'queued')
        rows = []
        item_patch_mode = context.get('look_item_patch_mode')
        if status != 'running' and status != 'queued':
            rows.append([InlineKeyboardButton(text='⬅️ В LOOK_HOME', callback_data='look:home')])
        return f'🧩 Конструктор лука • Генерация\n\njob_id: {job_id}\nstatus: {status} {progress}%\n[{bar}]', InlineKeyboardMarkup(inline_keyboard=rows)

    if screen == Screen.LOOK_VIDEO_MENU:
        rows = [[InlineKeyboardButton(text=str(i), callback_data=f'look:video:{i}') for i in range(1, 6)], [InlineKeyboardButton(text='⬅️ Назад', callback_data='look:home')]]
        return '🎬 Видео из текущего лука • Presets', InlineKeyboardMarkup(inline_keyboard=rows)

    return 'Unknown screen', back_keyboard('home')
