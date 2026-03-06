"""create core tables

Revision ID: 001_create_core_tables
Revises:
Create Date: 2026-03-06 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_create_core_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tg_user_id', sa.BigInteger(), nullable=False),
        sa.Column('tg_chat_id', sa.BigInteger(), nullable=False),
        sa.Column('panel_message_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tg_user_id'),
    )

    op.create_table(
        'user_photos',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('storage_key', sa.Text(), nullable=False),
        sa.Column('sha256', sa.Text(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(length=255), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'user_settings',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('provider', sa.Text(), server_default='grok', nullable=False),
        sa.Column('language', sa.Text(), nullable=True),
        sa.Column('active_user_photo_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['active_user_photo_id'], ['user_photos.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
    )

    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('parent_job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('provider_model', sa.Text(), nullable=True),
        sa.Column('prompt_version', sa.Text(), server_default='v1.0', nullable=False),
        sa.Column('fit_pref', sa.Text(), nullable=True),
        sa.Column('height_cm', sa.Integer(), nullable=True),
        sa.Column('measurements_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('preset', sa.Integer(), nullable=True),
        sa.Column('product_media_key', sa.Text(), nullable=True),
        sa.Column('user_photo_id', sa.BigInteger(), nullable=True),
        sa.Column('user_media_key', sa.Text(), nullable=True),
        sa.Column('inputs_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('result_image_key', sa.Text(), nullable=True),
        sa.Column('result_video_key', sa.Text(), nullable=True),
        sa.Column('result_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=True),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_attempts', sa.Integer(), server_default='2', nullable=False),
        sa.Column('is_retryable', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('error_code', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("type IN ('tryon_image', 'tryon_video')", name='ck_jobs_type'),
        sa.CheckConstraint(
            "status IN ('created', 'queued', 'running', 'done', 'failed', 'expired')",
            name='ck_jobs_status',
        ),
        sa.CheckConstraint(
            "fit_pref IN ('slim', 'regular', 'oversize') OR fit_pref IS NULL",
            name='ck_jobs_fit_pref',
        ),
        sa.CheckConstraint('progress BETWEEN 0 AND 100 OR progress IS NULL', name='ck_jobs_progress_range'),
        sa.CheckConstraint('preset BETWEEN 1 AND 5 OR preset IS NULL', name='ck_jobs_preset_range'),
        sa.ForeignKeyConstraint(['parent_job_id'], ['jobs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_photo_id'], ['user_photos.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_jobs_user_created_at', 'jobs', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_jobs_status_created_at', 'jobs', ['status', 'created_at'], unique=False)
    op.create_index('ix_jobs_provider_created_at', 'jobs', ['provider', 'created_at'], unique=False)
    op.create_index('ix_jobs_expires_at', 'jobs', ['expires_at'], unique=False)
    op.create_index('ix_jobs_parent_job_id', 'jobs', ['parent_job_id'], unique=False)
    op.create_index('ix_jobs_user_photo_id', 'jobs', ['user_photo_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_jobs_user_photo_id', table_name='jobs')
    op.drop_index('ix_jobs_parent_job_id', table_name='jobs')
    op.drop_index('ix_jobs_expires_at', table_name='jobs')
    op.drop_index('ix_jobs_provider_created_at', table_name='jobs')
    op.drop_index('ix_jobs_status_created_at', table_name='jobs')
    op.drop_index('ix_jobs_user_created_at', table_name='jobs')
    op.drop_table('jobs')
    op.drop_table('user_settings')
    op.drop_table('user_photos')
    op.drop_table('users')
