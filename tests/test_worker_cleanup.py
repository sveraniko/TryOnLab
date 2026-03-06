from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.storage_utils import safe_delete
from app.worker.cleanup import cleanup_expired_jobs


def test_safe_delete_ignores_none_and_errors() -> None:
    storage = AsyncMock()

    asyncio.run(safe_delete(storage, None))
    storage.delete.assert_not_called()

    storage.delete.side_effect = RuntimeError('boom')
    asyncio.run(safe_delete(storage, 'key-1'))
    storage.delete.assert_awaited_once_with('key-1')


def test_cleanup_expired_jobs_marks_and_deletes() -> None:
    jobs = [
        SimpleNamespace(
            id='job-1',
            status='done',
            product_media_key='p1',
            user_media_key='u1',
            result_image_key='ri1',
            result_video_key='rv1',
        ),
        SimpleNamespace(
            id='job-2',
            status='failed',
            product_media_key='p2',
            user_media_key=None,
            result_image_key=None,
            result_video_key='rv2',
        ),
    ]

    class FakeSession:
        async def scalars(self, _query):
            return jobs

        async def commit(self):
            return None

    session = FakeSession()
    redis = AsyncMock()
    storage = AsyncMock()

    cleaned = asyncio.run(cleanup_expired_jobs(session=session, redis=redis, storage=storage, limit=100))

    assert cleaned == 2
    assert jobs[0].status == 'expired'
    assert jobs[1].status == 'expired'
    storage.delete.assert_any_await('p1')
    storage.delete.assert_any_await('u1')
    storage.delete.assert_any_await('ri1')
    storage.delete.assert_any_await('rv1')
    storage.delete.assert_any_await('p2')
    storage.delete.assert_any_await('rv2')
    redis.delete.assert_any_await('job:job-1:status')
    redis.delete.assert_any_await('job:job-2:status')
