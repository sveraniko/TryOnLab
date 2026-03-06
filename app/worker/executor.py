from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, UserPhoto
from app.services.storage import StorageBackend
from app.services.storage_keys import job_key


@dataclass
class ExecutionFailure(Exception):
    error_code: str
    error_message: str
    is_retryable: bool = False


async def execute_job(session: AsyncSession, storage: StorageBackend, job: Job) -> None:
    if job.type == 'tryon_image':
        if job.provider == 'dummy':
            await _execute_dummy_image(session, storage, job)
            return
        raise ExecutionFailure('provider_not_implemented', f'Provider {job.provider} is not implemented', False)

    if job.type == 'tryon_video':
        if job.provider == 'dummy':
            raise ExecutionFailure('video_not_implemented', 'Dummy video generation is not implemented', False)
        raise ExecutionFailure('provider_not_implemented', f'Provider {job.provider} is not implemented', False)

    raise ExecutionFailure('unsupported_job_type', f'Unsupported job type: {job.type}', False)


async def _execute_dummy_image(session: AsyncSession, storage: StorageBackend, job: Job) -> None:
    source_key = await _resolve_source_key(session, job)
    data = await storage.get_bytes(source_key)
    output_key = job_key(str(job.id), 'output', 'image.jpg')
    await storage.put_bytes(output_key, data, content_type='image/jpeg')
    job.result_image_key = output_key
    job.result_json = {'dummy': True, 'source': source_key}


async def _resolve_source_key(session: AsyncSession, job: Job) -> str:
    if job.user_media_key:
        return job.user_media_key

    if job.user_photo_id:
        user_photo = await session.scalar(select(UserPhoto).where(UserPhoto.id == job.user_photo_id))
        if user_photo is None or user_photo.deleted_at is not None or user_photo.is_deleted:
            raise ExecutionFailure('bad_request', 'User photo not found', False)
        return user_photo.storage_key

    raise ExecutionFailure('bad_request', 'No source user image provided', False)
