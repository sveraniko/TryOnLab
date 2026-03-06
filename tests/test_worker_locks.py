import asyncio
from unittest.mock import AsyncMock

from app.worker.locks import release_lock, renew_lock


def test_renew_lock_only_on_matching_token() -> None:
    redis = AsyncMock()
    redis.eval.return_value = 1

    renewed = asyncio.run(renew_lock(redis, key='lock:job:1', token='abc', lease_seconds=300))

    assert renewed is True
    redis.eval.assert_awaited_once()


def test_release_lock_only_on_matching_token() -> None:
    redis = AsyncMock()
    redis.eval.return_value = 0

    released = asyncio.run(release_lock(redis, key='lock:job:1', token='bad'))

    assert released is False
    redis.eval.assert_awaited_once()
