from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[object, object]] = {
        dict[str, Any]: JSON().with_variant(JSONB(), "postgresql")
    }


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    external_login: Mapped[str] = mapped_column(String(320), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuotaAccountModel(Base):
    __tablename__ = "quota_accounts"
    __table_args__ = (
        CheckConstraint("max_storage_bytes > 0", name="ck_quota_max_storage_positive"),
        CheckConstraint("reserved_storage_bytes >= 0", name="ck_quota_reserved_nonnegative"),
        CheckConstraint("used_storage_bytes >= 0", name="ck_quota_used_nonnegative"),
        CheckConstraint("active_uploads >= 0", name="ck_quota_active_uploads_nonnegative"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    max_projects: Mapped[int] = mapped_column(Integer)
    max_concurrent_uploads: Mapped[int] = mapped_column(Integer)
    max_storage_bytes: Mapped[int] = mapped_column(BigInteger)
    reserved_storage_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    used_storage_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    active_uploads: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectModel(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_projects_owner_idempotency"),
        Index("ix_projects_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(160))
    lifecycle: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MediaAssetModel(Base):
    __tablename__ = "media_assets"
    __table_args__ = (Index("ix_media_project_created", "project_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))
    original_artifact_id: Mapped[UUID] = mapped_column(Uuid)
    proxy_artifact_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    probe: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UploadIntentModel(Base):
    __tablename__ = "upload_intents"
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key", name="uq_upload_project_idempotency"),
        UniqueConstraint("media_asset_id", name="uq_upload_media_asset"),
        Index("ix_upload_expires_state", "expires_at", "state"),
        CheckConstraint("declared_size_bytes > 0", name="ck_upload_size_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    original_artifact_id: Mapped[UUID] = mapped_column(Uuid)
    staging_object_key: Mapped[str] = mapped_column(String(512), unique=True)
    sealed_object_key: Mapped[str] = mapped_column(String(512), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    declared_content_type: Mapped[str] = mapped_column(String(128))
    declared_size_bytes: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArtifactModel(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_artifact_object_key"),
        CheckConstraint("byte_size > 0", name="ck_artifact_size_positive"),
        Index("ix_artifact_project_created", "project_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(64))
    media_type: Mapped[str] = mapped_column(String(128))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    object_key: Mapped[str] = mapped_column(String(512))
    retention_class: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32))
    producer_stage_execution_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArtifactEdgeModel(Base):
    __tablename__ = "artifact_edges"
    __table_args__ = (
        UniqueConstraint(
            "parent_artifact_id", "child_artifact_id", "relation", name="uq_artifact_edge"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    parent_artifact_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False
    )
    child_artifact_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StageExecutionModel(Base):
    __tablename__ = "stage_executions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "stage_name", "attempt", name="uq_stage_workflow_attempt"),
        UniqueConstraint("idempotency_key", "attempt", name="uq_stage_idempotency_attempt"),
        Index("ix_stage_project_started", "project_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[str] = mapped_column(String(255))
    stage_name: Mapped[str] = mapped_column(String(96))
    scope_id: Mapped[str] = mapped_column(String(255))
    idempotency_key: Mapped[str] = mapped_column(String(512))
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    attempt: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    retryable: Mapped[bool | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TranscriptStateModel(Base):
    __tablename__ = "transcript_states"
    __table_args__ = (Index("ix_transcript_project_updated", "project_id", "updated_at"),)

    media_asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32))
    region_config: Mapped[dict[str, Any]] = mapped_column()
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OcrObservationModel(Base):
    __tablename__ = "ocr_observations"
    __table_args__ = (
        Index("ix_ocr_media_time", "media_asset_id", "time_us"),
        CheckConstraint("time_us >= 0", name="ck_ocr_time_nonnegative"),
        CheckConstraint(
            "confidence_ppm >= 0 AND confidence_ppm <= 1000000",
            name="ck_ocr_confidence_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    time_us: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(String(2000))
    confidence_ppm: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(96))
    model_version: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SubtitleSegmentModel(Base):
    __tablename__ = "subtitle_segments"
    __table_args__ = (
        UniqueConstraint("media_asset_id", "ordinal", name="uq_segment_media_ordinal"),
        Index("ix_segment_project_media", "project_id", "media_asset_id", "ordinal"),
        CheckConstraint("ordinal >= 0", name="ck_segment_ordinal_nonnegative"),
        CheckConstraint("start_us >= 0", name="ck_segment_start_nonnegative"),
        CheckConstraint("end_us > start_us", name="ck_segment_timing_valid"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    start_us: Mapped[int] = mapped_column(BigInteger)
    end_us: Mapped[int] = mapped_column(BigInteger)
    current_source_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "source_revisions.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_segment_current_source_revision",
        ),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceRevisionModel(Base):
    __tablename__ = "source_revisions"
    __table_args__ = (
        UniqueConstraint("subtitle_segment_id", "version", name="uq_source_revision_version"),
        Index("ix_source_revision_segment_created", "subtitle_segment_id", "created_at"),
        CheckConstraint("version > 0", name="ck_source_revision_version_positive"),
        CheckConstraint(
            "confidence_ppm IS NULL OR (confidence_ppm >= 0 AND confidence_ppm <= 1000000)",
            name="ck_source_revision_confidence_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    subtitle_segment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("subtitle_segments.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(String(4000))
    origin: Mapped[str] = mapped_column(String(32))
    confidence_ppm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    editor_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    parent_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("source_revisions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
