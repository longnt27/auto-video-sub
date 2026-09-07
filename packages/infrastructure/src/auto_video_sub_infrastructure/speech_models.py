from __future__ import annotations

from datetime import datetime
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
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from auto_video_sub_infrastructure.models import Base


class SpeechStateModel(Base):
    __tablename__ = "speech_states"
    __table_args__ = (Index("ix_speech_project_updated", "project_id", "updated_at"),)

    media_asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32))
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(160))
    model_revision: Mapped[str] = mapped_column(String(160))
    voice_id: Mapped[str] = mapped_column(String(160))
    policy_version: Mapped[str] = mapped_column(String(96))
    tolerance_us: Mapped[int] = mapped_column(BigInteger)
    max_speed_factor_ppm: Mapped[int] = mapped_column(Integer)
    max_rewrite_attempts: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SpeechAttemptModel(Base):
    __tablename__ = "speech_attempts"
    __table_args__ = (
        UniqueConstraint(
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
        UniqueConstraint("idempotency_key", name="uq_speech_attempt_idempotency"),
        Index("ix_speech_attempt_media_segment", "media_asset_id", "subtitle_segment_id"),
        CheckConstraint("attempt_index >= 0", name="ck_speech_attempt_index_nonnegative"),
        CheckConstraint("slot_us > 0", name="ck_speech_attempt_slot_positive"),
        CheckConstraint("tolerance_us >= 0", name="ck_speech_attempt_tolerance_nonnegative"),
        CheckConstraint("speed_factor_ppm >= 1000000", name="ck_speech_attempt_speed_minimum"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    subtitle_segment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("subtitle_segments.id", ondelete="CASCADE"), nullable=False
    )
    attempt_index: Mapped[int] = mapped_column(Integer)
    parent_attempt_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("speech_attempts.id", ondelete="SET NULL"), nullable=True
    )
    translation_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("translation_revisions.id", ondelete="RESTRICT"), nullable=False
    )
    text: Mapped[str] = mapped_column(String(4000))
    text_origin: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(160))
    model_revision: Mapped[str] = mapped_column(String(160))
    voice_id: Mapped[str] = mapped_column(String(160))
    policy_version: Mapped[str] = mapped_column(String(96))
    idempotency_key: Mapped[str] = mapped_column(String(512))
    raw_audio_artifact_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    trimmed_audio_artifact_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    final_audio_artifact_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    envelope_artifact_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    measured_duration_us: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trimmed_duration_us: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    final_duration_us: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    silence_removed_us: Mapped[int] = mapped_column(BigInteger, default=0)
    speed_factor_ppm: Mapped[int] = mapped_column(Integer, default=1_000_000)
    slot_us: Mapped[int] = mapped_column(BigInteger)
    tolerance_us: Mapped[int] = mapped_column(BigInteger)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SpeechSegmentStateModel(Base):
    __tablename__ = "speech_segment_states"
    __table_args__ = (Index("ix_speech_segment_media_status", "media_asset_id", "status"),)

    subtitle_segment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("subtitle_segments.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    translation_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("translation_revisions.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32))
    current_attempt_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("speech_attempts.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
