from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from auto_video_sub_api.auth import CurrentUser
from auto_video_sub_api.subtitle_style_schemas import (
    SaveSubtitleStyleRequest,
    SubtitleFontResponse,
    SubtitleStyleResponse,
)

router = APIRouter(prefix="/v1", tags=["subtitle-style"])


@router.get("/subtitle-styles/fonts", response_model=list[SubtitleFontResponse])
async def list_subtitle_fonts(user: CurrentUser, request: Request) -> list[SubtitleFontResponse]:
    del user
    return [
        SubtitleFontResponse(id=item.id, family=item.family, license=item.license)
        for item in request.app.state.subtitle_style_service.font_catalog()
    ]


@router.get(
    "/projects/{project_id}/media/{media_asset_id}/subtitle-style",
    response_model=SubtitleStyleResponse,
)
async def get_subtitle_style(
    project_id: UUID,
    media_asset_id: UUID,
    user: CurrentUser,
    request: Request,
) -> SubtitleStyleResponse:
    value = await request.app.state.subtitle_style_service.get(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
    )
    return SubtitleStyleResponse.from_domain(value)


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/subtitle-style/revisions",
    response_model=SubtitleStyleResponse,
)
async def save_subtitle_style(
    project_id: UUID,
    media_asset_id: UUID,
    body: SaveSubtitleStyleRequest,
    user: CurrentUser,
    request: Request,
) -> SubtitleStyleResponse:
    value = await request.app.state.subtitle_style_service.save(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
        expected_version=body.expected_version,
        font_id=body.font_id,
        font_size_pct=body.font_size_pct,
        text_color=body.text_color,
        outline_color=body.outline_color,
        background_color=body.background_color,
        background_opacity_pct=body.background_opacity_pct,
        outline_px=body.outline_px,
        shadow_px=body.shadow_px,
        alignment=body.alignment,
    )
    return SubtitleStyleResponse.from_domain(value)
