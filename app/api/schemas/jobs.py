from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class JobCreateResponse(BaseModel):
    job_id: UUID
    status: str


class JobStatusResponse(BaseModel):
    job_id: UUID
    type: str
    status: str
    progress: int | None
    provider: str
    attempts: int
    max_attempts: int
    result_image_url: str | None = None
    result_video_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class JobRetryResponse(BaseModel):
    job_id: UUID
    status: str
    attempts: int


class VideoJobCreateResponse(BaseModel):
    video_job_id: UUID
    status: str


class JobListItem(BaseModel):
    job_id: UUID
    type: str
    status: str
    provider: str
    preset: int | None
    created_at: datetime


class JobListResponse(BaseModel):
    items: list[JobListItem]
    total: int
