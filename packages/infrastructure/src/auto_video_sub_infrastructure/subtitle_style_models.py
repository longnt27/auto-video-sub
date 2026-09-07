from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from auto_video_sub_infrastructure.models import Base


class SubtitleStyleVersionModel(Base):
    __tablename__ = "subtitle_style_versions"
    __table_args__ = (
        UniqueConstraint("media_asset_id", "version", name="uq_subtitle_style_media_version"),
        Index("ix_subtitle_style_media_created", "media_asset_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    font_id: Mapped[str] = mapped_column(String(64), nullable=False)
    font_family: Mapped[str] = mapped_column(String(160), nullable=False)
    font_license: Mapped[str] = mapped_column(String(64), nullable=False)
    font_size_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    text_color: Mapped[str] = mapped_column(String(7), nullable=False)
    outline_color: Mapped[str] = mapped_column(String(7), nullable=False)
    background_color: Mapped[str] = mapped_column(String(7), nullable=False)
    background_opacity_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    outline_millipx: Mapped[int] = mapped_column(Integer, nullable=False)
    shadow_millipx: Mapped[int] = mapped_column(Integer, nullable=False)
    alignment: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("subtitle_style_versions.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
