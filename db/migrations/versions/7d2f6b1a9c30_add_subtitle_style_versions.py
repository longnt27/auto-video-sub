"""add subtitle style versions

Revision ID: 7d2f6b1a9c30
Revises: c4a7e2d91b44
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d2f6b1a9c30"
down_revision: str | Sequence[str] | None = "c4a7e2d91b44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subtitle_style_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("font_id", sa.String(length=64), nullable=False),
        sa.Column("font_family", sa.String(length=160), nullable=False),
        sa.Column("font_license", sa.String(length=64), nullable=False),
        sa.Column("font_size_ppm", sa.Integer(), nullable=False),
        sa.Column("text_color", sa.String(length=7), nullable=False),
        sa.Column("outline_color", sa.String(length=7), nullable=False),
        sa.Column("background_color", sa.String(length=7), nullable=False),
        sa.Column("background_opacity_pct", sa.Integer(), nullable=False),
        sa.Column("outline_millipx", sa.Integer(), nullable=False),
        sa.Column("shadow_millipx", sa.Integer(), nullable=False),
        sa.Column("alignment", sa.String(length=32), nullable=False),
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_version_id"], ["subtitle_style_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_asset_id", "version", name="uq_subtitle_style_media_version"),
    )
    op.create_index(
        "ix_subtitle_style_media_created",
        "subtitle_style_versions",
        ["media_asset_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_subtitle_style_media_created", table_name="subtitle_style_versions")
    op.drop_table("subtitle_style_versions")
