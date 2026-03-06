import asyncio

from app.bot.api.client import ApiClient


def test_create_job_force_lock_default_on_for_look_builder_style_call() -> None:
    client = ApiClient('http://api.local', tg_user_id=1, tg_chat_id=2)
    captured = {}

    async def fake_request(method, path, **kwargs):
        captured['method'] = method
        captured['path'] = path
        captured['kwargs'] = kwargs
        return {'job_id': 'x'}

    client._request = fake_request  # type: ignore[method-assign]

    asyncio.run(
        client.create_job(
            product=b'prod',
            person_image=b'person',
            user_photo_id=None,
            fit_pref='regular',
            measurements_json=None,
            mode='strict',
            scope='upper',
            force_lock=True,
        )
    )

    assert captured['method'] == 'POST'
    assert captured['path'] == '/jobs'
    assert captured['kwargs']['data']['force_lock'] == '1'


def test_create_job_force_lock_off() -> None:
    client = ApiClient('http://api.local', tg_user_id=1, tg_chat_id=2)
    captured = {}

    async def fake_request(method, path, **kwargs):
        captured['kwargs'] = kwargs
        return {'job_id': 'x'}

    client._request = fake_request  # type: ignore[method-assign]

    asyncio.run(
        client.create_job(
            product=b'prod',
            person_image=None,
            user_photo_id=9,
            fit_pref='regular',
            measurements_json=None,
            mode='creative',
            scope='lower',
            force_lock=False,
        )
    )

    assert captured['kwargs']['data']['force_lock'] == '0'
