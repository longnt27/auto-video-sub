from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from auto_video_sub_infrastructure.models import Base


class RenderJobModel(Base):
    __tablename__ = "render_jobs"
    __table_args__ = (
        UniqueConstraint(
            "media_asset_id", "input_fingerprint", name="uq_render_media_fingerprint"
        ),
        Index("ix_render_project_updated", "project_id", "updated_at"),
        CheckConstraint(
            "original_audio_gain_ppm >= 0 AND original_audio_gain_ppm <= 1000000",
            name="ck_render_audio_gain_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    audio_policy: Mapped[str] = mapped_column(String(32), nullable=False)
    original_audio_gain_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(160), nullable=False)
    font_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    font_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_payload: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    manifest_artifact_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    subtitle_artifact_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    output_artifact_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    validation_artifact_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    validation_summary: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
