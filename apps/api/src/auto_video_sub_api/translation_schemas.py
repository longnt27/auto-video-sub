from __future__ import annotations

from datetime import datetime
from uuid import UUID

from auto_video_sub_application.translation_ports import (
    TranslationEstimate,
    TranslationSnapshot,
)
from auto_video_sub_domain import ContextEntity, TonePreset, new_uuid7
from pydantic import BaseModel, ConfigDict, Field


class TonePresetResponse(BaseModel):
    id: TonePreset
    label: str


class EstimateTranslationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: TonePreset = TonePreset.NATURAL


class TranslationEstimateResponse(BaseModel):
    preset: TonePreset
    provider: str
    model: str
    source_characters: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_micros: int

    @classmethod
    def from_domain(cls, estimate: TranslationEstimate) -> TranslationEstimateResponse:
        return cls(
            preset=estimate.preset,
            provider=estimate.provider,
            model=estimate.model,
            source_characters=estimate.source_characters,
            estimated_input_tokens=estimate.estimated_input_tokens,
            estimated_output_tokens=estimate.estimated_output_tokens,
            estimated_cost_micros=estimate.estimated_cost_micros,
        )


class StartTranslationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: TonePreset = TonePreset.NATURAL
    confirm_paid: bool = False
    max_cost_micros: int = Field(ge=0)


class ContextEntityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    kind: str = Field(min_length=1, max_length=64)
    source_forms: list[str] = Field(min_length=1, max_length=20)
    preferred_vietnamese: str | None = Field(default=None, max_length=400)
    confidence: float = Field(ge=0, le=1)
    ambiguous: bool = False
    notes: str | None = Field(default=None, max_length=2000)
    evidence_segment_ids: list[UUID] = Field(default_factory=list, max_length=200)

    def to_domain(self) -> ContextEntity:
        return ContextEntity(
            id=self.id or new_uuid7(),
            kind=self.kind.strip(),
            source_forms=tuple(item.strip() for item in self.source_forms),
            preferred_vietnamese=(
                self.preferred_vietnamese.strip() if self.preferred_vietnamese is not None else None
            ),
            confidence=self.confidence,
            ambiguous=self.ambiguous,
            notes=self.notes.strip() if self.notes is not None else None,
            evidence_segment_ids=tuple(self.evidence_segment_ids),
        )


class ApproveTranslationContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    summary: str | None = Field(default=None, min_length=1, max_length=20_000)
    entities: list[ContextEntityInput] | None = None


class EditTranslationSegmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)
    expected_version: int = Field(ge=1)


class ApproveTranslationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


class TranslationPolicyResponse(BaseModel):
    id: UUID
    preset: TonePreset
    prompt_version: str
    provider: str
    model: str
    version: int
    created_at: datetime


class ContextEntityResponse(BaseModel):
    id: UUID
    kind: str
    source_forms: list[str]
    preferred_vietnamese: str | None
    confidence: float
    ambiguous: bool
    notes: str | None
    evidence_segment_ids: list[UUID]


class ContextVersionResponse(BaseModel):
    id: UUID
    transcript_version: int
    version: int
    summary: str
    entities: list[ContextEntityResponse]
    approved: bool
    parent_version_id: UUID | None
    created_at: datetime


class TranslationRevisionResponse(BaseModel):
    id: UUID
    version: int
    text: str
    origin: str
    provider: str | None
    model: str | None
    prompt_version: str | None
    created_at: datetime


class TranslationSegmentResponse(BaseModel):
    id: UUID
    ordinal: int
    start_us: int
    end_us: int
    source_text: str
    source_version: int
    segment_version: int
    translation: TranslationRevisionResponse | None


class TranslationFindingResponse(BaseModel):
    code: str
    segment_id: UUID | None
    message: str


class TranslationResponse(BaseModel):
    project_id: UUID
    media_asset_id: UUID
    status: str
    version: int
    error_code: str | None
    estimated_cost_micros: int
    reserved_cost_micros: int
    actual_cost_micros: int
    policy: TranslationPolicyResponse
    context: ContextVersionResponse | None
    segments: list[TranslationSegmentResponse]
    findings: list[TranslationFindingResponse]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, snapshot: TranslationSnapshot) -> TranslationResponse:
        context = None
        if snapshot.context is not None:
            context = ContextVersionResponse(
                id=snapshot.context.id,
                transcript_version=snapshot.context.transcript_version,
                version=snapshot.context.version,
                summary=snapshot.context.summary,
                entities=[
                    ContextEntityResponse(
                        id=entity.id,
                        kind=entity.kind,
                        source_forms=list(entity.source_forms),
                        preferred_vietnamese=entity.preferred_vietnamese,
                        confidence=entity.confidence,
                        ambiguous=entity.ambiguous,
                        notes=entity.notes,
                        evidence_segment_ids=list(entity.evidence_segment_ids),
                    )
                    for entity in snapshot.context.entities
                ],
                approved=snapshot.context.approved,
                parent_version_id=snapshot.context.parent_version_id,
                created_at=snapshot.context.created_at,
            )
        return cls(
            project_id=snapshot.record.project_id,
            media_asset_id=snapshot.record.media_asset_id,
            status=snapshot.record.status,
            version=snapshot.record.version,
            error_code=snapshot.record.error_code,
            estimated_cost_micros=snapshot.record.estimated_cost_micros,
            reserved_cost_micros=snapshot.record.reserved_cost_micros,
            actual_cost_micros=snapshot.record.actual_cost_micros,
            policy=TranslationPolicyResponse(
                id=snapshot.policy.id,
                preset=snapshot.policy.preset,
                prompt_version=snapshot.policy.prompt_version,
                provider=snapshot.policy.provider,
                model=snapshot.policy.model,
                version=snapshot.policy.version,
                created_at=snapshot.policy.created_at,
            ),
            context=context,
            segments=[
                TranslationSegmentResponse(
                    id=item.source.id,
                    ordinal=item.source.ordinal,
                    start_us=item.source.start_us,
                    end_us=item.source.end_us,
                    source_text=item.source.current_revision.text,
                    source_version=item.source.current_revision.version,
                    segment_version=(
                        item.translation.version
                        if item.translation is not None
                        else item.source.version
                    ),
                    translation=(
                        TranslationRevisionResponse(
                            id=item.translation.id,
                            version=item.translation.version,
                            text=item.translation.text,
                            origin=item.translation.origin,
                            provider=item.translation.provider,
                            model=item.translation.model,
                            prompt_version=item.translation.prompt_version,
                            created_at=item.translation.created_at,
                        )
                        if item.translation is not None
                        else None
                    ),
                )
                for item in snapshot.segments
            ],
            findings=[
                TranslationFindingResponse(
                    code=item.code,
                    segment_id=item.segment_id,
                    message=item.message,
                )
                for item in snapshot.findings
            ],
            created_at=snapshot.record.created_at,
            updated_at=snapshot.record.updated_at,
        )
