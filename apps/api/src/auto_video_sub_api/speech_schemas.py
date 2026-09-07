from __future__ import annotations

from datetime import datetime
from uuid import UUID

from auto_video_sub_application.speech_ports import SpeechSnapshot
from auto_video_sub_domain import SpeechAttempt
from pydantic import BaseModel, ConfigDict, Field


class RetrySpeechSegmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, min_length=1, max_length=4000)


class ApproveSpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


class DurationPolicyResponse(BaseModel):
    version: str
    tolerance_us: int
    max_speed_factor_ppm: int
    max_rewrite_attempts: int


class SpeechAttemptResponse(BaseModel):
    id: UUID
    attempt_index: int
    parent_attempt_id: UUID | None
    translation_revision_id: UUID
    text: str
    text_origin: str
    provider: str
    model: str
    model_revision: str
    voice_id: str
    measured_duration_us: int | None
    trimmed_duration_us: int | None
    final_duration_us: int | None
    silence_removed_us: int
    speed_factor_ppm: int
    slot_us: int
    tolerance_us: int
    outcome: str | None
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None


class SpeechSegmentResponse(BaseModel):
    id: UUID
    ordinal: int
    start_us: int
    end_us: int
    translation_revision_id: UUID
    text: str
    tone: str
    status: str
    current_attempt: SpeechAttemptResponse | None
    attempts: list[SpeechAttemptResponse]
    audio_url: str | None


class SpeechResponse(BaseModel):
    project_id: UUID
    media_asset_id: UUID
    status: str
    workflow_id: str | None
    error_code: str | None
    provider: str
    model: str
    model_revision: str
    voice_id: str
    policy: DurationPolicyResponse
    version: int
    segments: list[SpeechSegmentResponse]
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def _attempt(value: SpeechAttempt) -> SpeechAttemptResponse:
        return SpeechAttemptResponse(
            id=value.id,
            attempt_index=value.attempt_index,
            parent_attempt_id=value.parent_attempt_id,
            translation_revision_id=value.translation_revision_id,
            text=value.text,
            text_origin=value.text_origin,
            provider=value.provider,
            model=value.model,
            model_revision=value.model_revision,
            voice_id=value.voice_id,
            measured_duration_us=value.measured_duration_us,
            trimmed_duration_us=value.trimmed_duration_us,
            final_duration_us=value.final_duration_us,
            silence_removed_us=value.silence_removed_us,
            speed_factor_ppm=value.speed_factor_ppm,
            slot_us=value.slot_us,
            tolerance_us=value.tolerance_us,
            outcome=value.outcome,
            error_code=value.error_code,
            created_at=value.created_at,
            completed_at=value.completed_at,
        )

    @classmethod
    def from_domain(cls, snapshot: SpeechSnapshot) -> SpeechResponse:
        record = snapshot.record
        return cls(
            project_id=record.project_id,
            media_asset_id=record.media_asset_id,
            status=record.status,
            workflow_id=record.workflow_id,
            error_code=record.error_code,
            provider=record.provider,
            model=record.model,
            model_revision=record.model_revision,
            voice_id=record.voice_id,
            policy=DurationPolicyResponse(
                version=record.policy.version,
                tolerance_us=record.policy.tolerance_us,
                max_speed_factor_ppm=record.policy.max_speed_factor_ppm,
                max_rewrite_attempts=record.policy.max_rewrite_attempts,
            ),
            version=record.version,
            segments=[
                SpeechSegmentResponse(
                    id=item.input.id,
                    ordinal=item.input.ordinal,
                    start_us=item.input.start_us,
                    end_us=item.input.end_us,
                    translation_revision_id=item.input.translation_revision_id,
                    text=item.input.text,
                    tone=item.input.tone,
                    status=item.status,
                    current_attempt=(
                        cls._attempt(item.current_attempt) if item.current_attempt is not None else None
                    ),
                    attempts=[cls._attempt(attempt) for attempt in item.attempts],
                    audio_url=item.audio_url,
                )
                for item in snapshot.segments
            ],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
