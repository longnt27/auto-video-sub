"""use system font families for render

Revision ID: b7f4c9a2d610
Revises: 9a31c7d4e2b8
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7f4c9a2d610"
down_revision: str | Sequence[str] | None = "9a31c7d4e2b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Preserve the old Noto selection as a real family name before the column is repurposed.
    op.execute(
        "UPDATE render_jobs SET font_filename = 'Noto Sans' "
        "WHERE font_filename = 'NotoSans-Regular.ttf'"
    )
    op.alter_column(
        "render_jobs",
        "font_filename",
        new_column_name="font_family",
        existing_type=sa.String(length=255),
        type_=sa.String(length=160),
        existing_nullable=False,
    )
    op.drop_column("render_jobs", "font_checksum_sha256")


def downgrade() -> None:
    op.alter_column(
        "render_jobs",
        "font_family",
        new_column_name="font_filename",
        existing_type=sa.String(length=160),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.add_column(
        "render_jobs",
        sa.Column(
            "font_checksum_sha256",
            sa.String(length=64),
            nullable=False,
            server_default="0" * 64,
        ),
    )
    op.alter_column("render_jobs", "font_checksum_sha256", server_default=None)
