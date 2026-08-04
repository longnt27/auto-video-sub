from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePath
from uuid import UUID

from auto_video_sub_domain.errors import ValidationError


class UploadState(StrEnum):
    PENDING = "pending"
    OBJECT_RECEIVED = "object_received"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ABORTED = "aborted"


class MediaStatus(StrEnum):
    UPLOAD_PENDING = "upload_pending"
    OBJECT_RECEIVED = "object_received"
    VALIDATING = "validating"
    PROXY_GENERATING = "proxy_generating"
    READY = "ready"
    REJECTED = "rejected"
    FAILED = "failed"


class ArtifactState(StrEnum):
    AVAILABLE = "available"
    DELETED = "deleted"


class ArtifactKind(StrEnum):
    ORIGINAL_VIDEO = "original_video"
    PROXY_VIDEO = "proxy_video"


class RetentionClass(StrEnum):
    SOURCE = "source"
    DERIVED_REUSABLE = "derived_reusable"


@dataclass(frozen=True, slots=True)
class MediaLimits:
    max_upload_bytes: int
    max_duration_us: int
    max_width: int
    max_height: int
    max_frame_rate: float
    max_streams: int
    allowed_content_types: frozenset[str]

    def validate_upload_declaration(self, *, byte_size: int, content_type: str) -> None:
        if byte_size <= 0:
            raise ValidationError("Upload must not be empty", code="UPLOAD_EMPTY")
        if byte_size > self.max_upload_bytes:
            raise ValidationError(
                "Upload exceeds the configured size limit", code="UPLOAD_TOO_LARGE"
            )
        if content_type not in self.allowed_content_types:
            raise ValidationError("Unsupported declared media type", code="UPLOAD_TYPE_UNSUPPORTED")


@dataclass(frozen=True, slots=True)
class UploadIntent:
    id: UUID
    project_id: UUID
    media_asset_id: UUID
    original_artifact_id: UUID
    object_key: str
    sealed_object_key: str
    display_name: str
    declared_content_type: str
    declared_size_bytes: int
    state: UploadState
    expires_at: datetime
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MediaProbe:
    format_name: str
    duration_us: int
    width: int
    height: int
    frame_rate: float
    video_codec: str
    audio_codec: str | None
    stream_count: int


@dataclass(frozen=True, slots=True)
class MediaAsset:
    id: UUID
    project_id: UUID
    display_name: str
    status: MediaStatus
    original_artifact_id: UUID
    proxy_artifact_id: UUID | None
    probe: MediaProbe | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Artifact:
    id: UUID
    project_id: UUID
    media_asset_id: UUID
    kind: ArtifactKind
    media_type: str
    byte_size: int
    checksum_sha256: str
    object_key: str
    retention_class: RetentionClass
    state: ArtifactState
    created_at: datetime


def safe_display_name(value: str) -> str:
    name = PurePath(value.replace("\\", "/")).name.strip()
    if not name or name in {".", ".."}:
        raise ValidationError("A valid display filename is required", code="UPLOAD_NAME_INVALID")
    if len(name) > 255 or any(ord(character) < 32 for character in name):
        raise ValidationError("Display filename is invalid", code="UPLOAD_NAME_INVALID")
    return name


def validate_probe(probe: MediaProbe, limits: MediaLimits) -> None:
    if probe.duration_us <= 0 or probe.duration_us > limits.max_duration_us:
        raise ValidationError(
            "Media duration is outside allowed limits", code="MEDIA_DURATION_INVALID"
        )
    if probe.width <= 0 or probe.height <= 0:
        raise ValidationError("Media has invalid frame dimensions", code="MEDIA_DIMENSIONS_INVALID")
    if probe.width > limits.max_width or probe.height > limits.max_height:
        raise ValidationError(
            "Media frame dimensions exceed limits", code="MEDIA_DIMENSIONS_EXCEEDED"
        )
    if probe.frame_rate <= 0 or probe.frame_rate > limits.max_frame_rate:
        raise ValidationError(
            "Media frame rate is outside allowed limits", code="MEDIA_FRAME_RATE_INVALID"
        )
    if probe.stream_count <= 0 or probe.stream_count > limits.max_streams:
        raise ValidationError(
            "Media stream count is outside allowed limits", code="MEDIA_STREAMS_INVALID"
        )
