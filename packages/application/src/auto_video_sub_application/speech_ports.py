from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from auto_video_sub_application.ports import ObjectMetadata
from auto_video_sub_domain import (
    ArtifactKind,
    DurationFitPolicy,
    SpeechAttempt,
    SpeechSegmentStatus,
    SpeechStatus,
    SpeechTextOrigin,
    TonePreset,
)


class TtsProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class RewriteProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class TtsRequest:
    segment_id: UUID
    text: str
    voice_id: str


@dataclass(frozen=True, slots=True)
class TtsResult:
    wav_bytes: bytes
    sample_rate_hz: int
    provider_request_id: str | None = None


@dataclass(frozen=True, slots=True)
class RewriteRequest:
    segment_id: UUID
    text: str
    tone: TonePreset
    protected_terms: tuple[str, ...]
    target_duration_us: int
    measured_duration_us: int
    previous_rewrites: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RewriteResult:
    segment_id: UUID
    text: str
    model: str
    model_revision: str


@dataclass(frozen=True, slots=True)
class AudioTransformResult:
    duration_us: int
    silence_removed_us: int = 0


@dataclass(frozen=True, slots=True)
class PublishedSpeechArtifact:
    id: UUID
    kind: ArtifactKind
    object_key: str
    media_type: str
    byte_size: int
    checksum_sha256: str


@dataclass(frozen=True, slots=True)
class SpeechInputSegment:
    id: UUID
    project_id: UUID
    media_asset_id: UUID
    ordinal: int
    start_us: int
    end_us: int
    translation_revision_id: UUID
    text: str
    tone: TonePreset
    protected_terms: tuple[str, ...]

    @property
    def slot_us(self) -> int:
        return self.end_us - self.start_us


@dataclass(frozen=True, slots=True)
class SpeechRecord:
    project_id: UUID
    media_asset_id: UUID
    status: SpeechStatus
    workflow_id: str | None
    error_code: str | None
    provider: str
    model: str
    model_revision: str
    voice_id: str
    policy: DurationFitPolicy
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SpeechSegmentView:
    input: SpeechInputSegment
    status: SpeechSegmentStatus
    current_attempt: SpeechAttempt | None
    attempts: tuple[SpeechAttempt, ...]
    audio_object_key: str | None
    audio_url: str | None = None


@dataclass(frozen=True, slots=True)
class SpeechSnapshot:
    record: SpeechRecord
    segments: tuple[SpeechSegmentView, ...]


class TtsProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def model_revision(self) -> str: ...

    @property
    def sample_rate_hz(self) -> int: ...

    async def synthesize(self, request: TtsRequest) -> TtsResult: ...


class LocalRewriteProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def model_revision(self) -> str: ...

    async def rewrite(self, request: RewriteRequest) -> RewriteResult: ...


class SpeechAudioProcessor(Protocol):
    async def probe_duration(self, source: Path) -> int: ...

    async def trim_edge_silence(self, source: Path, destination: Path) -> AudioTransformResult: ...

    async def speed_up(
        self, source: Path, destination: Path, *, speed_factor_ppm: int
    ) -> AudioTransformResult: ...


class SpeechObjectStorage(Protocol):
    async def object_metadata(self, object_key: str) -> ObjectMetadata: ...

    async def download_file(self, object_key: str, destination: Path) -> None: ...

    async def upload_file(
        self, source: Path, object_key: str, content_type: str
    ) -> ObjectMetadata: ...

    def sign_download(self, *, object_key: str, expires_at: datetime) -> str: ...


class SpeechRepository(Protocol):
    async def prepare(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        provider: str,
        model: str,
        model_revision: str,
        voice_id: str,
        policy: DurationFitPolicy,
    ) -> SpeechRecord: ...

    async def bind_workflow(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        workflow_id: str,
    ) -> SpeechRecord: ...

    async def snapshot(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> SpeechSnapshot: ...

    async def approve(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
    ) -> SpeechRecord: ...

    async def mark_cancelled(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> SpeechRecord: ...


class SpeechWorkflowControl(Protocol):
    async def start_speech(
        self, *, project_id: UUID, media_asset_id: UUID, speech_version: int
    ) -> str: ...

    async def retry_speech_segment(
        self, *, workflow_id: str, segment_id: UUID, text: str | None
    ) -> None: ...

    async def approve_speech(self, *, workflow_id: str) -> None: ...

    async def cancel_speech(self, *, workflow_id: str) -> None: ...


class SpeechWorkflowRepository(Protocol):
    async def get_record_internal(self, media_asset_id: UUID) -> SpeechRecord: ...

    async def list_inputs_internal(self, media_asset_id: UUID) -> tuple[SpeechInputSegment, ...]: ...

    async def begin_attempt(
        self,
        *,
        segment: SpeechInputSegment,
        attempt_index: int,
        parent_attempt_id: UUID | None,
        text: str,
        text_origin: SpeechTextOrigin,
        provider: str,
        model: str,
        model_revision: str,
        voice_id: str,
        policy: DurationFitPolicy,
    ) -> SpeechAttempt: ...

    async def finish_attempt(
        self,
        *,
        attempt_id: UUID,
        artifacts: tuple[PublishedSpeechArtifact, ...],
        raw_audio_artifact_id: UUID,
        trimmed_audio_artifact_id: UUID,
        final_audio_artifact_id: UUID | None,
        envelope_artifact_id: UUID,
        measured_duration_us: int,
        trimmed_duration_us: int,
        final_duration_us: int | None,
        silence_removed_us: int,
        speed_factor_ppm: int,
        outcome: str,
        error_code: str | None = None,
    ) -> SpeechAttempt: ...

    async def mark_attempt_failed(self, *, attempt_id: UUID, error_code: str) -> None: ...

    async def mark_segment_fitting(self, segment_id: UUID) -> None: ...

    async def mark_segment_needs_review(self, segment_id: UUID, attempt_id: UUID) -> None: ...

    async def mark_segment_fit(self, segment_id: UUID, attempt_id: UUID) -> None: ...

    async def finalize_speech(self, media_asset_id: UUID) -> SpeechStatus: ...

    async def set_speech_status(
        self, media_asset_id: UUID, status: SpeechStatus, *, error_code: str | None = None
    ) -> None: ...
