from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, ForceReply, Message
from redis.asyncio import Redis

from app.bot.api.client import ApiClient
from app.bot.fsm.states import WizardStates
from app.bot.services.look_builder import (
    choose_force_lock,
    choose_person_input,
    new_look_step,
    push_look_step,
    reset_look,
    resolve_person_image_bytes,
    undo_look_step,
)
from app.bot.services.parser import parse_measurements_text
from app.bot.services.provider_cache import is_provider_cache_fresh
from app.bot.ui.panel import ensure_panel, safe_edit_panel, try_delete
from app.bot.ui.screens import Screen, render
from app.core.config import Settings

router = Router()


async def _client(message: Message | CallbackQuery, settings: Settings) -> ApiClient:
    user = message.from_user
    if isinstance(message, CallbackQuery):
        chat_id = message.message.chat.id
    else:
        chat_id = message.chat.id
    return ApiClient(settings.api_base_url, tg_user_id=user.id, tg_chat_id=chat_id)


async def _render_current(bot: Bot, state: FSMContext, chat_id: int, api: ApiClient, settings: Settings) -> None:
    data = await state.get_data()
    me = await api.get_me()
    panel_message_id = me.get('panel_message_id')
    if panel_message_id is None:
        panel_message_id = await ensure_panel(
            bot,
            chat_id=chat_id,
            panel_message_id=None,
            fallback_text='TryOnLab loading...',
        )
        me = await api.patch_me({'panel_message_id': panel_message_id})
    providers = await _get_cached_providers(state, api, settings)
    pmeta = next((p for p in providers if p['name'] == me['provider']), None)
    screen = Screen(data.get('screen', Screen.HOME.value))
    ctx = {
        **data,
        'me': me,
        'provider_video': bool(pmeta and pmeta['video']),
        'storage_backend': settings.storage_backend,
        'retention_hours': settings.retention_hours,
    }
    text, kb = render(screen, ctx)
    await safe_edit_panel(bot, chat_id=chat_id, panel_message_id=me['panel_message_id'], text=text, keyboard=kb)


async def _switch_screen(bot: Bot, state: FSMContext, chat_id: int, api: ApiClient, settings: Settings, screen: Screen) -> None:
    await state.update_data(screen=screen.value)
    await _render_current(bot, state, chat_id, api, settings)


async def _get_cached_providers(state: FSMContext, api: ApiClient, settings: Settings) -> list[dict]:
    data = await state.get_data()
    cached = data.get('providers_meta_cache')
    ts = float(data.get('providers_meta_cached_at', 0) or 0)
    if cached and is_provider_cache_fresh(ts, settings.bot_provider_meta_cache_ttl_seconds):
        return cached

    providers = await api.list_providers()
    await state.update_data(providers_meta_cache=providers, providers_meta_cached_at=time.time())
    return providers


async def _consume_rate_limit(*, settings: Settings, tg_user_id: int, action: str, limit: int) -> bool:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    key = f'rl:user:{tg_user_id}:{action}'
    try:
        value = await redis.incr(key)
        if value == 1:
            await redis.expire(key, 3600)
        return value <= limit
    finally:
        await redis.aclose()


async def _apply_look_update(state: FSMContext, updater) -> None:
    data = await state.get_data()
    next_data = updater(data)
    await state.update_data(**next_data)


async def _read_result_bytes(url: str) -> bytes:
    if url.startswith('file://'):
        return Path(url[7:]).read_bytes()
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content


@router.message(Command('start'))
async def start_handler(message: Message, state: FSMContext, bot: Bot, settings: Settings) -> None:
    api = await _client(message, settings)
    me = await api.get_me()
    panel_id = await ensure_panel(bot, chat_id=message.chat.id, panel_message_id=me.get('panel_message_id'), fallback_text='TryOnLab loading...')
    if me.get('panel_message_id') != panel_id:
        await api.patch_me({'panel_message_id': panel_id})
    await state.update_data(screen=Screen.HOME.value, gen_mode='strict', edit_scope='full', look_active=False, look_steps=0, look_stack=[], look_patch_mode=True, look_base_job_id=None)
    await _render_current(bot, state, message.chat.id, api, settings)


@router.callback_query(F.data.startswith('nav:'))
async def nav_handler(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    api = await _client(query, settings)
    target = query.data.split(':', 1)[1]
    mapping = {
        'home': Screen.HOME,
        'product': Screen.PRODUCT,
        'userphoto': Screen.USER_PHOTO_MENU,
        'user_photo_list': Screen.USER_PHOTO_LIST,
        'user_photo_upload': Screen.USER_PHOTO_UPLOAD,
        'fit': Screen.FIT,
        'mode': Screen.MODE,
        'scope': Screen.SCOPE,
        'product_scope': Screen.PRODUCT_SCOPE,
        'measurements': Screen.MEASUREMENTS,
        'generate': Screen.GENERATE,
        'video': Screen.VIDEO_MENU,
        'settings': Screen.SETTINGS,
        'provider': Screen.PROVIDER,
        'history': Screen.HISTORY,
        'look_home': Screen.LOOK_HOME,
    }
    screen = mapping.get(target, Screen.HOME)
    if screen == Screen.PRODUCT:
        await state.set_state(WizardStates.await_product_photo)
    elif screen == Screen.USER_PHOTO_UPLOAD:
        await state.set_state(WizardStates.await_user_photo_upload)
    elif screen == Screen.MEASUREMENTS:
        await state.set_state(None)
    elif screen == Screen.LOOK_HOME:
        await state.set_state(None)
        data = await state.get_data()
        if 'look_stack' not in data:
            await state.update_data(look_active=False, look_steps=0, look_stack=[], look_patch_mode=True, look_base_job_id=None)
    else:
        await state.set_state(None)

    if screen == Screen.USER_PHOTO_LIST:
        await state.update_data(photos_offset=0)
        photos = await api.list_photos(offset=0, limit=9)
        await state.update_data(photo_items=photos['items'])
    if screen == Screen.HISTORY:
        jobs = await api.list_jobs(offset=(await state.get_data()).get('history_offset', 0), limit=10)
        await state.update_data(history_items=jobs['items'])
    if screen == Screen.PROVIDER:
        me = await api.get_me()
        providers = await _get_cached_providers(state, api, settings)
        await state.update_data(providers=[{'name': p['name'], 'current': p['name'] == me['provider']} for p in providers])

    await _switch_screen(bot, state, query.message.chat.id, api, settings, screen)


@router.callback_query(F.data == 'product:clear')
async def clear_product(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    await state.update_data(product_file_id=None)
    api = await _client(query, settings)
    await _switch_screen(bot, state, query.message.chat.id, api, settings, Screen.PRODUCT)


@router.message(WizardStates.await_product_photo, F.photo)
async def on_product_photo(message: Message, state: FSMContext, bot: Bot, settings: Settings) -> None:
    file_id = message.photo[-1].file_id
    await state.update_data(product_file_id=file_id, screen=Screen.PRODUCT_SCOPE.value)
    await try_delete(bot, message.chat.id, message.message_id)
    api = await _client(message, settings)
    await _render_current(bot, state, message.chat.id, api, settings)


@router.message(WizardStates.await_look_item_photo, F.photo)
async def on_look_item_photo(message: Message, state: FSMContext, bot: Bot, settings: Settings) -> None:
    file_id = message.photo[-1].file_id
    await state.update_data(look_item_product_file_id=file_id, look_item_scope=None, look_active=True, screen=Screen.LOOK_ITEM_SCOPE_SELECT.value)
    await try_delete(bot, message.chat.id, message.message_id)
    api = await _client(message, settings)
    await _render_current(bot, state, message.chat.id, api, settings)


@router.message(WizardStates.await_user_photo_upload, F.photo)
async def on_user_photo(message: Message, state: FSMContext, bot: Bot, settings: Settings) -> None:
    api = await _client(message, settings)
    file = await bot.get_file(message.photo[-1].file_id)
    data = await bot.download_file(file.file_path)
    payload = data.read()
    await api.upload_user_photo(payload)
    await try_delete(bot, message.chat.id, message.message_id)
    await state.update_data(screen=Screen.USER_PHOTO_MENU.value)
    await _render_current(bot, state, message.chat.id, api, settings)


@router.callback_query(F.data.startswith('userphoto:select:'))
async def select_photo(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    photo_id = int(query.data.rsplit(':', 1)[1])
    api = await _client(query, settings)
    await api.activate_photo(photo_id)
    await _switch_screen(bot, state, query.message.chat.id, api, settings, Screen.USER_PHOTO_MENU)


@router.callback_query(F.data == 'userphoto:delete_active')
async def delete_active(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    api = await _client(query, settings)
    me = await api.get_me()
    if me.get('active_user_photo_id'):
        await api.delete_photo(me['active_user_photo_id'])
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'userphoto:delete_all')
async def delete_all(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    api = await _client(query, settings)
    await api.delete_all_photos()
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data.startswith('mode:set:'))
async def set_mode(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    mode = query.data.rsplit(':', 1)[1]
    if mode not in {'strict', 'creative'}:
        return
    await state.update_data(gen_mode=mode, screen=Screen.HOME.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data.startswith('scope:set:'))
async def set_scope(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    scope = query.data.rsplit(':', 1)[1]
    if scope not in {'upper', 'lower', 'feet', 'full'}:
        return
    current = await state.get_data()
    target_screen = Screen.HOME.value
    if current.get('screen') in {Screen.SCOPE.value, Screen.PRODUCT_SCOPE.value}:
        target_screen = current.get('screen')
    await state.update_data(edit_scope=scope, screen=target_screen)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data.startswith('fit:'))
async def set_fit(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    fit = query.data.split(':', 1)[1]
    await state.update_data(fit_pref=fit, screen=Screen.HOME.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'measure:input')
async def measure_input(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer('Отправь текст с параметрами')
    await state.set_state(WizardStates.await_measurements_text)
    await query.message.answer(
        'Введи параметры в формате: chest=92, waist=74, hips=98, height_cm=176',
        reply_markup=ForceReply(selective=True),
    )


@router.callback_query(F.data == 'measure:skip')
async def measure_skip(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    await state.update_data(measurements_json=None, screen=Screen.HOME.value)
    await state.set_state(None)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'measure:clear')
async def measure_clear(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    await state.update_data(measurements_json=None)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.message(WizardStates.await_measurements_text, F.text)
async def on_measurements(message: Message, state: FSMContext, bot: Bot, settings: Settings) -> None:
    api = await _client(message, settings)
    try:
        parsed = parse_measurements_text(message.text)
    except Exception as exc:
        await message.answer(f'❌ {exc}')
        return
    await state.update_data(measurements_json=parsed, screen=Screen.HOME.value)
    await state.set_state(None)
    await _render_current(bot, state, message.chat.id, api, settings)


@router.callback_query(F.data.startswith('photos:'))
async def photos_pagination(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    api = await _client(query, settings)
    offset = (await state.get_data()).get('photos_offset', 0)
    if query.data == 'photos:next':
        offset += 9
    elif query.data == 'photos:prev':
        offset = max(0, offset - 9)
    photos = await api.list_photos(offset=offset, limit=9)
    await state.update_data(photos_offset=offset, photo_items=photos['items'], screen=Screen.USER_PHOTO_LIST.value)
    await _render_current(bot, state, query.message.chat.id, api, settings)


async def _monitor_job(bot: Bot, state: FSMContext, chat_id: int, api: ApiClient, settings: Settings, job_id: str, media_type: str, final_screen: Screen = Screen.HOME) -> None:
    monitor_screen = Screen.GENERATE if final_screen == Screen.HOME else final_screen
    await state.update_data(screen=monitor_screen.value)
    started_at = time.monotonic()
    poll_interval = max(1, settings.bot_monitor_base_interval_seconds)
    max_interval = max(poll_interval, settings.bot_monitor_max_interval_seconds)
    timeout_seconds = max(1, settings.bot_monitor_timeout_seconds)

    while True:
        if time.monotonic() - started_at > timeout_seconds:
            status_key = 'last_image_status' if media_type == 'image' else 'last_video_status'
            await state.update_data(
                **{status_key: 'failed_timeout'},
                job_status='failed_timeout',
                progress=0,
                monitor_error='⏱ Генерация превысила время ожидания. Проверь историю или попробуй позже.',
            )
            await _render_current(bot, state, chat_id, api, settings)
            break

        try:
            data = await api.get_job(job_id)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
            poll_interval = min(max_interval, poll_interval + settings.bot_monitor_base_interval_seconds)
            await asyncio.sleep(poll_interval)
            continue
        except Exception:
            status_key = 'last_image_status' if media_type == 'image' else 'last_video_status'
            await state.update_data(
                **{status_key: 'failed_api'},
                job_status='failed_api',
                progress=0,
                monitor_error='❌ Ошибка связи с сервисом генерации. Попробуй позже.',
            )
            await _render_current(bot, state, chat_id, api, settings)
            break

        poll_interval = max(1, settings.bot_monitor_base_interval_seconds)
        await state.update_data(job_status=data['status'], progress=data.get('progress') or 0)
        await _render_current(bot, state, chat_id, api, settings)
        if data['status'] in {'done', 'failed'}:
            if media_type == 'image':
                await state.update_data(last_image_status=data['status'])
            if media_type == 'video':
                await state.update_data(last_video_status=data['status'])
            if data['status'] == 'done':
                if media_type == 'image' and data.get('result_image_url'):
                    content = await _read_result_bytes(data['result_image_url'])
                    await bot.send_photo(chat_id, photo=BufferedInputFile(content, filename='result.jpg'))
                if media_type == 'video' and data.get('result_video_url'):
                    content = await _read_result_bytes(data['result_video_url'])
                    await bot.send_video(chat_id, video=BufferedInputFile(content, filename='result.mp4'))
            break
        await asyncio.sleep(poll_interval)
    await state.update_data(screen=final_screen.value, monitor_error=None)
    await _render_current(bot, state, chat_id, api, settings)


@router.callback_query(F.data == 'gen:image')
async def generate_image(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    api = await _client(query, settings)
    data = await state.get_data()
    me = await api.get_me()
    if not data.get('product_file_id') or not me.get('active_user_photo_id'):
        await query.answer('Нужны product и active user photo', show_alert=True)
        return
    if not await _consume_rate_limit(
        settings=settings,
        tg_user_id=query.from_user.id,
        action='image',
        limit=settings.bot_rate_limit_image_per_hour,
    ):
        await query.answer('Лимит генераций изображений исчерпан (1ч)', show_alert=True)
        return

    file = await bot.get_file(data['product_file_id'])
    stream = await bot.download_file(file.file_path)
    job = await api.create_job(
        product=stream.read(),
        user_photo_id=me['active_user_photo_id'],
        fit_pref=data.get('fit_pref'),
        measurements_json=data.get('measurements_json'),
        mode=data.get('gen_mode', 'strict'),
        scope=data.get('edit_scope', 'full'),
        force_lock=False,
    )
    await state.update_data(last_image_job_id=job['job_id'], polling_job_id=job['job_id'])
    await _monitor_job(bot, state, query.message.chat.id, api, settings, job['job_id'], 'image')


@router.callback_query(F.data == 'gen:retry')
async def retry_image(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    api = await _client(query, settings)
    job_id = (await state.get_data()).get('last_image_job_id')
    if not job_id:
        return
    if not await _consume_rate_limit(
        settings=settings,
        tg_user_id=query.from_user.id,
        action='retry',
        limit=settings.bot_rate_limit_retry_per_hour,
    ):
        await query.answer('Лимит retry исчерпан (1ч)', show_alert=True)
        return
    retry = await api.retry_job(job_id)
    await _monitor_job(bot, state, query.message.chat.id, api, settings, retry['job_id'], 'image')


@router.callback_query(F.data.startswith('video:'))
async def generate_video(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    preset = int(query.data.split(':', 1)[1])
    api = await _client(query, settings)
    job_id = (await state.get_data()).get('last_image_job_id')
    if not job_id:
        return
    if not await _consume_rate_limit(
        settings=settings,
        tg_user_id=query.from_user.id,
        action='video',
        limit=settings.bot_rate_limit_video_per_hour,
    ):
        await query.answer('Лимит генераций видео исчерпан (1ч)', show_alert=True)
        return
    video_job = await api.create_video(job_id, preset)
    await state.update_data(last_video_job_id=video_job['video_job_id'])
    await _monitor_job(bot, state, query.message.chat.id, api, settings, video_job['video_job_id'], 'video')


@router.callback_query(F.data == 'look:add_item')
async def look_add_item(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    await state.set_state(WizardStates.await_look_item_photo)
    await state.update_data(screen=Screen.LOOK_ADD_ITEM.value, look_active=True)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'look:cancel_add')
async def look_cancel_add(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    await state.set_state(None)
    await state.update_data(screen=Screen.LOOK_HOME.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'look:use_session_product')
async def look_use_session_product(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    data = await state.get_data()
    if not data.get('product_file_id'):
        return
    await state.set_state(None)
    await state.update_data(look_item_product_file_id=data['product_file_id'], look_item_scope=None, look_active=True, screen=Screen.LOOK_ITEM_SCOPE_SELECT.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'look:back_add')
async def look_back_add(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    await state.set_state(WizardStates.await_look_item_photo)
    await state.update_data(screen=Screen.LOOK_ADD_ITEM.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data.startswith('look:item_scope:'))
async def look_item_scope(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    scope = query.data.rsplit(':', 1)[1]
    if scope not in {'upper', 'lower', 'feet', 'full'}:
        return
    await state.set_state(None)
    await state.update_data(look_item_scope=scope, screen=Screen.LOOK_CONFIRM_APPLY.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'look:replace_item')
async def look_replace_item(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    await state.set_state(WizardStates.await_look_item_photo)
    await state.update_data(screen=Screen.LOOK_ADD_ITEM.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'look:home')
async def look_home(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    await state.set_state(None)
    data = await state.get_data()
    await state.update_data(screen=Screen.LOOK_HOME.value, look_active=True, look_patch_mode=bool(data.get('look_patch_mode', True)))
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)




@router.callback_query(F.data == 'look:patch_toggle')
async def look_patch_toggle(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    data = await state.get_data()
    current = bool(data.get('look_patch_mode', True))
    await state.update_data(look_patch_mode=not current, screen=Screen.LOOK_HOME.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)
@router.callback_query(F.data == 'look:apply')
async def look_apply(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    api = await _client(query, settings)
    data = await state.get_data()
    me = await api.get_me()
    item_file_id = data.get('look_item_product_file_id')
    item_scope = data.get('look_item_scope')
    if not item_file_id or not item_scope:
        await query.answer('Сначала добавь предмет и выбери Scope', show_alert=True)
        return

    selected_person = choose_person_input(
        look_base_job_id=data.get('look_base_job_id'),
        active_user_photo_id=me.get('active_user_photo_id'),
    )
    if selected_person['base_job_id'] is None and selected_person['user_photo_id'] is None:
        await query.answer('Нужно active user photo для первого шага', show_alert=True)
        return

    if not await _consume_rate_limit(
        settings=settings,
        tg_user_id=query.from_user.id,
        action='image',
        limit=settings.bot_rate_limit_image_per_hour,
    ):
        await query.answer('Лимит генераций изображений исчерпан (1ч)', show_alert=True)
        return

    prod_file = await bot.get_file(item_file_id)
    prod_stream = await bot.download_file(prod_file.file_path)
    product_bytes = prod_stream.read()

    person_image_bytes = await resolve_person_image_bytes(
        api_client=api,
        base_job_id=selected_person['base_job_id'],
        read_bytes=_read_result_bytes,
    )

    job = await api.create_job(
        product=product_bytes,
        person_image=person_image_bytes,
        user_photo_id=selected_person['user_photo_id'],
        fit_pref=data.get('fit_pref'),
        measurements_json=data.get('measurements_json'),
        mode=data.get('gen_mode', 'strict'),
        scope=item_scope,
        force_lock=choose_force_lock(data.get('look_patch_mode')),
    )
    await state.update_data(polling_job_id=job['job_id'], job_status='queued', progress=0, screen=Screen.LOOK_MONITOR.value)
    await _render_current(bot, state, query.message.chat.id, api, settings)

    while True:
        status = await api.get_job(job['job_id'])
        await state.update_data(job_status=status['status'], progress=status.get('progress') or 0)
        await _render_current(bot, state, query.message.chat.id, api, settings)
        if status['status'] in {'done', 'failed'}:
            if status['status'] == 'done' and status.get('result_image_url'):
                content = await _read_result_bytes(status['result_image_url'])
                await bot.send_photo(query.message.chat.id, photo=BufferedInputFile(content, filename='look_result.jpg'))
                step = new_look_step(
                    job_id=job['job_id'],
                    result_image_url=status['result_image_url'],
                    mode=data.get('gen_mode', 'strict'),
                    scope=item_scope,
                    provider=me.get('provider', '—'),
                )
                await _apply_look_update(state, lambda d: push_look_step(d, step))
                await state.update_data(last_image_job_id=job['job_id'], last_image_status='done')
            break
        await asyncio.sleep(2)

    await state.update_data(screen=Screen.LOOK_HOME.value)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'look:undo')
async def look_undo(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    await _apply_look_update(state, undo_look_step)
    await state.update_data(screen=Screen.LOOK_HOME.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'look:reset')
async def look_reset(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    await _apply_look_update(state, reset_look)
    await state.set_state(None)
    await state.update_data(screen=Screen.LOOK_HOME.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'look:video_menu')
async def look_video_menu(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    data = await state.get_data()
    if not data.get('look_base_job_id'):
        await query.answer('Нужна текущая база лука', show_alert=True)
        return
    await state.update_data(screen=Screen.LOOK_VIDEO_MENU.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data.startswith('look:video:'))
async def look_generate_video(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    preset = int(query.data.split(':')[-1])
    data = await state.get_data()
    base_job_id = data.get('look_base_job_id')
    if not base_job_id:
        await query.answer('Нужно получить base через job', show_alert=True)
        return

    if not await _consume_rate_limit(
        settings=settings,
        tg_user_id=query.from_user.id,
        action='video',
        limit=settings.bot_rate_limit_video_per_hour,
    ):
        await query.answer('Лимит генераций видео исчерпан (1ч)', show_alert=True)
        return

    api = await _client(query, settings)
    video_job = await api.create_video(base_job_id, preset)
    await state.update_data(last_video_job_id=video_job['video_job_id'], polling_job_id=video_job['video_job_id'], screen=Screen.LOOK_MONITOR.value)

    while True:
        status = await api.get_job(video_job['video_job_id'])
        await state.update_data(job_status=status['status'], progress=status.get('progress') or 0)
        await _render_current(bot, state, query.message.chat.id, api, settings)
        if status['status'] in {'done', 'failed'}:
            if status['status'] == 'done' and status.get('result_video_url'):
                content = await _read_result_bytes(status['result_video_url'])
                await bot.send_video(query.message.chat.id, video=BufferedInputFile(content, filename='look_video.mp4'))
                await state.update_data(last_video_status='done')
            break
        await asyncio.sleep(2)

    await state.update_data(screen=Screen.LOOK_HOME.value)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'session:reset')
async def reset_session(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    keep = {'screen': Screen.HOME.value, 'gen_mode': 'strict', 'edit_scope': 'full', 'look_active': False, 'look_steps': 0, 'look_stack': [], 'look_patch_mode': True, 'look_base_job_id': None}
    await state.clear()
    await state.update_data(**keep)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data.startswith('provider:'))
async def select_provider(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    provider = query.data.split(':', 1)[1]
    api = await _client(query, settings)
    await api.patch_me({'provider': provider})
    await _switch_screen(bot, state, query.message.chat.id, api, settings, Screen.SETTINGS)


@router.callback_query(F.data.startswith('history:'))
async def history_actions(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    if query.data.startswith('history:job:'):
        await query.answer()
        job_id = query.data.split(':', 2)[2]
        items = (await state.get_data()).get('history_items', [])
        item = next((row for row in items if row['job_id'] == job_id), None)
        if item is None:
            await query.answer('Задача не найдена в текущей странице', show_alert=True)
            return
        await query.answer(
            f'type={item["type"]}\nstatus={item["status"]}\nprovider={item["provider"]}\npreset={item.get("preset") or "—"}',
            show_alert=True,
        )
        return

    await query.answer()
    api = await _client(query, settings)
    data = await state.get_data()
    offset = data.get('history_offset', 0)
    if query.data == 'history:next':
        offset += 10
    elif query.data == 'history:prev':
        offset = max(0, offset - 10)
    await state.update_data(history_offset=offset)
    jobs = await api.list_jobs(offset=offset, limit=10)
    await state.update_data(history_items=jobs['items'], screen=Screen.HISTORY.value)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'settings:purge')
async def settings_purge(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    await state.update_data(screen=Screen.PURGE_CONFIRM.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'purge:yes')
async def purge_yes(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer('Удаляю данные…')
    api = await _client(query, settings)
    await api.purge_me()
    await state.clear()
    await state.update_data(screen=Screen.HOME.value)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'purge:no')
async def purge_no(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer('Отменено')
    api = await _client(query, settings)
    await _switch_screen(bot, state, query.message.chat.id, api, settings, Screen.SETTINGS)
