"""add phase6 render jobs

Revision ID: 9a31c7d4e2b8
Revises: e61a4c8d2f90
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9a31c7d4e2b8"
down_revision: str | Sequence[str] | None = "e61a4c8d2f90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "render_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("workflow_id", sa.String(length=255), nullable=True),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("audio_policy", sa.String(length=32), nullable=False),
        sa.Column("original_audio_gain_ppm", sa.Integer(), nullable=False),
        sa.Column("renderer_version", sa.String(length=160), nullable=False),
        sa.Column("font_filename", sa.String(length=255), nullable=False),
        sa.Column("font_checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("manifest_payload", JSON_VALUE, nullable=False),
        sa.Column("manifest_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("subtitle_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("output_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("validation_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("validation_summary", JSON_VALUE, nullable=True),
        sa.Column("error_code", sa.String(length=96), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "original_audio_gain_ppm >= 0 AND original_audio_gain_ppm <= 1000000",
            name="ck_render_audio_gain_range",
        ),
        sa.ForeignKeyConstraint(["manifest_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["output_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subtitle_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["validation_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "media_asset_id", "input_fingerprint", name="uq_render_media_fingerprint"
        ),
    )
    op.create_index(
        "ix_render_project_updated",
        "render_jobs",
        ["project_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_render_project_updated", table_name="render_jobs")
    op.drop_table("render_jobs")
