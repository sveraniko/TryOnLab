from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.services.jobs import ensure_user_settings, upsert_user
from app.services.storage import StorageBackend, create_storage


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


async def get_redis(settings: Settings = Depends(get_settings)) -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


@lru_cache(maxsize=1)
def _get_storage_cached() -> StorageBackend:
    settings = get_settings()
    return create_storage(settings)


async def get_storage() -> StorageBackend:
    return _get_storage_cached()


async def get_current_user(
    db_session: AsyncSession = Depends(get_db_session),
    x_tg_user_id: str | None = Header(default=None, alias='X-TG-User-Id'),
    x_tg_chat_id: str | None = Header(default=None, alias='X-TG-Chat-Id'),
):
    if not x_tg_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='X-TG-User-Id header is required',
        )

    try:
        tg_user_id = int(x_tg_user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='X-TG-User-Id must be an integer',
        ) from exc

    if x_tg_chat_id is None:
        tg_chat_id = tg_user_id
    else:
        try:
            tg_chat_id = int(x_tg_chat_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='X-TG-Chat-Id must be an integer',
            ) from exc

    user = await upsert_user(db_session, tg_user_id=tg_user_id, tg_chat_id=tg_chat_id)
    await ensure_user_settings(db_session, user_id=user.id)
    await db_session.commit()
    await db_session.refresh(user)
    return user
