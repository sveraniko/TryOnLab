from __future__ import annotations

import json
import uuid

from redis.asyncio import Redis


async def set_job_status(redis: Redis, job_id: uuid.UUID, status: str, progress: int, ttl: int) -> None:
    payload = json.dumps({'status': status, 'progress': progress}, separators=(',', ':'))
    await redis.setex(f'job:{job_id}:status', ttl, payload)
