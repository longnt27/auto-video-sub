from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from auto_video_sub_domain.errors import ValidationError

_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


class TonePreset(StrEnum):
    NATURAL = "natural"
    FUNNY = "funny"
    FORMAL = "formal"
    DRAMATIC = "dramatic"


class TranslationStatus(StrEnum):
    NOT_STARTED = "not_started"
    CONTEXT_PROCESSING = "context_processing"
    WAITING_FOR_CONTEXT_REVIEW = "waiting_for_context_review"
    TRANSLATING = "translating"
    WAITING_FOR_REVIEW = "waiting_for_review"
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TranslationRevisionOrigin(StrEnum):
    CLOUD_TRANSLATION = "cloud_translation"
    CONSISTENCY_REPAIR = "consistency_repair"
    USER = "user"


@dataclass(frozen=True, slots=True)
class ContextEntity:
    id: UUID
    kind: str
    source_forms: tuple[str, ...]
    preferred_vietnamese: str | None
    confidence: float
    ambiguous: bool
    notes: str | None
    evidence_segment_ids: tuple[UUID, ...]

    def validate(self) -> None:
        if not self.kind.strip() or len(self.kind) > 64:
            raise ValidationError("Context entity kind is invalid", code="CONTEXT_ENTITY_INVALID")
        if not self.source_forms or any(not item.strip() for item in self.source_forms):
            raise ValidationError("Context entity source forms are required", code="CONTEXT_ENTITY_INVALID")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationError("Context entity confidence is invalid", code="CONTEXT_CONFIDENCE_INVALID")
        if self.preferred_vietnamese is not None and len(self.preferred_vietnamese.strip()) > 400:
            raise ValidationError("Context rendering is too long", code="CONTEXT_ENTITY_INVALID")
        if self.notes is not None and len(self.notes) > 2000:
            raise ValidationError("Context entity notes are too long", code="CONTEXT_ENTITY_INVALID")


@dataclass(frozen=True, slots=True)
class ContextVersion:
    id: UUID
    project_id: UUID
    media_asset_id: UUID
    transcript_version: int
    version: int
    summary: str
    entities: tuple[ContextEntity, ...]
    approved: bool
    parent_version_id: UUID | None
    created_by: UUID | None
    created_at: datetime

    def validate(self) -> None:
        if self.transcript_version < 1 or self.version < 1:
            raise ValidationError("Context version is invalid", code="CONTEXT_VERSION_INVALID")
        if not self.summary.strip() or len(self.summary) > 20_000:
            raise ValidationError("Context summary is invalid", code="CONTEXT_SUMMARY_INVALID")
        seen: set[UUID] = set()
        for entity in self.entities:
            entity.validate()
            if entity.id in seen:
                raise ValidationError("Context contains duplicate entity IDs", code="CONTEXT_ENTITY_DUPLICATE")
            seen.add(entity.id)


@dataclass(frozen=True, slots=True)
class TranslationPolicyVersion:
    id: UUID
    project_id: UUID
    preset: TonePreset
    prompt_version: str
    prompt_checksum: str
    provider: str
    model: str
    version: int
    created_by: UUID
    created_at: datetime

    def validate(self) -> None:
        if self.version < 1:
            raise ValidationError("Translation policy version is invalid", code="TRANSLATION_POLICY_INVALID")
        if not self.prompt_version or len(self.prompt_checksum) != 64:
            raise ValidationError("Translation prompt metadata is invalid", code="TRANSLATION_POLICY_INVALID")
        if not self.provider.strip() or not self.model.strip():
            raise ValidationError("Translation provider/model is required", code="TRANSLATION_PROVIDER_UNCONFIGURED")


@dataclass(frozen=True, slots=True)
class TranslationRevision:
    id: UUID
    subtitle_segment_id: UUID
    version: int
    text: str
    origin: TranslationRevisionOrigin
    context_version_id: UUID
    policy_version_id: UUID
    provider: str | None
    model: str | None
    prompt_version: str | None
    editor_id: UUID | None
    parent_revision_id: UUID | None
    created_at: datetime

    def validate(self) -> None:
        if self.version < 1:
            raise ValidationError("Translation revision version is invalid", code="TRANSLATION_VERSION_INVALID")
        cleaned = self.text.strip()
        if not cleaned:
            raise ValidationError("Vietnamese translation cannot be empty", code="TRANSLATION_TEXT_EMPTY")
        if len(cleaned) > 4000:
            raise ValidationError("Vietnamese translation is too long", code="TRANSLATION_TEXT_TOO_LONG")


@dataclass(frozen=True, slots=True)
class TranslationFinding:
    code: str
    segment_id: UUID | None
    message: str


@dataclass(frozen=True, slots=True)
class TranslationBatchPlan:
    ordinal: int
    owned_segment_ids: tuple[UUID, ...]
    overlap_segment_ids: tuple[UUID, ...]


def contains_han(value: str) -> bool:
    return _HAN.search(value) is not None


def validate_translation_items(
    *,
    owned_segment_ids: tuple[UUID, ...],
    items: tuple[tuple[UUID, str], ...],
) -> tuple[tuple[UUID, str], ...]:
    expected = set(owned_segment_ids)
    if not expected:
        raise ValidationError("Translation batch has no owned segments", code="TRANSLATION_BATCH_EMPTY")

    seen: set[UUID] = set()
    normalized: list[tuple[UUID, str]] = []
    for segment_id, text in items:
        if segment_id not in expected:
            raise ValidationError(
                "Translation provider returned an unknown segment ID",
                code="TRANSLATION_VALIDATION_UNKNOWN_ID",
            )
        if segment_id in seen:
            raise ValidationError(
                "Translation provider returned a duplicate segment ID",
                code="TRANSLATION_VALIDATION_DUPLICATE_ID",
            )
        cleaned = text.strip()
        if not cleaned:
            raise ValidationError(
                "Translation provider returned empty text",
                code="TRANSLATION_VALIDATION_EMPTY_TEXT",
            )
        if len(cleaned) > 4000:
            raise ValidationError(
                "Translation provider returned oversized text",
                code="TRANSLATION_VALIDATION_TEXT_TOO_LONG",
            )
        seen.add(segment_id)
        normalized.append((segment_id, cleaned))

    if seen != expected:
        raise ValidationError(
            "Translation provider omitted owned segments",
            code="TRANSLATION_VALIDATION_MISSING_ID",
        )
    return tuple(normalized)


def plan_translation_batches(
    segments: tuple[tuple[UUID, int, int], ...],
    *,
    max_owned_segments: int = 40,
    max_span_us: int = 5 * 60 * 1_000_000,
    overlap_segments: int = 2,
) -> tuple[TranslationBatchPlan, ...]:
    if max_owned_segments < 1 or max_owned_segments > 200:
        raise ValidationError("Translation batch size is invalid", code="TRANSLATION_BATCH_POLICY_INVALID")
    if max_span_us <= 0 or overlap_segments < 0 or overlap_segments > 10:
        raise ValidationError("Translation batch timing policy is invalid", code="TRANSLATION_BATCH_POLICY_INVALID")
    if not segments:
        return ()

    plans: list[TranslationBatchPlan] = []
    start = 0
    ordinal = 0
    while start < len(segments):
        end = start
        first_start_us = segments[start][1]
        while end < len(segments):
            candidate_count = end - start + 1
            candidate_span = segments[end][2] - first_start_us
            if candidate_count > max_owned_segments or candidate_span > max_span_us:
                break
            end += 1
        if end == start:
            end = start + 1
        owned = tuple(item[0] for item in segments[start:end])
        before = tuple(item[0] for item in segments[max(0, start - overlap_segments) : start])
        after = tuple(item[0] for item in segments[end : min(len(segments), end + overlap_segments)])
        plans.append(
            TranslationBatchPlan(
                ordinal=ordinal,
                owned_segment_ids=owned,
                overlap_segment_ids=before + after,
            )
        )
        ordinal += 1
        start = end
    return tuple(plans)
