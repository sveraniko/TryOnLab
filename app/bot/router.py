from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, ForceReply, Message

from app.bot.api.client import ApiClient
from app.bot.fsm.states import WizardStates
from app.bot.services.parser import parse_measurements_text
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
    providers = await api.list_providers()
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


@router.message(Command('start'))
async def start_handler(message: Message, state: FSMContext, bot: Bot, settings: Settings) -> None:
    api = await _client(message, settings)
    me = await api.get_me()
    panel_id = await ensure_panel(bot, chat_id=message.chat.id, panel_message_id=me.get('panel_message_id'), fallback_text='TryOnLab loading...')
    if me.get('panel_message_id') != panel_id:
        await api.patch_me({'panel_message_id': panel_id})
    await state.update_data(screen=Screen.HOME.value)
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
        'measurements': Screen.MEASUREMENTS,
        'generate': Screen.GENERATE,
        'video': Screen.VIDEO_MENU,
        'settings': Screen.SETTINGS,
        'provider': Screen.PROVIDER,
        'history': Screen.HISTORY,
    }
    screen = mapping.get(target, Screen.HOME)
    if screen == Screen.PRODUCT:
        await state.set_state(WizardStates.await_product_photo)
    elif screen == Screen.USER_PHOTO_UPLOAD:
        await state.set_state(WizardStates.await_user_photo_upload)
    elif screen == Screen.MEASUREMENTS:
        await state.set_state(WizardStates.await_measurements_text)
        await query.message.answer('Введи параметры текстом.', reply_markup=ForceReply(selective=True))
    else:
        await state.set_state(None)

    if screen == Screen.USER_PHOTO_LIST:
        photos = await api.list_photos(offset=(await state.get_data()).get('photos_offset', 0), limit=9)
        await state.update_data(photo_items=photos['items'])
    if screen == Screen.HISTORY:
        jobs = await api.list_jobs(offset=(await state.get_data()).get('history_offset', 0), limit=10)
        await state.update_data(history_items=jobs['items'])
    if screen == Screen.PROVIDER:
        me = await api.get_me()
        providers = await api.list_providers()
        await state.update_data(providers=[{'name':p['name'], 'current':p['name']==me['provider']} for p in providers])

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
    await state.update_data(product_file_id=file_id, screen=Screen.HOME.value)
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


@router.callback_query(F.data.startswith('fit:'))
async def set_fit(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    fit = query.data.split(':', 1)[1]
    await state.update_data(fit_pref=fit, screen=Screen.HOME.value)
    api = await _client(query, settings)
    await _render_current(bot, state, query.message.chat.id, api, settings)


@router.callback_query(F.data == 'measure:input')
async def measure_input(query: CallbackQuery) -> None:
    await query.answer('Отправь текст с параметрами')


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


async def _read_result_bytes(url: str) -> bytes:
    if url.startswith('file://'):
        return Path(url[7:]).read_bytes()
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content


async def _monitor_job(bot: Bot, state: FSMContext, chat_id: int, api: ApiClient, settings: Settings, job_id: str, media_type: str) -> None:
    await state.update_data(screen=Screen.GENERATE.value)
    while True:
        data = await api.get_job(job_id)
        await state.update_data(job_status=data['status'], progress=data.get('progress') or 0)
        await _render_current(bot, state, chat_id, api, settings)
        if data['status'] in {'done', 'failed'}:
            if data['status'] == 'done':
                if media_type == 'image' and data.get('result_image_url'):
                    content = await _read_result_bytes(data['result_image_url'])
                    await bot.send_photo(chat_id, photo=BufferedInputFile(content, filename='result.jpg'))
                if media_type == 'video' and data.get('result_video_url'):
                    content = await _read_result_bytes(data['result_video_url'])
                    await bot.send_video(chat_id, video=BufferedInputFile(content, filename='result.mp4'))
            break
        await asyncio.sleep(2)
    await state.update_data(screen=Screen.HOME.value)
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

    file = await bot.get_file(data['product_file_id'])
    stream = await bot.download_file(file.file_path)
    job = await api.create_job(
        product=stream.read(),
        user_photo_id=me['active_user_photo_id'],
        fit_pref=data.get('fit_pref'),
        measurements_json=data.get('measurements_json'),
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
    video_job = await api.create_video(job_id, preset)
    await state.update_data(last_video_job_id=video_job['video_job_id'])
    await _monitor_job(bot, state, query.message.chat.id, api, settings, video_job['video_job_id'], 'video')


@router.callback_query(F.data == 'session:reset')
async def reset_session(query: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await query.answer()
    keep = {'screen': Screen.HOME.value}
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
