from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MeResponse(BaseModel):
    tg_user_id: int
    tg_chat_id: int
    panel_message_id: int | None
    provider: str
    active_user_photo_id: int | None
    stored_user_photos_count: int


class MePatchRequest(BaseModel):
    panel_message_id: int | None = None
    provider: str | None = None
    active_user_photo_id: int | None = None


class UserPhotoListItem(BaseModel):
    id: int
    created_at: datetime
    is_deleted: bool


class UserPhotoListResponse(BaseModel):
    items: list[UserPhotoListItem]
    total: int


class UserPhotoCreateResponse(BaseModel):
    photo_id: int
    active_user_photo_id: int | None
    stored_count: int


class ProvidersMetaItem(BaseModel):
    name: str
    video: bool
    async_video: bool
    image_edit: bool
