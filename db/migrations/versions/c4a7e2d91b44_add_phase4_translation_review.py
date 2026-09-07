"""add phase4 translation review

Revision ID: c4a7e2d91b44
Revises: 8f1d5e9c3a21
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4a7e2d91b44"
down_revision: str | Sequence[str] | None = "8f1d5e9c3a21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "translation_budget_accounts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("max_cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("reserved_cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("used_cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("max_cost_micros >= 0", name="ck_translation_budget_max_nonnegative"),
        sa.CheckConstraint("reserved_cost_micros >= 0", name="ck_translation_budget_reserved_nonnegative"),
        sa.CheckConstraint("used_cost_micros >= 0", name="ck_translation_budget_used_nonnegative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "translation_policy_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("preset", sa.String(length=32), nullable=False),
        sa.Column("prompt_version", sa.String(length=96), nullable=False),
        sa.Column("prompt_checksum", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version", name="uq_translation_policy_project_version"),
    )
    op.create_index("ix_translation_policy_project_created", "translation_policy_versions", ["project_id", "created_at"], unique=False)
    op.create_table(
        "context_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("transcript_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(length=20000), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_version_id"], ["context_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_asset_id", "version", name="uq_context_media_version"),
    )
    op.create_index("ix_context_media_created", "context_versions", ["media_asset_id", "created_at"], unique=False)
    op.create_table(
        "context_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("context_version_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("source_forms", JSON_VALUE, nullable=False),
        sa.Column("preferred_vietnamese", sa.String(length=400), nullable=True),
        sa.Column("confidence_ppm", sa.Integer(), nullable=False),
        sa.Column("ambiguous", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("evidence_segment_ids", JSON_VALUE, nullable=False),
        sa.ForeignKeyConstraint(["context_version_id"], ["context_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_context_entity_version", "context_entities", ["context_version_id"], unique=False)
    op.create_table(
        "translation_states",
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("transcript_version", sa.Integer(), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("context_version_id", sa.Uuid(), nullable=True),
        sa.Column("workflow_id", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=96), nullable=True),
        sa.Column("estimated_cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("reserved_cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("actual_cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("findings", JSON_VALUE, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["context_version_id"], ["context_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_version_id"], ["translation_policy_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("media_asset_id"),
    )
    op.create_index("ix_translation_project_updated", "translation_states", ["project_id", "updated_at"], unique=False)
    op.create_table(
        "translation_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("owned_segment_ids", JSON_VALUE, nullable=False),
        sa.Column("overlap_segment_ids", JSON_VALUE, nullable=False),
        sa.Column("context_version_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["context_version_id"], ["context_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_version_id"], ["translation_policy_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_version_id", "ordinal", name="uq_translation_batch_policy_ordinal"),
    )
    op.create_index("ix_translation_batch_media", "translation_batches", ["media_asset_id", "ordinal"], unique=False)
    op.create_table(
        "translation_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subtitle_segment_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=4000), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("context_version_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=160), nullable=True),
        sa.Column("prompt_version", sa.String(length=96), nullable=True),
        sa.Column("editor_id", sa.Uuid(), nullable=True),
        sa.Column("parent_revision_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["context_version_id"], ["context_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_revision_id"], ["translation_revisions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["policy_version_id"], ["translation_policy_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subtitle_segment_id"], ["subtitle_segments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subtitle_segment_id", "version", name="uq_translation_revision_version"),
    )
    op.create_index("ix_translation_revision_segment_created", "translation_revisions", ["subtitle_segment_id", "created_at"], unique=False)
    op.create_table(
        "segment_translation_heads",
        sa.Column("subtitle_segment_id", sa.Uuid(), nullable=False),
        sa.Column("translation_revision_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["subtitle_segment_id"], ["subtitle_segments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["translation_revision_id"], ["translation_revisions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("subtitle_segment_id"),
    )
    op.create_table(
        "translation_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("stage_name", sa.String(length=96), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_version_id"], ["translation_policy_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_translation_usage_media_created", "translation_usage", ["media_asset_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_translation_usage_media_created", table_name="translation_usage")
    op.drop_table("translation_usage")
    op.drop_table("segment_translation_heads")
    op.drop_index("ix_translation_revision_segment_created", table_name="translation_revisions")
    op.drop_table("translation_revisions")
    op.drop_index("ix_translation_batch_media", table_name="translation_batches")
    op.drop_table("translation_batches")
    op.drop_index("ix_translation_project_updated", table_name="translation_states")
    op.drop_table("translation_states")
    op.drop_index("ix_context_entity_version", table_name="context_entities")
    op.drop_table("context_entities")
    op.drop_index("ix_context_media_created", table_name="context_versions")
    op.drop_table("context_versions")
    op.drop_index("ix_translation_policy_project_created", table_name="translation_policy_versions")
    op.drop_table("translation_policy_versions")
    op.drop_table("translation_budget_accounts")
