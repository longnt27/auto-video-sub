from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from auto_video_sub_application.subtitle_style import (
    DEFAULT_SUBTITLE_STYLE,
    FONT_CATALOG,
    SubtitleStyleService,
)
from auto_video_sub_domain import SubtitleAlignment, SubtitleStyleDraft, SubtitleStyleVersion, ValidationError


class MemoryStyleRepository:
    def __init__(self) -> None:
        self.current: SubtitleStyleVersion | None = None
        self.saved_style: SubtitleStyleDraft | None = None

    async def get_or_create_default(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        default_style: SubtitleStyleDraft,
    ) -> SubtitleStyleVersion:
        if self.current is None:
            self.current = SubtitleStyleVersion(
                id=uuid4(),
                project_id=project_id,
                media_asset_id=media_asset_id,
                version=1,
                style=default_style,
                parent_version_id=None,
                created_by=owner_id,
                created_at=datetime.now(UTC),
            )
        return self.current

    async def create_version(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
        style: SubtitleStyleDraft,
    ) -> SubtitleStyleVersion:
        if self.current is None or self.current.version != expected_version:
            raise AssertionError("test repository version mismatch")
        self.saved_style = style
        self.current = SubtitleStyleVersion(
            id=uuid4(),
            project_id=project_id,
            media_asset_id=media_asset_id,
            version=expected_version + 1,
            style=style,
            parent_version_id=self.current.id,
            created_by=owner_id,
            created_at=datetime.now(UTC),
        )
        return self.current


@pytest.mark.asyncio
async def test_default_style_and_font_catalog_are_pinned() -> None:
    repository = MemoryStyleRepository()
    service = SubtitleStyleService(repository)
    result = await service.get(
        owner_id=uuid4(), project_id=uuid4(), media_asset_id=uuid4()
    )

    assert result.style == DEFAULT_SUBTITLE_STYLE
    assert FONT_CATALOG[0].id == "noto-sans"
    assert FONT_CATALOG[0].license == "OFL-1.1"


@pytest.mark.asyncio
async def test_save_creates_new_style_version_without_provider_or_render_dependency() -> None:
    repository = MemoryStyleRepository()
    service = SubtitleStyleService(repository)
    owner_id, project_id, media_asset_id = uuid4(), uuid4(), uuid4()
    current = await service.get(
        owner_id=owner_id, project_id=project_id, media_asset_id=media_asset_id
    )

    result = await service.save(
        owner_id=owner_id,
        project_id=project_id,
        media_asset_id=media_asset_id,
        expected_version=current.version,
        font_id="noto-sans",
        font_size_pct=6.0,
        text_color="#ffffff",
        outline_color="#111111",
        background_color="#000000",
        background_opacity_pct=35,
        outline_px=2.5,
        shadow_px=1.5,
        alignment=SubtitleAlignment.CENTER,
    )

    assert result.version == 2
    assert result.parent_version_id == current.id
    assert repository.saved_style == replace(
        DEFAULT_SUBTITLE_STYLE,
        font_size_pct=6.0,
        text_color="#FFFFFF",
        outline_color="#111111",
        background_opacity_pct=35,
        outline_px=2.5,
        shadow_px=1.5,
    )


@pytest.mark.asyncio
async def test_save_rejects_unapproved_font() -> None:
    repository = MemoryStyleRepository()
    service = SubtitleStyleService(repository)

    with pytest.raises(ValidationError) as error:
        await service.save(
            owner_id=uuid4(),
            project_id=uuid4(),
            media_asset_id=uuid4(),
            expected_version=1,
            font_id="arbitrary-upload.ttf",
            font_size_pct=5.0,
            text_color="#FFFFFF",
            outline_color="#000000",
            background_color="#000000",
            background_opacity_pct=0,
            outline_px=2.0,
            shadow_px=1.0,
            alignment=SubtitleAlignment.CENTER,
        )

    assert error.value.code == "SUBTITLE_FONT_NOT_APPROVED"
