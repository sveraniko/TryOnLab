from __future__ import annotations

from redis.asyncio import Redis


_CHECK_AND_EXPIRE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
return 0
"""

_CHECK_AND_DELETE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


async def renew_lock(redis: Redis, key: str, token: str, lease_seconds: int) -> bool:
    renewed = await redis.eval(_CHECK_AND_EXPIRE, 1, key, token, lease_seconds)
    return bool(renewed)


async def release_lock(redis: Redis, key: str, token: str) -> bool:
    released = await redis.eval(_CHECK_AND_DELETE, 1, key, token)
    return bool(released)

