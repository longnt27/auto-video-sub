from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from auto_video_sub_domain import (
    ContextEntity,
    ContextVersion,
    SubtitleSegment,
    TonePreset,
    TranslationBatchPlan,
    TranslationFinding,
    TranslationPolicyVersion,
    TranslationRevision,
    TranslationStatus,
)


class TranslationProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class TranslationSourceSegment:
    id: UUID
    start_us: int
    end_us: int
    text: str


@dataclass(frozen=True, slots=True)
class ContextExtractionRequest:
    project_id: UUID
    media_asset_id: UUID
    transcript_version: int
    segments: tuple[TranslationSourceSegment, ...]
    prompt_version: str
    instructions: str


@dataclass(frozen=True, slots=True)
class ContextProviderEntity:
    kind: str
    source_forms: tuple[str, ...]
    preferred_vietnamese: str | None
    confidence: float
    ambiguous: bool
    notes: str | None
    evidence_segment_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class ContextProviderResult:
    summary: str
    entities: tuple[ContextProviderEntity, ...]
    unresolved_questions: tuple[str, ...]
    usage: ProviderUsage
    provider_request_id: str | None


@dataclass(frozen=True, slots=True)
class TranslationBatchRequest:
    batch_id: UUID
    owned_segments: tuple[TranslationSourceSegment, ...]
    overlap_segments: tuple[TranslationSourceSegment, ...]
    context_summary: str
    glossary: tuple[ContextEntity, ...]
    preset: TonePreset
    prompt_version: str
    instructions: str


@dataclass(frozen=True, slots=True)
class TranslationProviderItem:
    segment_id: UUID
    text: str


@dataclass(frozen=True, slots=True)
class TranslationProviderResult:
    items: tuple[TranslationProviderItem, ...]
    usage: ProviderUsage
    provider_request_id: str | None


@dataclass(frozen=True, slots=True)
class TranslationEstimate:
    preset: TonePreset
    provider: str
    model: str
    source_characters: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_micros: int


@dataclass(frozen=True, slots=True)
class TranslationRecord:
    project_id: UUID
    media_asset_id: UUID
    status: TranslationStatus
    transcript_version: int
    policy_version_id: UUID
    context_version_id: UUID | None
    workflow_id: str | None
    error_code: str | None
    estimated_cost_micros: int
    reserved_cost_micros: int
    actual_cost_micros: int
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TranslationSegmentView:
    source: SubtitleSegment
    translation: TranslationRevision | None


@dataclass(frozen=True, slots=True)
class TranslationSnapshot:
    record: TranslationRecord
    policy: TranslationPolicyVersion
    context: ContextVersion | None
    segments: tuple[TranslationSegmentView, ...]
    findings: tuple[TranslationFinding, ...]


@dataclass(frozen=True, slots=True)
class TranslationBatchRecord:
    id: UUID
    project_id: UUID
    media_asset_id: UUID
    ordinal: int
    plan: TranslationBatchPlan
    status: str
    context_version_id: UUID
    policy_version_id: UUID
    created_at: datetime
    updated_at: datetime


class TranslationProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    async def extract_context(self, request: ContextExtractionRequest) -> ContextProviderResult: ...

    async def translate_batch(self, request: TranslationBatchRequest) -> TranslationProviderResult: ...


class TranslationRepository(Protocol):
    async def source_for_estimate(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> tuple[int, tuple[SubtitleSegment, ...]]: ...

    async def prepare(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        preset: TonePreset,
        provider: str,
        model: str,
        prompt_version: str,
        prompt_checksum: str,
        estimated_cost_micros: int,
        max_cost_micros: int,
    ) -> TranslationRecord: ...

    async def bind_workflow(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        workflow_id: str,
    ) -> TranslationRecord: ...

    async def snapshot(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> TranslationSnapshot: ...

    async def approve_context(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
        summary: str | None,
        entities: tuple[ContextEntity, ...] | None,
    ) -> ContextVersion: ...

    async def edit_segment(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        segment_id: UUID,
        text: str,
        expected_version: int,
    ) -> TranslationRevision: ...

    async def approve_translation(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
    ) -> TranslationRecord: ...

    async def mark_cancelled(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> TranslationRecord: ...


class TranslationWorkflowControl(Protocol):
    async def start_translation(
        self,
        *,
        project_id: UUID,
        media_asset_id: UUID,
        policy_version_id: UUID,
    ) -> str: ...

    async def approve_translation_context(
        self, *, media_asset_id: UUID, policy_version_id: UUID
    ) -> None: ...

    async def approve_translation(self, *, media_asset_id: UUID, policy_version_id: UUID) -> None: ...

    async def cancel_translation(self, *, media_asset_id: UUID, policy_version_id: UUID) -> None: ...


class TranslationWorkflowRepository(Protocol):
    async def get_record_internal(self, media_asset_id: UUID) -> TranslationRecord: ...

    async def get_policy_internal(self, policy_version_id: UUID) -> TranslationPolicyVersion: ...

    async def get_context_internal(self, media_asset_id: UUID) -> ContextVersion | None: ...

    async def load_source_segments_internal(
        self, media_asset_id: UUID
    ) -> tuple[TranslationSourceSegment, ...]: ...

    async def publish_context(
        self,
        *,
        media_asset_id: UUID,
        result: ContextProviderResult,
        provider: str,
        model: str,
        prompt_version: str,
    ) -> ContextVersion: ...

    async def create_batches(
        self, *, media_asset_id: UUID, plans: tuple[TranslationBatchPlan, ...]
    ) -> tuple[TranslationBatchRecord, ...]: ...

    async def get_batch_internal(self, batch_id: UUID) -> TranslationBatchRecord: ...

    async def publish_batch_result(
        self,
        *,
        batch_id: UUID,
        result: TranslationProviderResult,
        provider: str,
        model: str,
        prompt_version: str,
    ) -> None: ...

    async def finalize_translation(self, media_asset_id: UUID) -> tuple[TranslationFinding, ...]: ...

    async def set_translation_status(
        self,
        media_asset_id: UUID,
        status: TranslationStatus,
        *,
        error_code: str | None = None,
    ) -> None: ...

    async def record_usage(
        self,
        *,
        media_asset_id: UUID,
        stage_name: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        provider_request_id: str | None,
    ) -> None: ...

    async def reconcile_budget(self, media_asset_id: UUID) -> None: ...
