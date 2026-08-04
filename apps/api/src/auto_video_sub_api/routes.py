from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

from auto_video_sub_domain import ValidationError
from fastapi import APIRouter, Header, Request, status

from auto_video_sub_api.auth import CurrentUser
from auto_video_sub_api.schemas import (
    CreateProjectRequest,
    CreateUploadIntentRequest,
    MediaResponse,
    ProjectResponse,
    UploadIntentResponse,
)

IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")

router = APIRouter(prefix="/v1")


def idempotency_key(
    value: Annotated[str, Header(alias="Idempotency-Key")],
) -> str:
    if not IDEMPOTENCY_PATTERN.fullmatch(value):
        raise ValidationError(
            "Idempotency-Key must contain 8-128 letters, digits, underscores, or hyphens",
            code="IDEMPOTENCY_KEY_INVALID",
        )
    return value


IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key")]


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: CreateProjectRequest,
    user: CurrentUser,
    request: Request,
    idempotency: IdempotencyKey,
) -> ProjectResponse:
    project = await request.app.state.project_service.create(
        owner_id=user.id,
        title=body.title,
        idempotency_key=idempotency_key(idempotency),
    )
    return ProjectResponse.from_domain(project)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(user: CurrentUser, request: Request) -> list[ProjectResponse]:
    projects = await request.app.state.project_service.list(owner_id=user.id)
    return [ProjectResponse.from_domain(project) for project in projects]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID, user: CurrentUser, request: Request) -> ProjectResponse:
    project = await request.app.state.project_service.get(owner_id=user.id, project_id=project_id)
    return ProjectResponse.from_domain(project)


@router.post(
    "/projects/{project_id}/uploads",
    response_model=UploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_intent(
    project_id: UUID,
    body: CreateUploadIntentRequest,
    user: CurrentUser,
    request: Request,
    idempotency: IdempotencyKey,
) -> UploadIntentResponse:
    grant = await request.app.state.upload_service.create_intent(
        owner_id=user.id,
        project_id=project_id,
        file_name=body.file_name,
        content_type=body.content_type,
        byte_size=body.byte_size,
        idempotency_key=idempotency_key(idempotency),
    )
    return UploadIntentResponse.from_domain(grant)


@router.post(
    "/projects/{project_id}/uploads/{upload_intent_id}/complete",
    response_model=MediaResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def complete_upload(
    project_id: UUID,
    upload_intent_id: UUID,
    user: CurrentUser,
    request: Request,
) -> MediaResponse:
    media = await request.app.state.upload_service.complete(
        owner_id=user.id,
        project_id=project_id,
        upload_intent_id=upload_intent_id,
    )
    return MediaResponse.from_media(media)


@router.get("/projects/{project_id}/media/{media_asset_id}", response_model=MediaResponse)
async def get_media(
    project_id: UUID,
    media_asset_id: UUID,
    user: CurrentUser,
    request: Request,
) -> MediaResponse:
    view = await request.app.state.upload_service.get_media(
        owner_id=user.id,
        project_id=project_id,
        media_asset_id=media_asset_id,
    )
    return MediaResponse.from_view(view)
