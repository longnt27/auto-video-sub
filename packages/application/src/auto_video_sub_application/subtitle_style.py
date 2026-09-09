from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from auto_video_sub_domain import (
    SubtitleAlignment,
    SubtitleStyleDraft,
    SubtitleStyleVersion,
    ValidationError,
)


@dataclass(frozen=True, slots=True)
class SubtitleFontDefinition:
    id: str
    family: str
    license: str


# These are runtime/system font aliases, not files users must download or mount.
# fontconfig resolves them inside the render worker; the image includes baseline
# font packages so all three generic families work out of the box.
FONT_CATALOG: tuple[SubtitleFontDefinition, ...] = (
    SubtitleFontDefinition(id="system-sans", family="sans-serif", license="system"),
    SubtitleFontDefinition(id="system-serif", family="serif", license="system"),
    SubtitleFontDefinition(id="system-monospace", family="monospace", license="system"),
)

DEFAULT_SUBTITLE_STYLE = SubtitleStyleDraft(
    font_id="system-sans",
    font_family="sans-serif",
    font_license="system",
    font_size_pct=5.0,
    text_color="#FFFFFF",
    outline_color="#000000",
    background_color="#000000",
    background_opacity_pct=0,
    outline_px=2.0,
    shadow_px=1.0,
    alignment=SubtitleAlignment.CENTER,
)


class SubtitleStyleRepository(Protocol):
    async def get_or_create_default(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        default_style: SubtitleStyleDraft,
    ) -> SubtitleStyleVersion: ...

    async def create_version(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
        style: SubtitleStyleDraft,
    ) -> SubtitleStyleVersion: ...


class SubtitleStyleService:
    def __init__(self, repository: SubtitleStyleRepository) -> None:
        self._repository = repository

    @staticmethod
    def font_catalog() -> tuple[SubtitleFontDefinition, ...]:
        return FONT_CATALOG

    async def get(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> SubtitleStyleVersion:
        return await self._repository.get_or_create_default(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
            default_style=DEFAULT_SUBTITLE_STYLE,
        )

    async def save(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
        font_id: str,
        font_size_pct: float,
        text_color: str,
        outline_color: str,
        background_color: str,
        background_opacity_pct: int,
        outline_px: float,
        shadow_px: float,
        alignment: SubtitleAlignment,
    ) -> SubtitleStyleVersion:
        if expected_version < 1:
            raise ValidationError(
                "Expected subtitle style version is invalid", code="VERSION_INVALID"
            )
        font = next((item for item in FONT_CATALOG if item.id == font_id), None)
        if font is None:
            raise ValidationError(
                "Subtitle system font is not supported", code="SUBTITLE_FONT_NOT_APPROVED"
            )
        style = SubtitleStyleDraft(
            font_id=font.id,
            font_family=font.family,
            font_license=font.license,
            font_size_pct=font_size_pct,
            text_color=text_color.upper(),
            outline_color=outline_color.upper(),
            background_color=background_color.upper(),
            background_opacity_pct=background_opacity_pct,
            outline_px=outline_px,
            shadow_px=shadow_px,
            alignment=alignment,
        )
        style.validate()
        return await self._repository.create_version(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
            expected_version=expected_version,
            style=style,
        )
