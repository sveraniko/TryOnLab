from __future__ import annotations

import asyncio
import datetime
from types import SimpleNamespace
from uuid import UUID

from starlette.datastructures import UploadFile

if not hasattr(datetime, 'UTC'):
    datetime.UTC = datetime.timezone.utc  # type: ignore[attr-defined]

from app.api.routers import jobs as jobs_router


class DummyStorage:
    def __init__(self) -> None:
        self.saved: list[tuple[str, bytes, str]] = []

    async def put_bytes(self, key: str, data: bytes, *, content_type: str) -> None:
        self.saved.append((key, data, content_type))


class DummyRedis:
    async def rpush(self, *_args, **_kwargs) -> None:
        return None


class DummySession:
    async def commit(self) -> None:
        return None


def _upload(name: str, payload: bytes) -> UploadFile:
    from io import BytesIO

    return UploadFile(filename=name, file=BytesIO(payload), headers={'content-type': 'image/jpeg'})


def _run_create(**kwargs):
    return asyncio.run(jobs_router.create_job(**kwargs))


def _base_kwargs(storage: DummyStorage):
    settings = SimpleNamespace(
        max_upload_mb=10,
        retention_hours=24,
        ai_provider_default='grok',
        ai_provider_allowlist='grok,openai,dummy',
        job_queue_key='jobs:queue',
        job_status_ttl_seconds=120,
    )
    return dict(
        person_image=_upload('person.jpg', b'person'),
        user_photo_id=None,
        fit_pref='regular',
        height_cm=None,
        measurements_json=None,
        provider='grok',
        mode='strict',
        scope='full',
        force_lock='0',
        session=DummySession(),
        redis=DummyRedis(),
        storage=storage,
        current_user=SimpleNamespace(id=123),
        settings=settings,
        registry=SimpleNamespace(list=lambda: ['grok', 'openai', 'dummy']),
    )


def test_create_job_clean_only_sets_inputs_json(monkeypatch) -> None:
    captured = {}

    async def fake_ensure_user_settings(*_args, **_kwargs):
        return SimpleNamespace(provider='grok')

    async def fake_create_image_job(_session, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=kwargs['job_id'], status='queued')

    async def fake_set_queued_status(*_args, **_kwargs):
        return None

    monkeypatch.setattr(jobs_router, 'ensure_user_settings', fake_ensure_user_settings)
    monkeypatch.setattr(jobs_router, 'create_image_job', fake_create_image_job)
    monkeypatch.setattr(jobs_router, '_set_queued_status', fake_set_queued_status)

    storage = DummyStorage()
    kwargs = _base_kwargs(storage)
    response = _run_create(product_image=_upload('product.jpg', b'clean'), product_clean_image=None, product_fit_image=None, **kwargs)

    assert isinstance(response.job_id, UUID)
    assert captured['inputs_json']['product_reference_mode'] == 'clean_only'
    assert 'product_clean_key' in captured['inputs_json']
    assert 'product_fit_key' not in captured['inputs_json']


def test_create_job_fit_only_sets_inputs_json(monkeypatch) -> None:
    captured = {}

    async def fake_ensure_user_settings(*_args, **_kwargs):
        return SimpleNamespace(provider='grok')

    async def fake_create_image_job(_session, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=kwargs['job_id'], status='queued')

    async def fake_set_queued_status(*_args, **_kwargs):
        return None

    monkeypatch.setattr(jobs_router, 'ensure_user_settings', fake_ensure_user_settings)
    monkeypatch.setattr(jobs_router, 'create_image_job', fake_create_image_job)
    monkeypatch.setattr(jobs_router, '_set_queued_status', fake_set_queued_status)

    storage = DummyStorage()
    kwargs = _base_kwargs(storage)
    _run_create(product_image=None, product_clean_image=None, product_fit_image=_upload('fit.jpg', b'fit'), **kwargs)

    assert captured['inputs_json']['product_reference_mode'] == 'fit_only'
    assert 'product_clean_key' not in captured['inputs_json']
    assert 'product_fit_key' in captured['inputs_json']


def test_create_job_clean_plus_fit_sets_inputs_json(monkeypatch) -> None:
    captured = {}

    async def fake_ensure_user_settings(*_args, **_kwargs):
        return SimpleNamespace(provider='grok')

    async def fake_create_image_job(_session, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=kwargs['job_id'], status='queued')

    async def fake_set_queued_status(*_args, **_kwargs):
        return None

    monkeypatch.setattr(jobs_router, 'ensure_user_settings', fake_ensure_user_settings)
    monkeypatch.setattr(jobs_router, 'create_image_job', fake_create_image_job)
    monkeypatch.setattr(jobs_router, '_set_queued_status', fake_set_queued_status)

    storage = DummyStorage()
    kwargs = _base_kwargs(storage)
    _run_create(
        product_image=None,
        product_clean_image=_upload('clean.jpg', b'clean'),
        product_fit_image=_upload('fit.jpg', b'fit'),
        **kwargs,
    )

    assert captured['inputs_json']['product_reference_mode'] == 'clean_plus_fit'
    assert 'product_clean_key' in captured['inputs_json']
    assert 'product_fit_key' in captured['inputs_json']
