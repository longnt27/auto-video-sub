from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from auto_video_sub_infrastructure.models import Base


class TranslationBudgetAccountModel(Base):
    __tablename__ = "translation_budget_accounts"
    __table_args__ = (
        CheckConstraint("max_cost_micros >= 0", name="ck_translation_budget_max_nonnegative"),
        CheckConstraint("reserved_cost_micros >= 0", name="ck_translation_budget_reserved_nonnegative"),
        CheckConstraint("used_cost_micros >= 0", name="ck_translation_budget_used_nonnegative"),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    max_cost_micros: Mapped[int] = mapped_column(BigInteger)
    reserved_cost_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    used_cost_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TranslationPolicyVersionModel(Base):
    __tablename__ = "translation_policy_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_translation_policy_project_version"),
        Index("ix_translation_policy_project_created", "project_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    preset: Mapped[str] = mapped_column(String(32))
    prompt_version: Mapped[str] = mapped_column(String(96))
    prompt_checksum: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContextVersionModel(Base):
    __tablename__ = "context_versions"
    __table_args__ = (
        UniqueConstraint("media_asset_id", "version", name="uq_context_media_version"),
        Index("ix_context_media_created", "media_asset_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    media_asset_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False)
    transcript_version: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(String(20000))
    approved: Mapped[bool] = mapped_column(default=False)
    parent_version_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("context_versions.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContextEntityModel(Base):
    __tablename__ = "context_entities"
    __table_args__ = (Index("ix_context_entity_version", "context_version_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    context_version_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("context_versions.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(64))
    source_forms: Mapped[dict[str, Any]] = mapped_column()
    preferred_vietnamese: Mapped[str | None] = mapped_column(String(400), nullable=True)
    confidence_ppm: Mapped[int] = mapped_column(Integer)
    ambiguous: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    evidence_segment_ids: Mapped[dict[str, Any]] = mapped_column()


class TranslationStateModel(Base):
    __tablename__ = "translation_states"
    __table_args__ = (Index("ix_translation_project_updated", "project_id", "updated_at"),)

    media_asset_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(40))
    transcript_version: Mapped[int] = mapped_column(Integer)
    policy_version_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("translation_policy_versions.id", ondelete="RESTRICT"), nullable=False)
    context_version_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("context_versions.id", ondelete="RESTRICT"), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    estimated_cost_micros: Mapped[int] = mapped_column(BigInteger)
    reserved_cost_micros: Mapped[int] = mapped_column(BigInteger)
    actual_cost_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    findings: Mapped[dict[str, Any]] = mapped_column(default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TranslationBatchModel(Base):
    __tablename__ = "translation_batches"
    __table_args__ = (
        UniqueConstraint("policy_version_id", "ordinal", name="uq_translation_batch_policy_ordinal"),
        Index("ix_translation_batch_media", "media_asset_id", "ordinal"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    media_asset_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer)
    owned_segment_ids: Mapped[dict[str, Any]] = mapped_column()
    overlap_segment_ids: Mapped[dict[str, Any]] = mapped_column()
    context_version_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("context_versions.id", ondelete="RESTRICT"), nullable=False)
    policy_version_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("translation_policy_versions.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TranslationRevisionModel(Base):
    __tablename__ = "translation_revisions"
    __table_args__ = (
        UniqueConstraint("subtitle_segment_id", "version", name="uq_translation_revision_version"),
        Index("ix_translation_revision_segment_created", "subtitle_segment_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    subtitle_segment_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("subtitle_segments.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(String(4000))
    origin: Mapped[str] = mapped_column(String(32))
    context_version_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("context_versions.id", ondelete="RESTRICT"), nullable=False)
    policy_version_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("translation_policy_versions.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(96), nullable=True)
    editor_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    parent_revision_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("translation_revisions.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SegmentTranslationHeadModel(Base):
    __tablename__ = "segment_translation_heads"

    subtitle_segment_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("subtitle_segments.id", ondelete="CASCADE"), primary_key=True)
    translation_revision_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("translation_revisions.id", ondelete="RESTRICT"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TranslationUsageModel(Base):
    __tablename__ = "translation_usage"
    __table_args__ = (Index("ix_translation_usage_media_created", "media_asset_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    media_asset_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False)
    policy_version_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("translation_policy_versions.id", ondelete="RESTRICT"), nullable=False)
    stage_name: Mapped[str] = mapped_column(String(96))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(160))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cost_micros: Mapped[int] = mapped_column(BigInteger)
    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
