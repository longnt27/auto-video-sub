from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status

from auto_video_sub_api.auth import CurrentUser
from auto_video_sub_api.speech_schemas import (
    ApproveSpeechRequest,
    RetrySpeechSegmentRequest,
    SpeechResponse,
)

router = APIRouter(prefix="/v1", tags=["speech"])


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/speech/start",
    response_model=SpeechResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_speech(
    project_id: UUID,
    media_asset_id: UUID,
    user: CurrentUser,
    request: Request,
) -> SpeechResponse:
    snapshot = await request.app.state.speech_service.start(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
    )
    return SpeechResponse.from_domain(snapshot)


@router.get(
    "/projects/{project_id}/media/{media_asset_id}/speech",
    response_model=SpeechResponse,
)
async def get_speech(
    project_id: UUID,
    media_asset_id: UUID,
    user: CurrentUser,
    request: Request,
) -> SpeechResponse:
    snapshot = await request.app.state.speech_service.get(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
    )
    return SpeechResponse.from_domain(snapshot)


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/speech/segments/{segment_id}/retry",
    response_model=SpeechResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_speech_segment(
    project_id: UUID,
    media_asset_id: UUID,
    segment_id: UUID,
    body: RetrySpeechSegmentRequest,
    user: CurrentUser,
    request: Request,
) -> SpeechResponse:
    snapshot = await request.app.state.speech_service.retry_segment(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
        segment_id=segment_id,
        text=body.text,
    )
    return SpeechResponse.from_domain(snapshot)


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/speech/approve",
    response_model=SpeechResponse,
)
async def approve_speech(
    project_id: UUID,
    media_asset_id: UUID,
    body: ApproveSpeechRequest,
    user: CurrentUser,
    request: Request,
) -> SpeechResponse:
    snapshot = await request.app.state.speech_service.approve(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
        expected_version=body.expected_version,
    )
    return SpeechResponse.from_domain(snapshot)


@router.post(
    "/projects/{project_id}/media/{media_asset_id}/speech/cancel",
    response_model=SpeechResponse,
)
async def cancel_speech(
    project_id: UUID,
    media_asset_id: UUID,
    user: CurrentUser,
    request: Request,
) -> SpeechResponse:
    snapshot = await request.app.state.speech_service.cancel(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
    )
    return SpeechResponse.from_domain(snapshot)
