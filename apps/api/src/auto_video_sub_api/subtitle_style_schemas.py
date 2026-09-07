from __future__ import annotations

from datetime import datetime
from uuid import UUID

from auto_video_sub_domain import SubtitleAlignment, SubtitleStyleVersion
from pydantic import BaseModel, ConfigDict, Field


class SubtitleFontResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    family: str
    license: str


class SubtitleStyleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    media_asset_id: UUID
    version: int
    font_id: str
    font_family: str
    font_license: str
    font_size_pct: float
    text_color: str
    outline_color: str
    background_color: str
    background_opacity_pct: int
    outline_px: float
    shadow_px: float
    alignment: SubtitleAlignment
    parent_version_id: UUID | None
    created_by: UUID
    created_at: datetime

    @classmethod
    def from_domain(cls, value: SubtitleStyleVersion) -> SubtitleStyleResponse:
        return cls(
            id=value.id,
            project_id=value.project_id,
            media_asset_id=value.media_asset_id,
            version=value.version,
            font_id=value.style.font_id,
            font_family=value.style.font_family,
            font_license=value.style.font_license,
            font_size_pct=value.style.font_size_pct,
            text_color=value.style.text_color,
            outline_color=value.style.outline_color,
            background_color=value.style.background_color,
            background_opacity_pct=value.style.background_opacity_pct,
            outline_px=value.style.outline_px,
            shadow_px=value.style.shadow_px,
            alignment=value.style.alignment,
            parent_version_id=value.parent_version_id,
            created_by=value.created_by,
            created_at=value.created_at,
        )


class SaveSubtitleStyleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    font_id: str = Field(min_length=1, max_length=64)
    font_size_pct: float = Field(ge=3.0, le=8.0)
    text_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    outline_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    background_opacity_pct: int = Field(ge=0, le=90)
    outline_px: float = Field(ge=0.0, le=4.0)
    shadow_px: float = Field(ge=0.0, le=4.0)
    alignment: SubtitleAlignment = SubtitleAlignment.CENTER
