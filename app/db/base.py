from datetime import datetime

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class TimestampMixin:
    """Common created/updated timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDeleteMixin:
    """Soft-delete fields for user-managed media entities."""

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default='false')
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
