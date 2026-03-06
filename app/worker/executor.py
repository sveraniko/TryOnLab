from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, UserPhoto
from app.providers.base import ProviderBadRequestError
from app.providers.registry import ProviderRegistry
from app.services.storage import StorageBackend


async def execute_job(
    session: AsyncSession,
    storage: StorageBackend,
    job: Job,
    registry: ProviderRegistry,
    on_progress: Callable[[int], Awaitable[None]] | None = None,
) -> None:
    provider = registry.get(job.provider)

    if job.type == 'tryon_image':
        person_key = await _resolve_person_key(session, job)
        if not job.product_media_key:
            raise ProviderBadRequestError('No product image')

        result = await provider.generate_image(
            job_id=str(job.id),
            storage_key_product=job.product_media_key,
            storage_key_person=person_key,
            fit_pref=job.fit_pref,
            measurements=job.measurements_json,
            on_progress=on_progress,
        )
        job.result_image_key = result.storage_key
        job.result_json = result.metadata
        return

    if job.type == 'tryon_video':
        source_image_key = _resolve_video_source_key(job)
        result = await provider.generate_video(
            job_id=str(job.id),
            storage_key_image_result=source_image_key,
            preset=job.preset or 1,
            on_progress=on_progress,
        )
        job.result_video_key = result.storage_key
        job.result_json = result.metadata
        return

    raise ProviderBadRequestError(f'Unsupported job type: {job.type}')


async def _resolve_person_key(session: AsyncSession, job: Job) -> str:
    if job.user_media_key:
        return job.user_media_key

    if job.user_photo_id:
        user_photo = await session.scalar(select(UserPhoto).where(UserPhoto.id == job.user_photo_id))
        if user_photo is None or user_photo.deleted_at is not None or user_photo.is_deleted:
            raise ProviderBadRequestError('User photo not found')
        return user_photo.storage_key

    raise ProviderBadRequestError('No person image')


def _resolve_video_source_key(job: Job) -> str:
    if job.inputs_json and job.inputs_json.get('parent_result_image_key'):
        return str(job.inputs_json['parent_result_image_key'])

    raise ProviderBadRequestError('No image result for video generation')
