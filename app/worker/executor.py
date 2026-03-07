from __future__ import annotations

from collections.abc import Awaitable, Callable
from io import BytesIO

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Job, UserPhoto
from app.providers.base import ProviderBadRequestError
from app.providers.registry import ProviderRegistry
from app.services.storage import StorageBackend
from app.worker.lock_engine import compose_result, prepare_controlled_patch


async def execute_job(
    session: AsyncSession,
    storage: StorageBackend,
    job: Job,
    registry: ProviderRegistry,
    on_progress: Callable[[int], Awaitable[None]] | None = None,
) -> None:
    settings = get_settings()
    provider = registry.get(job.provider)

    if job.type == 'tryon_image':
        person_key = await _resolve_person_key(session, job)
        clean_key, fit_key = _resolve_product_keys(job)
        if not clean_key and not fit_key:
            raise ProviderBadRequestError('No product image')

        mode = _input(job, 'mode', 'strict')
        scope = _input(job, 'scope', 'full')

        force_lock = _input_bool(job, 'force_lock', False)

        if scope != 'full' and force_lock:
            person_bytes = await storage.get_bytes(person_key)
            plan = await prepare_controlled_patch(
                settings=settings,
                storage=storage,
                job_id=str(job.id),
                base_image_bytes=person_bytes,
                scope=scope,
            )
            crop_bytes, crop_rect = _crop_person_bytes(person_bytes, plan.crop_rect)
            crop_key = f'tryon/jobs/{job.id}/tmp/person_crop.jpg'
            await storage.put_bytes(crop_key, crop_bytes, content_type='image/jpeg')

            result = await provider.generate_image(
                job_id=str(job.id),
                storage_key_product=job.product_media_key,
                storage_key_product_clean=clean_key,
                storage_key_product_fit=fit_key,
                storage_key_person=crop_key,
                fit_pref=job.fit_pref,
                measurements=job.measurements_json,
                mode=mode,
                scope=scope,
                force_lock=force_lock,
                on_progress=on_progress,
            )
            edited_crop_bytes = await storage.get_bytes(result.storage_key)
            final_bytes = await compose_result(
                settings=settings,
                base_image_bytes=person_bytes,
                edited_patch_bytes=edited_crop_bytes,
                plan=plan,
            )
            output_key = f'tryon/jobs/{job.id}/output/image.jpg'
            await storage.put_bytes(output_key, final_bytes, content_type='image/jpeg')
            job.result_image_key = output_key
            job.result_json = {
                **(result.metadata or {}),
                'mode': mode,
                'scope': scope,
                'lock_engine': plan.lock_engine,
                'parsing_backend': plan.parsing_backend,
                'mask_area_ratio': plan.mask_area_ratio,
                'force_lock': force_lock,
                **(plan.metadata or {}),
            }
            return

        result = await provider.generate_image(
            job_id=str(job.id),
            storage_key_product=job.product_media_key,
            storage_key_product_clean=clean_key,
            storage_key_product_fit=fit_key,
            storage_key_person=person_key,
            fit_pref=job.fit_pref,
            measurements=job.measurements_json,
            mode=mode,
            scope=scope,
            force_lock=force_lock,
            on_progress=on_progress,
        )
        job.result_image_key = result.storage_key
        job.result_json = {
            **(result.metadata or {}),
            'mode': mode,
            'scope': scope,
            'lock_engine': 'disabled',
            'parsing_backend': 'none',
            'force_lock': force_lock,
        }
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


def _input(job: Job, key: str, default: str) -> str:
    if not job.inputs_json:
        return default
    value = str(job.inputs_json.get(key, default)).strip().lower()
    if key == 'mode' and value in {'strict', 'creative'}:
        return value
    if key == 'scope' and value in {'upper', 'lower', 'feet', 'full'}:
        return value
    return default


def _crop_person_bytes(person_bytes: bytes, rect: tuple[int, int, int, int]) -> tuple[bytes, tuple[int, int, int, int]]:
    image = Image.open(BytesIO(person_bytes)).convert('RGB')
    cropped = image.crop(rect)
    out = BytesIO()
    cropped.save(out, format='JPEG')
    return out.getvalue(), rect


def _input_bool(job: Job, key: str, default: bool) -> bool:
    if not job.inputs_json:
        return default
    value = job.inputs_json.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def _resolve_product_keys(job: Job) -> tuple[str | None, str | None]:
    if not job.inputs_json:
        return job.product_media_key, None
    clean_key = job.inputs_json.get('product_clean_key') or job.product_media_key
    fit_key = job.inputs_json.get('product_fit_key')
    return str(clean_key) if clean_key else None, str(fit_key) if fit_key else None
