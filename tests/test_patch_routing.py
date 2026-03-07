from __future__ import annotations

import asyncio
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

pytest.importorskip('numpy', reason='numpy is required by worker executor imports')

from app.worker.executor import execute_job


class DummyProvider:
    name = 'dummy'

    async def generate_image(self, **kwargs):
        _ = kwargs
        return SimpleNamespace(storage_key='out/image.jpg', metadata={'provider': 'dummy'})


class DummyRegistry:
    def get(self, _name: str):
        return DummyProvider()


class DummySession:
    async def scalar(self, _query):
        return None


class MemoryStorage:
    def __init__(self) -> None:
        img = Image.new('RGB', (64, 64), (30, 30, 30))
        out = BytesIO()
        img.save(out, format='JPEG')
        self._img = out.getvalue()
        self.saved: dict[str, bytes] = {'user.jpg': self._img, 'out/image.jpg': self._img, 'product.jpg': self._img}

    async def get_bytes(self, key: str) -> bytes:
        return self.saved[key]

    async def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        _ = content_type
        self.saved[key] = data


def _job(*, mode: str, scope: str, force_lock: bool) -> SimpleNamespace:
    return SimpleNamespace(
        id='job-1',
        provider='dummy',
        type='tryon_image',
        product_media_key='product.jpg',
        user_media_key='user.jpg',
        user_photo_id=None,
        fit_pref='regular',
        measurements_json=None,
        inputs_json={'mode': mode, 'scope': scope, 'force_lock': force_lock},
        result_image_key=None,
        result_json=None,
    )


def test_strict_lower_force_lock_false_bypasses_lock_engine(monkeypatch):
    async def _unexpected(*args, **kwargs):
        raise AssertionError('lock engine must be bypassed')

    monkeypatch.setattr('app.worker.executor.prepare_controlled_patch', _unexpected)
    storage = MemoryStorage()
    job = _job(mode='strict', scope='lower', force_lock=False)
    asyncio.run(execute_job(DummySession(), storage, job, DummyRegistry()))
    assert job.result_json['lock_engine'] == 'disabled'


def test_strict_lower_force_lock_true_enables_lock_engine(monkeypatch):
    plan = SimpleNamespace(crop_rect=(0, 0, 64, 64), lock_engine='mask_v1_lower_v2', parsing_backend='fake', mask_area_ratio=0.4, metadata={})

    async def _plan(*args, **kwargs):
        return plan

    async def _compose(*args, **kwargs):
        return MemoryStorage()._img

    monkeypatch.setattr('app.worker.executor.prepare_controlled_patch', _plan)
    monkeypatch.setattr('app.worker.executor.compose_result', _compose)

    storage = MemoryStorage()
    job = _job(mode='strict', scope='lower', force_lock=True)
    asyncio.run(execute_job(DummySession(), storage, job, DummyRegistry()))
    assert job.result_json['lock_engine'] == 'mask_v1_lower_v2'


def test_creative_upper_force_lock_false_bypasses_lock_engine(monkeypatch):
    async def _unexpected(*args, **kwargs):
        raise AssertionError('lock engine must be bypassed')

    monkeypatch.setattr('app.worker.executor.prepare_controlled_patch', _unexpected)
    storage = MemoryStorage()
    job = _job(mode='creative', scope='upper', force_lock=False)
    asyncio.run(execute_job(DummySession(), storage, job, DummyRegistry()))
    assert job.result_json['lock_engine'] == 'disabled'


def test_full_scope_force_lock_true_bypasses_lock_engine(monkeypatch):
    async def _unexpected(*args, **kwargs):
        raise AssertionError('full scope must bypass lock engine')

    monkeypatch.setattr('app.worker.executor.prepare_controlled_patch', _unexpected)
    storage = MemoryStorage()
    job = _job(mode='strict', scope='full', force_lock=True)
    asyncio.run(execute_job(DummySession(), storage, job, DummyRegistry()))
    assert job.result_json['scope'] == 'full'
    assert job.result_json['lock_engine'] == 'disabled'
