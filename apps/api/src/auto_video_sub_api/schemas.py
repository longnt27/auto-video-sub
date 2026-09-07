from __future__ import annotations

from datetime import datetime
from uuid import UUID

from auto_video_sub_application import MediaView, UploadGrant
from auto_video_sub_application.ports import TranscriptSnapshot
from auto_video_sub_domain import MediaAsset, Project, SubtitleRegion, SubtitleSegment
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


class StartTranscriptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x_start_ratio: float = Field(default=0.05, ge=0, le=1)
    x_end_ratio: float = Field(default=0.95, ge=0, le=1)
    y_start_ratio: float = Field(default=0.68, ge=0, le=1)
    y_end_ratio: float = Field(default=0.98, ge=0, le=1)
    sample_interval_ms: int = Field(default=400, ge=100, le=5000)

    def to_domain(self) -> SubtitleRegion:
        return SubtitleRegion(
            x_start_ratio=self.x_start_ratio,
            x_end_ratio=self.x_end_ratio,
            y_start_ratio=self.y_start_ratio,
            y_end_ratio=self.y_end_ratio,
            sample_interval_ms=self.sample_interval_ms,
        )


class EditSourceSegmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)
    expected_version: int = Field(ge=1)


class ApproveTranscriptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


class SourceRevisionResponse(BaseModel):
    id: UUID
    version: int
    text: str
    origin: str
    confidence: float | None


class SubtitleSegmentResponse(BaseModel):
    id: UUID
    ordinal: int
    start_us: int
    end_us: int
    version: int
    source: SourceRevisionResponse

    @classmethod
    def from_domain(cls, segment: SubtitleSegment) -> SubtitleSegmentResponse:
        return cls(
            id=segment.id,
            ordinal=segment.ordinal,
            start_us=segment.start_us,
            end_us=segment.end_us,
            version=segment.version,
            source=SourceRevisionResponse(
                id=segment.current_revision.id,
                version=segment.current_revision.version,
                text=segment.current_revision.text,
                origin=segment.current_revision.origin,
                confidence=segment.current_revision.confidence,
            ),
        )


class TranscriptRegionResponse(BaseModel):
    x_start_ratio: float
    x_end_ratio: float
    y_start_ratio: float
    y_end_ratio: float
    sample_interval_ms: int


class TranscriptResponse(BaseModel):
    project_id: UUID
    media_asset_id: UUID
    status: str
    version: int
    region: TranscriptRegionResponse
    error_code: str | None
    segments: list[SubtitleSegmentResponse]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, snapshot: TranscriptSnapshot) -> TranscriptResponse:
        record = snapshot.record
        return cls(
            project_id=record.project_id,
            media_asset_id=record.media_asset_id,
            status=record.status,
            version=record.version,
            region=TranscriptRegionResponse(
                x_start_ratio=record.region.x_start_ratio,
                x_end_ratio=record.region.x_end_ratio,
                y_start_ratio=record.region.y_start_ratio,
                y_end_ratio=record.region.y_end_ratio,
                sample_interval_ms=record.region.sample_interval_ms,
            ),
            error_code=record.error_code,
            segments=[SubtitleSegmentResponse.from_domain(item) for item in snapshot.segments],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody
