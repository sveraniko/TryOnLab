from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, User, UserPhoto, UserSettings


async def upsert_user(session: AsyncSession, tg_user_id: int, tg_chat_id: int) -> User:
    query: Select[tuple[User]] = select(User).where(User.tg_user_id == tg_user_id)
    user = await session.scalar(query)

    if user is None:
        user = User(tg_user_id=tg_user_id, tg_chat_id=tg_chat_id)
        session.add(user)
        await session.flush()
    else:
        user.tg_chat_id = tg_chat_id
        user.last_seen_at = datetime.now(UTC)

    return user


async def ensure_user_settings(session: AsyncSession, user_id: int, default_provider: str) -> UserSettings:
    settings = await session.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if settings is None:
        settings = UserSettings(user_id=user_id, provider=default_provider)
        session.add(settings)
        await session.flush()
    return settings


async def create_image_job(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    user_id: int,
    provider: str,
    retention_hours: int,
    product_media_key: str,
    user_media_key: str | None,
    user_photo_id: int | None,
    fit_pref: str | None,
    height_cm: int | None,
    measurements_json: dict | None,
    inputs_json: dict | None = None,
) -> Job:
    expires_at = datetime.now(UTC) + timedelta(hours=retention_hours)
    job = Job(
        id=job_id,
        user_id=user_id,
        type='tryon_image',
        provider=provider,
        status='queued',
        progress=0,
        attempts=0,
        is_retryable=True,
        expires_at=expires_at,
        product_media_key=product_media_key,
        user_media_key=user_media_key,
        user_photo_id=user_photo_id,
        fit_pref=fit_pref,
        height_cm=height_cm,
        measurements_json=measurements_json,
        inputs_json=inputs_json,
    )
    session.add(job)
    await session.flush()
    return job


async def get_job_for_user(session: AsyncSession, job_id: uuid.UUID, user_id: int) -> Job:
    job = await session.scalar(select(Job).where(Job.id == job_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job not found')
    if job.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    return job


async def retry_job(session: AsyncSession, job: Job) -> Job:
    if job.status == 'running':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Job is currently running')
    if job.attempts >= job.max_attempts:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Max retry attempts exceeded')

    job.attempts += 1
    job.status = 'queued'
    job.progress = 0
    job.error_code = None
    job.error_message = None
    job.result_image_key = None
    job.result_video_key = None
    job.result_json = None
    job.started_at = None
    job.finished_at = None
    await session.flush()
    return job


async def create_video_job(
    session: AsyncSession,
    *,
    parent_job: Job,
    provider: str,
    preset: int,
    retention_hours: int,
) -> Job:
    if parent_job.type != 'tryon_image':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Video can only be created from image job')
    if parent_job.status != 'done' or not parent_job.result_image_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Image job must be done and have result_image_key',
        )

    video_job = Job(
        id=uuid.uuid4(),
        user_id=parent_job.user_id,
        type='tryon_video',
        parent_job_id=parent_job.id,
        provider=provider,
        status='queued',
        progress=0,
        attempts=0,
        is_retryable=True,
        preset=preset,
        inputs_json={'parent_result_image_key': parent_job.result_image_key},
        expires_at=datetime.now(UTC) + timedelta(hours=retention_hours),
    )
    session.add(video_job)
    await session.flush()
    return video_job


async def get_user_photo_for_user(session: AsyncSession, user_photo_id: int, user_id: int) -> UserPhoto:
    user_photo = await session.scalar(select(UserPhoto).where(UserPhoto.id == user_photo_id))
    if user_photo is None or user_photo.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User photo not found')
    if user_photo.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    return user_photo


async def list_user_photos(
    session: AsyncSession,
    *,
    user_id: int,
    offset: int,
    limit: int,
) -> tuple[list[UserPhoto], int]:
    total = await session.scalar(
        select(func.count(UserPhoto.id)).where(
            UserPhoto.user_id == user_id,
            UserPhoto.deleted_at.is_(None),
        )
    )
    items = list(
        await session.scalars(
            select(UserPhoto)
            .where(
                UserPhoto.user_id == user_id,
                UserPhoto.deleted_at.is_(None),
            )
            .order_by(UserPhoto.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return items, int(total or 0)


async def list_jobs_for_user(
    session: AsyncSession,
    *,
    user_id: int,
    offset: int,
    limit: int,
) -> tuple[list[Job], int]:
    total = await session.scalar(select(func.count(Job.id)).where(Job.user_id == user_id))
    items = list(
        await session.scalars(
            select(Job)
            .where(Job.user_id == user_id)
            .order_by(Job.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return items, int(total or 0)
