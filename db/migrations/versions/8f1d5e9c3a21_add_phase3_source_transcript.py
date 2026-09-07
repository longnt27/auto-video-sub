"""add phase3 source transcript

Revision ID: 8f1d5e9c3a21
Revises: 1b105fb342a2
Create Date: 2026-09-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "8f1d5e9c3a21"
down_revision: str | Sequence[str] | None = "1b105fb342a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transcript_states",
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("region_config", sa.JSON(), nullable=False),
        sa.Column("workflow_id", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=96), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("media_asset_id"),
    )
    op.create_index(
        "ix_transcript_project_updated",
        "transcript_states",
        ["project_id", "updated_at"],
        unique=False,
    )
    op.create_table(
        "ocr_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("time_us", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.String(length=2000), nullable=False),
        sa.Column("confidence_ppm", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=96), nullable=False),
        sa.Column("model_version", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence_ppm >= 0 AND confidence_ppm <= 1000000",
            name="ck_ocr_confidence_range",
        ),
        sa.CheckConstraint("time_us >= 0", name="ck_ocr_time_nonnegative"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ocr_media_time", "ocr_observations", ["media_asset_id", "time_us"], unique=False
    )
    op.create_table(
        "subtitle_segments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("start_us", sa.BigInteger(), nullable=False),
        sa.Column("end_us", sa.BigInteger(), nullable=False),
        sa.Column("current_source_revision_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_us > start_us", name="ck_segment_timing_valid"),
        sa.CheckConstraint("ordinal >= 0", name="ck_segment_ordinal_nonnegative"),
        sa.CheckConstraint("start_us >= 0", name="ck_segment_start_nonnegative"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_asset_id", "ordinal", name="uq_segment_media_ordinal"),
    )
    op.create_index(
        "ix_segment_project_media",
        "subtitle_segments",
        ["project_id", "media_asset_id", "ordinal"],
        unique=False,
    )
    op.create_table(
        "source_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subtitle_segment_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=4000), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("confidence_ppm", sa.Integer(), nullable=True),
        sa.Column("editor_id", sa.Uuid(), nullable=True),
        sa.Column("parent_revision_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence_ppm IS NULL OR (confidence_ppm >= 0 AND confidence_ppm <= 1000000)",
            name="ck_source_revision_confidence_range",
        ),
        sa.CheckConstraint("version > 0", name="ck_source_revision_version_positive"),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["parent_revision_id"], ["source_revisions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["subtitle_segment_id"], ["subtitle_segments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subtitle_segment_id", "version", name="uq_source_revision_version"),
    )
    op.create_index(
        "ix_source_revision_segment_created",
        "source_revisions",
        ["subtitle_segment_id", "created_at"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_segment_current_source_revision",
        "subtitle_segments",
        "source_revisions",
        ["current_source_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_segment_current_source_revision", "subtitle_segments", type_="foreignkey"
    )
    op.drop_index("ix_source_revision_segment_created", table_name="source_revisions")
    op.drop_table("source_revisions")
    op.drop_index("ix_segment_project_media", table_name="subtitle_segments")
    op.drop_table("subtitle_segments")
    op.drop_index("ix_ocr_media_time", table_name="ocr_observations")
    op.drop_table("ocr_observations")
    op.drop_index("ix_transcript_project_updated", table_name="transcript_states")
    op.drop_table("transcript_states")
