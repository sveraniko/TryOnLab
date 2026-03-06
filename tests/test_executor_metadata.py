from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("numpy", reason="numpy is required by worker executor imports")
from app.worker.executor import execute_job


class DummyProvider:
    name = 'dummy'

    async def generate_image(self, **kwargs):
        _ = kwargs
        return SimpleNamespace(storage_key='out/image.jpg', metadata={'provider': 'dummy'})


class DummyRegistry:
    def get(self, _name: str):
        return DummyProvider()


class DummyStorage:
    async def get_bytes(self, _key: str) -> bytes:
        return b''


class DummySession:
    async def scalar(self, _query):
        return None


def test_plain_flow_adds_mode_scope_metadata() -> None:
    job = SimpleNamespace(
        id='job-1',
        provider='dummy',
        type='tryon_image',
        product_media_key='product.jpg',
        user_media_key='user.jpg',
        user_photo_id=None,
        fit_pref='regular',
        measurements_json=None,
        inputs_json={'mode': 'creative', 'scope': 'full', 'force_lock': False},
        result_image_key=None,
        result_json=None,
    )

    asyncio.run(execute_job(DummySession(), DummyStorage(), job, DummyRegistry()))

    assert job.result_image_key == 'out/image.jpg'
    assert job.result_json['mode'] == 'creative'
    assert job.result_json['scope'] == 'full'
    assert job.result_json['lock_engine'] == 'disabled'
    assert job.result_json['parsing_backend'] == 'none'
    assert job.result_json['force_lock'] is False
