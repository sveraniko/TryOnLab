import asyncio

from app.bot.api.client import ApiClient
from app.bot.services.look_builder import resolve_item_refs


def test_look_item_can_store_clean_and_fit_refs() -> None:
    refs = resolve_item_refs({'look_item_clean_file_id': 'clean-1', 'look_item_fit_file_id': 'fit-1'})
    assert refs == {'clean': 'clean-1', 'fit': 'fit-1'}


def test_apply_uses_both_refs_when_present() -> None:
    client = ApiClient('http://api.local', tg_user_id=1, tg_chat_id=2)
    captured = {}

    async def fake_request(_method, _path, **kwargs):
        captured.update(kwargs)
        return {'job_id': 'x'}

    client._request = fake_request  # type: ignore[method-assign]
    asyncio.run(
        client.create_job(
            product_clean=b'clean',
            product_fit=b'fit',
            person_image=b'person',
            user_photo_id=None,
            fit_pref='regular',
            measurements_json=None,
            mode='strict',
            scope='upper',
            force_lock=True,
        )
    )

    files = captured['files']
    assert 'product_clean_image' in files
    assert 'product_fit_image' in files


def test_apply_fallback_to_single_ref() -> None:
    client = ApiClient('http://api.local', tg_user_id=1, tg_chat_id=2)
    captured = {}

    async def fake_request(_method, _path, **kwargs):
        captured.update(kwargs)
        return {'job_id': 'x'}

    client._request = fake_request  # type: ignore[method-assign]
    asyncio.run(
        client.create_job(
            product_clean=b'clean',
            product_fit=None,
            person_image=b'person',
            user_photo_id=None,
            fit_pref='regular',
            measurements_json=None,
            mode='strict',
            scope='upper',
            force_lock=True,
        )
    )

    files = captured['files']
    assert 'product_clean_image' in files
    assert 'product_fit_image' not in files
