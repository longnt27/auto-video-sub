from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status

from auto_video_sub_api.auth import CurrentUser
from auto_video_sub_api.translation_schemas import (
    ApproveTranslationContextRequest,
    ApproveTranslationRequest,
    EditTranslationSegmentRequest,
    EstimateTranslationRequest,
    StartTranslationRequest,
    TonePresetResponse,
    TranslationEstimateResponse,
    TranslationResponse,
)

router = APIRouter(prefix="/v1", tags=["translation"])


@router.get("/translation/tones", response_model=list[TonePresetResponse])
async def list_translation_tones(user: CurrentUser, request: Request) -> list[TonePresetResponse]:
    del user
    return [
        TonePresetResponse(id=item.preset, label=item.label)
        for item in request.app.state.translation_service.tone_catalog()
    ]


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/translation/estimate",
    response_model=TranslationEstimateResponse,
)
async def estimate_translation(
    project_id: UUID,
    media_asset_id: UUID,
    body: EstimateTranslationRequest,
    user: CurrentUser,
    request: Request,
) -> TranslationEstimateResponse:
    estimate = await request.app.state.translation_service.estimate(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
        preset=body.preset,
    )
    return TranslationEstimateResponse.from_domain(estimate)


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/translation/start",
    response_model=TranslationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_translation(
    project_id: UUID,
    media_asset_id: UUID,
    body: StartTranslationRequest,
    user: CurrentUser,
    request: Request,
) -> TranslationResponse:
    snapshot = await request.app.state.translation_service.start(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
        preset=body.preset,
        confirm_paid=body.confirm_paid,
        max_cost_micros=body.max_cost_micros,
    )
    return TranslationResponse.from_domain(snapshot)


@router.get(
    "/projects/{project_id}/media/{media_asset_id}/translation",
    response_model=TranslationResponse,
)
async def get_translation(
    project_id: UUID,
    media_asset_id: UUID,
    user: CurrentUser,
    request: Request,
) -> TranslationResponse:
    snapshot = await request.app.state.translation_service.get(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
    )
    return TranslationResponse.from_domain(snapshot)


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/translation/context/approve",
    response_model=TranslationResponse,
)
async def approve_translation_context(
    project_id: UUID,
    media_asset_id: UUID,
    body: ApproveTranslationContextRequest,
    user: CurrentUser,
    request: Request,
) -> TranslationResponse:
    snapshot = await request.app.state.translation_service.approve_context(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
        expected_version=body.expected_version,
        summary=body.summary,
        entities=(
            tuple(item.to_domain() for item in body.entities) if body.entities is not None else None
        ),
    )
    return TranslationResponse.from_domain(snapshot)


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/translation/segments/{segment_id}/revisions",
    response_model=TranslationResponse,
)
async def edit_translation_segment(
    project_id: UUID,
    media_asset_id: UUID,
    segment_id: UUID,
    body: EditTranslationSegmentRequest,
    user: CurrentUser,
    request: Request,
) -> TranslationResponse:
    snapshot = await request.app.state.translation_service.edit_segment(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
        segment_id=segment_id,
        text=body.text,
        expected_version=body.expected_version,
    )
    return TranslationResponse.from_domain(snapshot)


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/translation/approve",
    response_model=TranslationResponse,
)
async def approve_translation(
    project_id: UUID,
    media_asset_id: UUID,
    body: ApproveTranslationRequest,
    user: CurrentUser,
    request: Request,
) -> TranslationResponse:
    snapshot = await request.app.state.translation_service.approve(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
        expected_version=body.expected_version,
    )
    return TranslationResponse.from_domain(snapshot)


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/translation/cancel",
    response_model=TranslationResponse,
)
async def cancel_translation(
    project_id: UUID,
    media_asset_id: UUID,
    user: CurrentUser,
    request: Request,
) -> TranslationResponse:
    snapshot = await request.app.state.translation_service.cancel(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
    )
    return TranslationResponse.from_domain(snapshot)
