from __future__ import annotations

from datetime import datetime
from uuid import UUID

from auto_video_sub_application.render_ports import RenderSnapshot
from auto_video_sub_domain.rendering import OriginalAudioPolicy
from pydantic import BaseModel, ConfigDict


class StartRenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audio_policy: OriginalAudioPolicy


class RenderResponse(BaseModel):
    id: UUID
    project_id: UUID
    media_asset_id: UUID
    status: str
    workflow_id: str | None
    input_fingerprint: str
    audio_policy: str
    original_audio_gain_ppm: int
    renderer_version: str
    font_family: str
    manifest_artifact_id: UUID | None
    subtitle_artifact_id: UUID | None
    output_artifact_id: UUID | None
    validation_artifact_id: UUID | None
    error_code: str | None
    version: int
    validation: dict[str, object] | None
    download_url: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, snapshot: RenderSnapshot) -> RenderResponse:
        record = snapshot.record
        return cls(
            id=record.id,
            project_id=record.project_id,
            media_asset_id=record.media_asset_id,
            status=record.status,
            workflow_id=record.workflow_id,
            input_fingerprint=record.input_fingerprint,
            audio_policy=record.audio_policy,
            original_audio_gain_ppm=record.original_audio_gain_ppm,
            renderer_version=record.renderer_version,
            font_family=record.font_family,
            manifest_artifact_id=record.manifest_artifact_id,
            subtitle_artifact_id=record.subtitle_artifact_id,
            output_artifact_id=record.output_artifact_id,
            validation_artifact_id=record.validation_artifact_id,
            error_code=record.error_code,
            version=record.version,
            validation=snapshot.validation,
            download_url=snapshot.output_url,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
