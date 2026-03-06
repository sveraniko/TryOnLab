import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    tg_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    panel_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    settings: Mapped['UserSettings | None'] = relationship(back_populates='user', uselist=False)
    photos: Mapped[list['UserPhoto']] = relationship(back_populates='user', cascade='all, delete-orphan')
    jobs: Mapped[list['Job']] = relationship(back_populates='user', cascade='all, delete-orphan')


class UserPhoto(Base, SoftDeleteMixin):
    __tablename__ = 'user_photos'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped['User'] = relationship(back_populates='photos')
    active_for_settings: Mapped[list['UserSettings']] = relationship(
        back_populates='active_user_photo', foreign_keys='UserSettings.active_user_photo_id'
    )
    jobs: Mapped[list['Job']] = relationship(back_populates='user_photo')


class UserSettings(Base, TimestampMixin):
    __tablename__ = 'user_settings'

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False, server_default='grok')
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_user_photo_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('user_photos.id', ondelete='SET NULL'), nullable=True
    )

    user: Mapped['User'] = relationship(back_populates='settings')
    active_user_photo: Mapped['UserPhoto | None'] = relationship(
        back_populates='active_for_settings', foreign_keys=[active_user_photo_id]
    )


class Job(Base, TimestampMixin):
    __tablename__ = 'jobs'
    __table_args__ = (
        CheckConstraint("type IN ('tryon_image', 'tryon_video')", name='ck_jobs_type'),
        CheckConstraint(
            "status IN ('created', 'queued', 'running', 'done', 'failed', 'expired')",
            name='ck_jobs_status',
        ),
        CheckConstraint("fit_pref IN ('slim', 'regular', 'oversize') OR fit_pref IS NULL", name='ck_jobs_fit_pref'),
        CheckConstraint('progress BETWEEN 0 AND 100 OR progress IS NULL', name='ck_jobs_progress_range'),
        CheckConstraint('preset BETWEEN 1 AND 5 OR preset IS NULL', name='ck_jobs_preset_range'),
        Index('ix_jobs_user_created_at', 'user_id', 'created_at'),
        Index('ix_jobs_status_created_at', 'status', 'created_at'),
        Index('ix_jobs_provider_created_at', 'provider', 'created_at'),
        Index('ix_jobs_expires_at', 'expires_at'),
        Index('ix_jobs_parent_job_id', 'parent_job_id'),
        Index('ix_jobs_user_photo_id', 'user_photo_id'),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    parent_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False, server_default='v1.0')
    fit_pref: Mapped[str | None] = mapped_column(Text, nullable=True)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    measurements_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    preset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_media_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_photo_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('user_photos.id', ondelete='SET NULL'), nullable=True
    )
    user_media_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    inputs_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result_image_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_video_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default='2')
    is_retryable: Mapped[bool] = mapped_column(nullable=False, server_default='false')
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped['User'] = relationship(back_populates='jobs')
    parent_job: Mapped['Job | None'] = relationship(remote_side=[id], back_populates='child_jobs')
    child_jobs: Mapped[list['Job']] = relationship(back_populates='parent_job')
    user_photo: Mapped['UserPhoto | None'] = relationship(back_populates='jobs')
