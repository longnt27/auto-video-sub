from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from auto_video_sub_domain.errors import ValidationError

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class OriginalAudioPolicy(StrEnum):
    RETAIN = "retain"
    REDUCE = "reduce"
    REMOVE = "remove"


class RenderStatus(StrEnum):
    PROCESSING = "processing"
    VALIDATING = "validating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class RenderJob:
    id: UUID
    project_id: UUID
    media_asset_id: UUID
    status: RenderStatus
    workflow_id: str | None
    input_fingerprint: str
    audio_policy: OriginalAudioPolicy
    original_audio_gain_ppm: int
    renderer_version: str
    font_family: str
    manifest_artifact_id: UUID | None
    subtitle_artifact_id: UUID | None
    output_artifact_id: UUID | None
    validation_artifact_id: UUID | None
    error_code: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    def validate(self) -> None:
        if _SHA256.fullmatch(self.input_fingerprint) is None:
            raise ValidationError("Render fingerprint is invalid", code="RENDER_INPUT_INVALID")
        if not self.renderer_version.strip() or len(self.renderer_version) > 160:
            raise ValidationError("Renderer version is invalid", code="RENDER_INPUT_INVALID")
        if not self.font_family.strip() or len(self.font_family) > 160:
            raise ValidationError("Render font family is invalid", code="RENDER_FONT_INVALID")
        if self.version < 1:
            raise ValidationError("Render version is invalid", code="RENDER_INPUT_INVALID")
        if self.audio_policy is OriginalAudioPolicy.RETAIN:
            if self.original_audio_gain_ppm != 1_000_000:
                raise ValidationError(
                    "Retained audio must use unity gain", code="RENDER_AUDIO_INVALID"
                )
        elif self.audio_policy is OriginalAudioPolicy.REDUCE:
            if not 0 < self.original_audio_gain_ppm < 1_000_000:
                raise ValidationError("Reduced audio gain is invalid", code="RENDER_AUDIO_INVALID")
        elif self.original_audio_gain_ppm != 0:
            raise ValidationError("Removed audio must use zero gain", code="RENDER_AUDIO_INVALID")
