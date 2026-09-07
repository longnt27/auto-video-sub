from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from auto_video_sub_domain.errors import ValidationError

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class SubtitleAlignment(StrEnum):
    CENTER = "center"


@dataclass(frozen=True, slots=True)
class SubtitleStyleDraft:
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

    def validate(self) -> None:
        if not self.font_id.strip() or len(self.font_id) > 64:
            raise ValidationError("Subtitle font ID is invalid", code="SUBTITLE_STYLE_INVALID")
        if not self.font_family.strip() or len(self.font_family) > 160:
            raise ValidationError("Subtitle font family is invalid", code="SUBTITLE_STYLE_INVALID")
        if not self.font_license.strip() or len(self.font_license) > 64:
            raise ValidationError("Subtitle font license is invalid", code="SUBTITLE_STYLE_INVALID")
        if not 3.0 <= self.font_size_pct <= 8.0:
            raise ValidationError(
                "Subtitle font size must be between 3% and 8% of video height",
                code="SUBTITLE_STYLE_INVALID",
            )
        for value in (self.text_color, self.outline_color, self.background_color):
            if _HEX_COLOR.fullmatch(value) is None:
                raise ValidationError(
                    "Subtitle colors must use #RRGGBB format", code="SUBTITLE_STYLE_INVALID"
                )
        if not 0 <= self.background_opacity_pct <= 90:
            raise ValidationError(
                "Subtitle background opacity must be between 0% and 90%",
                code="SUBTITLE_STYLE_INVALID",
            )
        if not 0.0 <= self.outline_px <= 4.0:
            raise ValidationError(
                "Subtitle outline must be between 0px and 4px", code="SUBTITLE_STYLE_INVALID"
            )
        if not 0.0 <= self.shadow_px <= 4.0:
            raise ValidationError(
                "Subtitle shadow must be between 0px and 4px", code="SUBTITLE_STYLE_INVALID"
            )
        if self.alignment is not SubtitleAlignment.CENTER:
            raise ValidationError(
                "Only centered subtitles are supported in the MVP", code="SUBTITLE_STYLE_INVALID"
            )


@dataclass(frozen=True, slots=True)
class SubtitleStyleVersion:
    id: UUID
    project_id: UUID
    media_asset_id: UUID
    version: int
    style: SubtitleStyleDraft
    parent_version_id: UUID | None
    created_by: UUID
    created_at: datetime

    def validate(self) -> None:
        if self.version < 1:
            raise ValidationError(
                "Subtitle style version is invalid", code="SUBTITLE_STYLE_INVALID"
            )
        self.style.validate()
