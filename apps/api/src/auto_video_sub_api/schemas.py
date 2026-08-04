from __future__ import annotations

from datetime import datetime
from uuid import UUID

from auto_video_sub_application import MediaView, UploadGrant
from auto_video_sub_domain import MediaAsset, Project
from pydantic import BaseModel, ConfigDict, Field


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)


class ProjectResponse(BaseModel):
    id: UUID
    title: str
    lifecycle: str
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, project: Project) -> ProjectResponse:
        return cls(
            id=project.id,
            title=project.title,
            lifecycle=project.lifecycle,
            version=project.version,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class CreateUploadIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=128)
    byte_size: int = Field(gt=0)


class SignedUploadResponse(BaseModel):
    url: str
    method: str
    headers: dict[str, str]
    expires_at: datetime


class UploadIntentResponse(BaseModel):
    id: UUID
    project_id: UUID
    media_asset_id: UUID
    state: str
    upload: SignedUploadResponse

    @classmethod
    def from_domain(cls, grant: UploadGrant) -> UploadIntentResponse:
        return cls(
            id=grant.intent.id,
            project_id=grant.intent.project_id,
            media_asset_id=grant.intent.media_asset_id,
            state=grant.intent.state,
            upload=SignedUploadResponse(
                url=grant.signed_upload.url,
                method=grant.signed_upload.method,
                headers=grant.signed_upload.headers,
                expires_at=grant.signed_upload.expires_at,
            ),
        )


class MediaProbeResponse(BaseModel):
    format_name: str
    duration_us: int
    width: int
    height: int
    frame_rate: float
    video_codec: str
    audio_codec: str | None
    stream_count: int


class MediaResponse(BaseModel):
    id: UUID
    project_id: UUID
    display_name: str
    status: str
    probe: MediaProbeResponse | None
    error_code: str | None
    proxy_url: str | None
    proxy_url_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_media(cls, media: MediaAsset) -> MediaResponse:
        return cls.from_view(MediaView(media=media, proxy_url=None, proxy_url_expires_at=None))

    @classmethod
    def from_view(cls, view: MediaView) -> MediaResponse:
        probe = (
            MediaProbeResponse(
                format_name=view.media.probe.format_name,
                duration_us=view.media.probe.duration_us,
                width=view.media.probe.width,
                height=view.media.probe.height,
                frame_rate=view.media.probe.frame_rate,
                video_codec=view.media.probe.video_codec,
                audio_codec=view.media.probe.audio_codec,
                stream_count=view.media.probe.stream_count,
            )
            if view.media.probe is not None
            else None
        )
        return cls(
            id=view.media.id,
            project_id=view.media.project_id,
            display_name=view.media.display_name,
            status=view.media.status,
            probe=probe,
            error_code=view.media.error_code,
            proxy_url=view.proxy_url,
            proxy_url_expires_at=view.proxy_url_expires_at,
            created_at=view.media.created_at,
            updated_at=view.media.updated_at,
        )


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody
