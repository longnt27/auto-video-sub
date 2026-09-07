"""add phase5 speech fitting

Revision ID: e61a4c8d2f90
Revises: 7d2f6b1a9c30
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e61a4c8d2f90"
down_revision: str | Sequence[str] | None = "7d2f6b1a9c30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "speech_states",
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("workflow_id", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=96), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("model_revision", sa.String(length=160), nullable=False),
        sa.Column("voice_id", sa.String(length=160), nullable=False),
        sa.Column("policy_version", sa.String(length=96), nullable=False),
        sa.Column("tolerance_us", sa.BigInteger(), nullable=False),
        sa.Column("max_speed_factor_ppm", sa.Integer(), nullable=False),
        sa.Column("max_rewrite_attempts", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("media_asset_id"),
    )
    op.create_index(
        "ix_speech_project_updated",
        "speech_states",
        ["project_id", "updated_at"],
        unique=False,
    )
    op.create_table(
        "speech_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("subtitle_segment_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column("parent_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("translation_revision_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.String(length=4000), nullable=False),
        sa.Column("text_origin", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("model_revision", sa.String(length=160), nullable=False),
        sa.Column("voice_id", sa.String(length=160), nullable=False),
        sa.Column("policy_version", sa.String(length=96), nullable=False),
        sa.Column("idempotency_key", sa.String(length=512), nullable=False),
        sa.Column("raw_audio_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("trimmed_audio_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("final_audio_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("envelope_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("measured_duration_us", sa.BigInteger(), nullable=True),
        sa.Column("trimmed_duration_us", sa.BigInteger(), nullable=True),
        sa.Column("final_duration_us", sa.BigInteger(), nullable=True),
        sa.Column("silence_removed_us", sa.BigInteger(), nullable=False),
        sa.Column("speed_factor_ppm", sa.Integer(), nullable=False),
        sa.Column("slot_us", sa.BigInteger(), nullable=False),
        sa.Column("tolerance_us", sa.BigInteger(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=True),
        sa.Column("error_code", sa.String(length=96), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt_index >= 0", name="ck_speech_attempt_index_nonnegative"),
        sa.CheckConstraint("slot_us > 0", name="ck_speech_attempt_slot_positive"),
        sa.CheckConstraint("speed_factor_ppm >= 1000000", name="ck_speech_attempt_speed_minimum"),
        sa.CheckConstraint("tolerance_us >= 0", name="ck_speech_attempt_tolerance_nonnegative"),
        sa.ForeignKeyConstraint(["envelope_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["final_audio_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_attempt_id"], ["speech_attempts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["raw_audio_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["subtitle_segment_id"], ["subtitle_segments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["translation_revision_id"], ["translation_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["trimmed_audio_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_speech_attempt_idempotency"),
        sa.UniqueConstraint(
            "subtitle_segment_id",
            "translation_revision_id",
            "attempt_index",
            "provider",
            "model",
            "model_revision",
            "voice_id",
            "policy_version",
            name="uq_speech_attempt_generation_index",
        ),
    )
    op.create_index(
        "ix_speech_attempt_media_segment",
        "speech_attempts",
        ["media_asset_id", "subtitle_segment_id"],
        unique=False,
    )
    op.create_table(
        "speech_segment_states",
        sa.Column("subtitle_segment_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("translation_revision_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["current_attempt_id"], ["speech_attempts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subtitle_segment_id"], ["subtitle_segments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["translation_revision_id"], ["translation_revisions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("subtitle_segment_id"),
    )
    op.create_index(
        "ix_speech_segment_media_status",
        "speech_segment_states",
        ["media_asset_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_speech_segment_media_status", table_name="speech_segment_states")
    op.drop_table("speech_segment_states")
    op.drop_index("ix_speech_attempt_media_segment", table_name="speech_attempts")
    op.drop_table("speech_attempts")
    op.drop_index("ix_speech_project_updated", table_name="speech_states")
    op.drop_table("speech_states")
