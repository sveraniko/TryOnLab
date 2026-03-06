from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, get_redis, get_storage
from app.api.schemas.jobs import JobCreateResponse, JobRetryResponse, JobStatusResponse, VideoJobCreateResponse
from app.core.config import Settings, get_settings
from app.db.models import User
from app.services.job_status import set_job_status
from app.services.jobs import (
    create_image_job,
    create_video_job,
    ensure_user_settings,
    get_job_for_user,
    get_user_photo_for_user,
    retry_job,
)
from app.services.media import parse_measurements_json, validate_image_upload
from app.services.storage import StorageBackend
from app.services.storage_keys import job_key

router = APIRouter(prefix='/jobs', tags=['jobs'])


def _provider_allowlist(settings: Settings) -> set[str]:
    values = [item.strip().lower() for item in settings.ai_provider_allowlist.split(',')]
    return {item for item in values if item}


def _validate_provider(provider: str, settings: Settings) -> str:
    normalized = provider.strip().lower()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='provider cannot be empty')

    if normalized not in _provider_allowlist(settings):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='provider is not allowed')

    return normalized


async def _set_queued_status(redis: Redis, settings: Settings, job_id: uuid.UUID) -> None:
    await set_job_status(redis, job_id, status='queued', progress=0, ttl=settings.job_status_ttl_seconds)
    await redis.rpush(settings.job_queue_key, str(job_id))


@router.post('', response_model=JobCreateResponse)
async def create_job(
    product_image: UploadFile = File(...),
    person_image: UploadFile | None = File(default=None),
    user_photo_id: int | None = Form(default=None),
    fit_pref: str | None = Form(default=None),
    height_cm: int | None = Form(default=None),
    measurements_json: str | None = Form(default=None),
    provider: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
    storage: StorageBackend = Depends(get_storage),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> JobCreateResponse:
    if (person_image is None and user_photo_id is None) or (person_image is not None and user_photo_id is not None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Provide exactly one of person_image or user_photo_id',
        )

    if fit_pref is not None and fit_pref not in {'slim', 'regular', 'oversize'}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid fit_pref')

    product_bytes, product_content_type, product_filename = await validate_image_upload(
        product_image, settings.max_upload_mb
    )

    person_key = None
    validated_user_photo_id = None
    if person_image is not None:
        person_bytes, person_content_type, person_filename = await validate_image_upload(person_image, settings.max_upload_mb)
    else:
        person_bytes = None
        person_content_type = None
        person_filename = None
        await get_user_photo_for_user(session, user_photo_id=user_photo_id, user_id=current_user.id)
        validated_user_photo_id = user_photo_id

    measurements = parse_measurements_json(measurements_json)

    user_settings = await ensure_user_settings(
        session, user_id=current_user.id, default_provider=settings.ai_provider_default
    )
    selected_provider = _validate_provider(provider or user_settings.provider, settings)

    job_id = uuid.uuid4()
    product_key = job_key(job_id, 'input', product_filename)
    await storage.put_bytes(product_key, product_bytes, content_type=product_content_type)

    if person_bytes is not None and person_content_type is not None and person_filename is not None:
        person_key = job_key(job_id, 'input', person_filename)
        await storage.put_bytes(person_key, person_bytes, content_type=person_content_type)

    job = await create_image_job(
        session,
        job_id=job_id,
        user_id=current_user.id,
        provider=selected_provider,
        retention_hours=settings.retention_hours,
        product_media_key=product_key,
        user_media_key=person_key,
        user_photo_id=validated_user_photo_id,
        fit_pref=fit_pref,
        height_cm=height_cm,
        measurements_json=measurements,
    )
    await session.commit()

    await _set_queued_status(redis, settings, job.id)
    return JobCreateResponse(job_id=job.id, status=job.status)


@router.get('/{job_id}', response_model=JobStatusResponse)
async def get_job_status(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
    storage: StorageBackend = Depends(get_storage),
    current_user: User = Depends(get_current_user),
) -> JobStatusResponse:
    job = await get_job_for_user(session, job_id=job_id, user_id=current_user.id)

    redis_status = await redis.get(f'job:{job.id}:status')
    status_value = job.status
    progress = job.progress
    if redis_status:
        try:
            parsed = json.loads(redis_status)
            status_value = parsed.get('status', status_value)
            progress = parsed.get('progress', progress)
        except json.JSONDecodeError:
            pass

    result_image_url = await storage.get_url(job.result_image_key) if job.result_image_key else None
    result_video_url = await storage.get_url(job.result_video_key) if job.result_video_key else None

    return JobStatusResponse(
        job_id=job.id,
        type=job.type,
        status=status_value,
        progress=progress,
        provider=job.provider,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        result_image_url=result_image_url,
        result_video_url=result_video_url,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post('/{job_id}/retry', response_model=JobRetryResponse)
async def retry_job_endpoint(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> JobRetryResponse:
    job = await get_job_for_user(session, job_id=job_id, user_id=current_user.id)
    job = await retry_job(session, job)
    await session.commit()

    await _set_queued_status(redis, settings, job.id)
    return JobRetryResponse(job_id=job.id, status=job.status, attempts=job.attempts)


@router.post('/{job_id}/video', response_model=VideoJobCreateResponse)
async def create_video_job_endpoint(
    job_id: uuid.UUID,
    preset: int = Query(..., ge=1, le=5),
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> VideoJobCreateResponse:
    image_job = await get_job_for_user(session, job_id=job_id, user_id=current_user.id)
    video_job = await create_video_job(
        session,
        parent_job=image_job,
        provider=_validate_provider(image_job.provider, settings),
        preset=preset,
        retention_hours=settings.retention_hours,
    )
    await session.commit()

    await _set_queued_status(redis, settings, video_job.id)
    return VideoJobCreateResponse(video_job_id=video_job.id, status=video_job.status)
