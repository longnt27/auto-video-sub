from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status

from auto_video_sub_api.auth import CurrentUser
from auto_video_sub_api.render_schemas import RenderResponse, StartRenderRequest

router = APIRouter(prefix="/v1", tags=["render"])


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/render/start",
    response_model=RenderResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_render(
    project_id: UUID,
    media_asset_id: UUID,
    body: StartRenderRequest,
    user: CurrentUser,
    request: Request,
) -> RenderResponse:
    snapshot = await request.app.state.render_service.start(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
        audio_policy=body.audio_policy,
    )
    return RenderResponse.from_domain(snapshot)


@router.get(
    "/projects/{project_id}/media/{media_asset_id}/render",
    response_model=RenderResponse,
)
async def get_render(
    project_id: UUID,
    media_asset_id: UUID,
    user: CurrentUser,
    request: Request,
) -> RenderResponse:
    snapshot = await request.app.state.render_service.get(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
    )
    return RenderResponse.from_domain(snapshot)


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/render/cancel",
    response_model=RenderResponse,
)
async def cancel_render(
    project_id: UUID,
    media_asset_id: UUID,
    user: CurrentUser,
    request: Request,
) -> RenderResponse:
    snapshot = await request.app.state.render_service.cancel(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
    )
    return RenderResponse.from_domain(snapshot)
