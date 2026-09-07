from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from auto_video_sub_domain.rendering import OriginalAudioPolicy, RenderJob, RenderStatus
from auto_video_sub_domain.subtitle_style import SubtitleStyleDraft

from auto_video_sub_application.ports import ObjectMetadata


@dataclass(frozen=True, slots=True)
class RenderSpeechTrack:
    segment_id: UUID
    ordinal: int
    start_us: int
    end_us: int
    text: str
    translation_revision_id: UUID
    speech_attempt_id: UUID
    audio_artifact_id: UUID
    audio_object_key: str


@dataclass(frozen=True, slots=True)
class FrozenRenderInput:
    render_id: UUID
    project_id: UUID
    media_asset_id: UUID
    original_artifact_id: UUID
    original_object_key: str
    original_checksum_sha256: str
    duration_us: int
    width: int
    height: int
    source_has_audio: bool
    transcript_version: int
    translation_policy_version_id: UUID
    subtitle_style_version_id: UUID
    subtitle_style: SubtitleStyleDraft
    speech_tracks: tuple[RenderSpeechTrack, ...]
    audio_policy: OriginalAudioPolicy
    original_audio_gain_ppm: int
    renderer_version: str
    font_filename: str
    font_checksum_sha256: str
    input_fingerprint: str


@dataclass(frozen=True, slots=True)
class PublishedRenderArtifact:
    id: UUID
    object_key: str
    media_type: str
    byte_size: int
    checksum_sha256: str


@dataclass(frozen=True, slots=True)
class RenderValidationResult:
    valid: bool
    duration_us: int
    width: int
    height: int
    video_codec: str
    audio_codec: str | None
    stream_count: int
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RenderSnapshot:
    record: RenderJob
    output_object_key: str | None
    output_url: str | None = None
    validation: dict[str, object] | None = None


class RenderRepository(Protocol):
    async def prepare(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        audio_policy: OriginalAudioPolicy,
        original_audio_gain_ppm: int,
        renderer_version: str,
        font_filename: str,
        font_checksum_sha256: str,
    ) -> RenderJob: ...

    async def bind_workflow(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        render_id: UUID,
        workflow_id: str,
    ) -> RenderJob: ...

    async def snapshot(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> RenderSnapshot: ...

    async def mark_cancelled(
        self, *, owner_id: UUID, project_id: UUID, render_id: UUID
    ) -> RenderJob: ...


class RenderWorkflowRepository(Protocol):
    async def get_input_internal(self, render_id: UUID) -> FrozenRenderInput: ...

    async def register_artifact(
        self,
        *,
        render_id: UUID,
        role: str,
        artifact: PublishedRenderArtifact,
        validation: dict[str, object] | None = None,
    ) -> RenderJob: ...

    async def set_status(
        self,
        render_id: UUID,
        status: RenderStatus,
        *,
        error_code: str | None = None,
    ) -> None: ...


class RenderWorkflowControl(Protocol):
    async def start_render(self, *, render_id: UUID, render_version: int) -> str: ...

    async def cancel_render(self, *, workflow_id: str) -> None: ...


class RenderObjectStorage(Protocol):
    async def download_file(self, object_key: str, destination: Path) -> None: ...

    async def upload_file(
        self, source: Path, object_key: str, content_type: str
    ) -> ObjectMetadata: ...

    def sign_download(self, *, object_key: str, expires_at: datetime) -> str: ...


class RenderProcessor(Protocol):
    def write_ass(self, render_input: FrozenRenderInput, destination: Path) -> None: ...

    async def render(
        self,
        *,
        render_input: FrozenRenderInput,
        original_path: Path,
        speech_paths: Mapping[UUID, Path],
        ass_path: Path,
        font_path: Path,
        output_path: Path,
    ) -> None: ...

    async def validate(
        self,
        *,
        output_path: Path,
        expected_duration_us: int,
        expected_width: int,
        expected_height: int,
    ) -> RenderValidationResult: ...
