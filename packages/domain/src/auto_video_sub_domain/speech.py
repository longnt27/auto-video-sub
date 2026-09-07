from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import ceil
from uuid import UUID

from auto_video_sub_domain.errors import ValidationError


class SpeechStatus(StrEnum):
    NOT_STARTED = "not_started"
    PROCESSING = "processing"
    WAITING_FOR_REVIEW = "waiting_for_review"
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SpeechSegmentStatus(StrEnum):
    PENDING = "pending"
    FITTING = "fitting"
    FIT = "fit"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class SpeechTextOrigin(StrEnum):
    TRANSLATION = "translation"
    LOCAL_REWRITE = "local_rewrite"
    USER = "user"


class SpeechAttemptOutcome(StrEnum):
    FIT = "fit"
    REWRITE_REQUIRED = "rewrite_required"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class DurationFitAction(StrEnum):
    ACCEPT = "accept"
    SPEED_UP = "speed_up"
    REWRITE = "rewrite"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class DurationFitPolicy:
    version: str = "duration-fit-v1"
    tolerance_us: int = 100_000
    max_speed_factor_ppm: int = 1_080_000
    max_rewrite_attempts: int = 2

    def validate(self) -> None:
        if not self.version.strip() or len(self.version) > 96:
            raise ValidationError(
                "Duration-fit policy version is invalid", code="DURATION_POLICY_INVALID"
            )
        if self.tolerance_us < 0 or self.tolerance_us > 2_000_000:
            raise ValidationError(
                "Duration-fit tolerance is invalid", code="DURATION_POLICY_INVALID"
            )
        if not 1_000_000 <= self.max_speed_factor_ppm <= 1_500_000:
            raise ValidationError(
                "Duration-fit speed limit is invalid", code="DURATION_POLICY_INVALID"
            )
        if not 0 <= self.max_rewrite_attempts <= 10:
            raise ValidationError(
                "Duration-fit rewrite limit is invalid", code="DURATION_POLICY_INVALID"
            )


@dataclass(frozen=True, slots=True)
class DurationFitDecision:
    action: DurationFitAction
    speed_factor_ppm: int
    target_us: int


@dataclass(frozen=True, slots=True)
class SpeechAttempt:
    id: UUID
    project_id: UUID
    media_asset_id: UUID
    subtitle_segment_id: UUID
    attempt_index: int
    parent_attempt_id: UUID | None
    translation_revision_id: UUID
    text: str
    text_origin: SpeechTextOrigin
    provider: str
    model: str
    model_revision: str
    voice_id: str
    policy_version: str
    raw_audio_artifact_id: UUID | None
    trimmed_audio_artifact_id: UUID | None
    final_audio_artifact_id: UUID | None
    envelope_artifact_id: UUID | None
    measured_duration_us: int | None
    trimmed_duration_us: int | None
    final_duration_us: int | None
    silence_removed_us: int
    speed_factor_ppm: int
    slot_us: int
    tolerance_us: int
    outcome: SpeechAttemptOutcome | None
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None

    def validate(self) -> None:
        if self.attempt_index < 0:
            raise ValidationError("Speech attempt index is invalid", code="TTS_ATTEMPT_INVALID")
        if not self.text.strip() or len(self.text) > 4000:
            raise ValidationError("Speech attempt text is invalid", code="TTS_TEXT_INVALID")
        if not self.provider.strip() or not self.model.strip() or not self.model_revision.strip():
            raise ValidationError("TTS provider metadata is invalid", code="TTS_PROVIDER_INVALID")
        if not self.voice_id.strip() or len(self.voice_id) > 160:
            raise ValidationError("TTS voice identifier is invalid", code="TTS_VOICE_INVALID")
        if self.slot_us <= 0 or self.tolerance_us < 0:
            raise ValidationError("Speech timing is invalid", code="DURATION_SLOT_INVALID")
        if self.speed_factor_ppm < 1_000_000:
            raise ValidationError("Speech speed factor is invalid", code="DURATION_SPEED_INVALID")
        for value in (
            self.measured_duration_us,
            self.trimmed_duration_us,
            self.final_duration_us,
        ):
            if value is not None and value <= 0:
                raise ValidationError(
                    "Speech duration is invalid", code="DURATION_MEASUREMENT_INVALID"
                )
        if self.silence_removed_us < 0:
            raise ValidationError("Removed silence is invalid", code="DURATION_MEASUREMENT_INVALID")


def decide_duration_fit(
    *,
    slot_us: int,
    measured_us: int,
    trimmed_us: int,
    rewrite_attempts_used: int,
    policy: DurationFitPolicy,
) -> DurationFitDecision:
    policy.validate()
    if slot_us <= 0:
        raise ValidationError("Speech slot must be positive", code="DURATION_SLOT_INVALID")
    if measured_us <= 0 or trimmed_us <= 0 or trimmed_us > measured_us:
        raise ValidationError(
            "Measured audio duration is invalid", code="DURATION_MEASUREMENT_INVALID"
        )
    if rewrite_attempts_used < 0:
        raise ValidationError("Rewrite attempt count is invalid", code="DURATION_ATTEMPT_INVALID")

    target_us = slot_us + policy.tolerance_us
    if trimmed_us <= target_us:
        return DurationFitDecision(
            action=DurationFitAction.ACCEPT,
            speed_factor_ppm=1_000_000,
            target_us=target_us,
        )

    required_speed_ppm = ceil(trimmed_us * 1_000_000 / target_us)
    if required_speed_ppm <= policy.max_speed_factor_ppm:
        return DurationFitDecision(
            action=DurationFitAction.SPEED_UP,
            speed_factor_ppm=max(1_000_000, required_speed_ppm),
            target_us=target_us,
        )

    if rewrite_attempts_used < policy.max_rewrite_attempts:
        return DurationFitDecision(
            action=DurationFitAction.REWRITE,
            speed_factor_ppm=1_000_000,
            target_us=target_us,
        )

    return DurationFitDecision(
        action=DurationFitAction.REVIEW,
        speed_factor_ppm=1_000_000,
        target_us=target_us,
    )
