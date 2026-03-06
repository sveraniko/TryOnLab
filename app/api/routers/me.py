from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, get_provider_registry, get_settings, get_storage
from app.api.schemas.me import (
    MePatchRequest,
    MeResponse,
    ProvidersMetaItem,
    UserPhotoCreateResponse,
    UserPhotoListItem,
    UserPhotoListResponse,
)
from app.db.models import User, UserPhoto, UserSettings
from app.providers.registry import ProviderRegistry
from app.services.jobs import ensure_user_settings, get_user_photo_for_user, list_user_photos
from app.services.media import validate_image_upload
from app.services.storage import StorageBackend
from app.services.storage_keys import user_photo_key

router = APIRouter(tags=['me'])


async def _build_me_response(session: AsyncSession, user: User) -> MeResponse:
    user_settings = await session.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    provider = user_settings.provider if user_settings else 'unknown'
    active_user_photo_id = user_settings.active_user_photo_id if user_settings else None
    stored_count = await session.scalar(
        select(func.count(UserPhoto.id)).where(UserPhoto.user_id == user.id, UserPhoto.deleted_at.is_(None))
    )

    return MeResponse(
        tg_user_id=user.tg_user_id,
        tg_chat_id=user.tg_chat_id,
        panel_message_id=user.panel_message_id,
        provider=provider,
        active_user_photo_id=active_user_photo_id,
        stored_user_photos_count=int(stored_count or 0),
    )


@router.get('/me', response_model=MeResponse)
async def get_me(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MeResponse:
    return await _build_me_response(session, current_user)


@router.patch('/me', response_model=MeResponse)
async def patch_me(
    payload: MePatchRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    settings=Depends(get_settings),
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> MeResponse:
    user_settings = await ensure_user_settings(session, user_id=current_user.id, default_provider=settings.ai_provider_default)

    if payload.panel_message_id is not None:
        current_user.panel_message_id = payload.panel_message_id

    if payload.provider is not None:
        provider = payload.provider.strip().lower()
        if provider not in registry.list():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Provider is not available')
        user_settings.provider = provider

    if payload.active_user_photo_id is not None:
        photo = await get_user_photo_for_user(session, user_photo_id=payload.active_user_photo_id, user_id=current_user.id)
        if photo.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Photo deleted')
        user_settings.active_user_photo_id = photo.id

    await session.commit()
    await session.refresh(current_user)
    return await _build_me_response(session, current_user)


@router.get('/me/photos', response_model=UserPhotoListResponse)
async def get_user_photos(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=9, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> UserPhotoListResponse:
    items, total = await list_user_photos(session, user_id=current_user.id, offset=offset, limit=limit)
    return UserPhotoListResponse(
        items=[
            UserPhotoListItem(id=item.id, created_at=item.created_at, is_deleted=item.deleted_at is not None)
            for item in items
        ],
        total=total,
    )


@router.post('/me/photos', response_model=UserPhotoCreateResponse)
async def upload_user_photo(
    photo: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    storage: StorageBackend = Depends(get_storage),
    current_user: User = Depends(get_current_user),
    settings=Depends(get_settings),
) -> UserPhotoCreateResponse:
    image_bytes, content_type, filename = await validate_image_upload(photo, settings.max_upload_mb)

    row = UserPhoto(
        user_id=current_user.id,
        storage_key='pending',
        mime_type=content_type,
        file_size=len(image_bytes),
        sha256=hashlib.sha256(image_bytes).hexdigest(),
    )
    session.add(row)
    await session.flush()

    storage_key = user_photo_key(current_user.tg_user_id, str(row.id), filename=filename)
    await storage.put_bytes(storage_key, image_bytes, content_type=content_type)
    row.storage_key = storage_key

    user_settings = await ensure_user_settings(session, user_id=current_user.id, default_provider=settings.ai_provider_default)
    user_settings.active_user_photo_id = row.id

    await session.commit()
    stored_count = await session.scalar(
        select(func.count(UserPhoto.id)).where(UserPhoto.user_id == current_user.id, UserPhoto.deleted_at.is_(None))
    )
    return UserPhotoCreateResponse(
        photo_id=row.id,
        active_user_photo_id=user_settings.active_user_photo_id,
        stored_count=int(stored_count or 0),
    )


@router.post('/me/photos/{photo_id}/activate', response_model=MeResponse)
async def activate_user_photo(
    photo_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    settings=Depends(get_settings),
) -> MeResponse:
    photo = await get_user_photo_for_user(session, user_photo_id=photo_id, user_id=current_user.id)
    user_settings = await ensure_user_settings(session, user_id=current_user.id, default_provider=settings.ai_provider_default)
    user_settings.active_user_photo_id = photo.id
    await session.commit()
    await session.refresh(current_user)
    return await _build_me_response(session, current_user)


@router.delete('/me/photos/{photo_id}', response_model=MeResponse)
async def delete_user_photo(
    photo_id: int,
    session: AsyncSession = Depends(get_db_session),
    storage: StorageBackend = Depends(get_storage),
    current_user: User = Depends(get_current_user),
    settings=Depends(get_settings),
) -> MeResponse:
    photo = await get_user_photo_for_user(session, user_photo_id=photo_id, user_id=current_user.id)
    await storage.delete(photo.storage_key)
    photo.deleted_at = func.now()

    user_settings = await ensure_user_settings(session, user_id=current_user.id, default_provider=settings.ai_provider_default)
    if user_settings.active_user_photo_id == photo.id:
        user_settings.active_user_photo_id = None

    await session.commit()
    await session.refresh(current_user)
    return await _build_me_response(session, current_user)


@router.delete('/me/photos', response_model=MeResponse)
async def delete_all_user_photos(
    session: AsyncSession = Depends(get_db_session),
    storage: StorageBackend = Depends(get_storage),
    current_user: User = Depends(get_current_user),
    settings=Depends(get_settings),
) -> MeResponse:
    photos = list(
        await session.scalars(select(UserPhoto).where(UserPhoto.user_id == current_user.id, UserPhoto.deleted_at.is_(None)))
    )
    for photo in photos:
        await storage.delete(photo.storage_key)
        photo.deleted_at = func.now()

    user_settings = await ensure_user_settings(session, user_id=current_user.id, default_provider=settings.ai_provider_default)
    user_settings.active_user_photo_id = None

    await session.commit()
    await session.refresh(current_user)
    return await _build_me_response(session, current_user)


@router.get('/meta/providers', response_model=list[ProvidersMetaItem])
async def providers_meta(registry: ProviderRegistry = Depends(get_provider_registry)) -> list[ProvidersMetaItem]:
    items: list[ProvidersMetaItem] = []
    for name in registry.list():
        provider = registry.get(name)
        items.append(
            ProvidersMetaItem(
                name=provider.name,
                video=provider.capabilities.video,
                async_video=provider.capabilities.async_video,
                image_edit=provider.capabilities.image_edit,
            )
        )
    return items
