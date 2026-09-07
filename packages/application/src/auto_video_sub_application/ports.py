from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from auto_video_sub_domain import (
    Artifact,
    ConsolidatedSegment,
    MediaAsset,
    MediaProbe,
    MediaStatus,
    OcrObservation,
    Project,
    SubtitleRegion,
    SubtitleSegment,
    TranscriptStatus,
    UploadIntent,
    User,
)


class MediaProcessError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class OcrProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class SignedUpload:
    url: str
    method: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    byte_size: int
    content_type: str
    etag: str | None


@dataclass(frozen=True, slots=True)
class ExtractedSubtitleFrame:
    time_us: int
    path: Path


@dataclass(frozen=True, slots=True)
class OcrResult:
    text: str
    confidence: float
    provider: str
    model_version: str


@dataclass(frozen=True, slots=True)
class TranscriptRecord:
    project_id: UUID
    media_asset_id: UUID
    status: TranscriptStatus
    region: SubtitleRegion
    workflow_id: str | None
    error_code: str | None
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TranscriptSnapshot:
    record: TranscriptRecord
    segments: tuple[SubtitleSegment, ...]


class ProductRepository(Protocol):
    async def get_or_create_user(self, external_login: str) -> User: ...

    async def create_project(
        self, *, owner_id: UUID, title: str, idempotency_key: str
    ) -> Project: ...

    async def list_projects(self, *, owner_id: UUID) -> list[Project]: ...

    async def get_project(self, *, owner_id: UUID, project_id: UUID) -> Project: ...

    async def create_upload_intent(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        display_name: str,
        content_type: str,
        byte_size: int,
        expires_at: datetime,
        idempotency_key: str,
    ) -> UploadIntent: ...

    async def get_upload_intent(
        self, *, owner_id: UUID, project_id: UUID, upload_intent_id: UUID
    ) -> UploadIntent: ...

    async def mark_upload_received(
        self, *, owner_id: UUID, upload_intent_id: UUID
    ) -> MediaAsset: ...

    async def reject_upload(self, *, upload_intent_id: UUID, error_code: str) -> None: ...

    async def get_media_asset(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> MediaAsset: ...

    async def get_media_asset_internal(self, media_asset_id: UUID) -> MediaAsset: ...

    async def get_upload_for_media_internal(self, media_asset_id: UUID) -> UploadIntent: ...

    async def get_artifact_for_owner(
        self, *, owner_id: UUID, project_id: UUID, artifact_id: UUID
    ) -> Artifact: ...


class ObjectStorage(Protocol):
    def sign_upload(
        self,
        *,
        object_key: str,
        content_type: str,
        byte_size: int,
        expires_at: datetime,
    ) -> SignedUpload: ...

    async def seal_upload(
        self,
        *,
        staging_key: str,
        sealed_key: str,
        expected_size: int,
        expected_content_type: str,
    ) -> ObjectMetadata: ...

    async def delete_object(self, object_key: str) -> None: ...

    def sign_download(self, *, object_key: str, expires_at: datetime) -> str: ...


class WorkflowStarter(Protocol):
    async def start_media_ingest(self, *, project_id: UUID, media_asset_id: UUID) -> str: ...


class TranscriptWorkflowControl(Protocol):
    async def start_source_transcript(
        self, *, project_id: UUID, media_asset_id: UUID, region: SubtitleRegion
    ) -> str: ...

    async def approve_source_transcript(self, *, media_asset_id: UUID) -> None: ...

    async def cancel_source_transcript(self, *, media_asset_id: UUID) -> None: ...


class TranscriptRepository(Protocol):
    async def prepare(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        region: SubtitleRegion,
    ) -> TranscriptRecord: ...

    async def bind_workflow(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        workflow_id: str,
    ) -> TranscriptRecord: ...

    async def snapshot(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> TranscriptSnapshot: ...

    async def edit_segment(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        segment_id: UUID,
        text: str,
        expected_version: int,
    ) -> SubtitleSegment: ...

    async def approve(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
    ) -> TranscriptRecord: ...

    async def mark_cancelled(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> TranscriptRecord: ...


class TranscriptWorkflowRepository(Protocol):
    async def get_record_internal(self, media_asset_id: UUID) -> TranscriptRecord: ...

    async def get_media_asset_internal(self, media_asset_id: UUID) -> MediaAsset: ...

    async def get_artifact_internal(self, artifact_id: UUID) -> Artifact | None: ...

    async def replace_ocr_observations(
        self, *, media_asset_id: UUID, observations: list[OcrObservation]
    ) -> None: ...

    async def load_ocr_observations(self, media_asset_id: UUID) -> list[OcrObservation]: ...

    async def publish_ocr_segments(
        self, *, media_asset_id: UUID, segments: list[ConsolidatedSegment]
    ) -> tuple[SubtitleSegment, ...]: ...

    async def set_transcript_status(
        self,
        media_asset_id: UUID,
        status: TranscriptStatus,
        *,
        error_code: str | None = None,
    ) -> None: ...

    async def begin_stage(
        self,
        *,
        project_id: UUID,
        media_asset_id: UUID,
        workflow_id: str,
        stage_name: str,
        attempt: int,
        input_fingerprint: str,
        worker_id: str,
    ) -> UUID: ...

    async def finish_stage(
        self,
        stage_execution_id: UUID,
        *,
        status: str,
        error_code: str | None = None,
        retryable: bool | None = None,
    ) -> None: ...


class MediaWorkflowRepository(Protocol):
    async def get_media_asset_internal(self, media_asset_id: UUID) -> MediaAsset: ...

    async def get_upload_for_media_internal(self, media_asset_id: UUID) -> UploadIntent: ...

    async def get_artifact_internal(self, artifact_id: UUID) -> Artifact | None: ...

    async def set_media_status(
        self, media_asset_id: UUID, status: MediaStatus, *, error_code: str | None = None
    ) -> None: ...

    async def mark_media_failed(self, media_asset_id: UUID, *, error_code: str) -> None: ...

    async def ensure_proxy_artifact_id(self, media_asset_id: UUID) -> UUID: ...

    async def register_original(
        self,
        *,
        media_asset_id: UUID,
        media_type: str,
        byte_size: int,
        checksum_sha256: str,
        probe: MediaProbe,
        stage_execution_id: UUID,
    ) -> Artifact: ...

    async def register_proxy(
        self,
        *,
        media_asset_id: UUID,
        artifact_id: UUID,
        object_key: str,
        byte_size: int,
        checksum_sha256: str,
        stage_execution_id: UUID,
    ) -> Artifact: ...

    async def begin_stage(
        self,
        *,
        project_id: UUID,
        media_asset_id: UUID,
        workflow_id: str,
        stage_name: str,
        attempt: int,
        input_fingerprint: str,
        worker_id: str,
    ) -> UUID: ...

    async def finish_stage(
        self,
        stage_execution_id: UUID,
        *,
        status: str,
        error_code: str | None = None,
        retryable: bool | None = None,
    ) -> None: ...

    async def reject_upload(self, *, upload_intent_id: UUID, error_code: str) -> None: ...


class MediaArtifactStorage(Protocol):
    async def object_metadata(self, object_key: str) -> ObjectMetadata: ...

    async def download_file(self, object_key: str, destination: Path) -> None: ...

    async def upload_file(
        self, source: Path, object_key: str, content_type: str
    ) -> ObjectMetadata: ...

    async def delete_object(self, object_key: str) -> None: ...


class MediaProcessor(Protocol):
    def validate_magic(self, path: Path, declared_content_type: str) -> None: ...

    async def probe(self, path: Path) -> MediaProbe: ...

    async def generate_proxy(self, source: Path, destination: Path) -> None: ...

    async def extract_subtitle_frames(
        self, source: Path, destination: Path, region: SubtitleRegion
    ) -> list[ExtractedSubtitleFrame]: ...


class OcrProvider(Protocol):
    async def recognize(self, path: Path) -> OcrResult: ...
