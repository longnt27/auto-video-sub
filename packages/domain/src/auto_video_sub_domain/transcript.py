from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from auto_video_sub_domain.errors import ValidationError

_WHITESPACE = re.compile(r"\s+")


class TranscriptStatus(StrEnum):
    NOT_STARTED = "not_started"
    PROCESSING = "processing"
    WAITING_FOR_REVIEW = "waiting_for_review"
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceRevisionOrigin(StrEnum):
    OCR = "ocr"
    USER = "user"
    IMPORT = "import"


@dataclass(frozen=True, slots=True)
class SubtitleRegion:
    x_start_ratio: float = 0.05
    x_end_ratio: float = 0.95
    y_start_ratio: float = 0.68
    y_end_ratio: float = 0.98
    sample_interval_ms: int = 400

    def validate(self) -> None:
        for name, value in (
            ("x_start_ratio", self.x_start_ratio),
            ("x_end_ratio", self.x_end_ratio),
            ("y_start_ratio", self.y_start_ratio),
            ("y_end_ratio", self.y_end_ratio),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValidationError(
                    f"{name} must be between 0 and 1",
                    code="OCR_REGION_INVALID",
                )
        if self.x_start_ratio >= self.x_end_ratio or self.y_start_ratio >= self.y_end_ratio:
            raise ValidationError("Subtitle region has invalid bounds", code="OCR_REGION_INVALID")
        if self.sample_interval_ms < 100 or self.sample_interval_ms > 5000:
            raise ValidationError(
                "Subtitle sampling interval must be between 100 and 5000 ms",
                code="OCR_SAMPLE_INTERVAL_INVALID",
            )


@dataclass(frozen=True, slots=True)
class OcrObservation:
    time_us: int
    text: str
    confidence: float
    provider: str
    model_version: str

    def validate(self) -> None:
        if self.time_us < 0:
            raise ValidationError("OCR observation time is invalid", code="OCR_TIME_INVALID")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationError("OCR confidence is invalid", code="OCR_CONFIDENCE_INVALID")
        if not self.provider or not self.model_version:
            raise ValidationError("OCR provider metadata is required", code="OCR_METADATA_INVALID")


@dataclass(frozen=True, slots=True)
class ConsolidatedSegment:
    start_us: int
    end_us: int
    text: str
    confidence: float
    evidence_times_us: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SourceRevision:
    id: UUID
    subtitle_segment_id: UUID
    version: int
    text: str
    origin: SourceRevisionOrigin
    confidence: float | None
    editor_id: UUID | None
    parent_revision_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SubtitleSegment:
    id: UUID
    project_id: UUID
    media_asset_id: UUID
    ordinal: int
    start_us: int
    end_us: int
    current_revision: SourceRevision
    version: int
    created_at: datetime
    updated_at: datetime


def normalize_ocr_text(value: str) -> str:
    """Normalize layout whitespace without rewriting semantic content."""

    return _WHITESPACE.sub(" ", value).strip()


def consolidate_observations(
    observations: list[OcrObservation],
    *,
    sample_interval_us: int,
    media_duration_us: int,
    max_gap_samples: int = 2,
) -> list[ConsolidatedSegment]:
    if sample_interval_us <= 0 or media_duration_us <= 0:
        raise ValidationError("Transcript timing configuration is invalid", code="OCR_TIMING_INVALID")
    if max_gap_samples < 1 or max_gap_samples > 10:
        raise ValidationError("OCR consolidation gap is invalid", code="OCR_GAP_INVALID")

    cleaned: list[OcrObservation] = []
    for observation in sorted(observations, key=lambda item: item.time_us):
        observation.validate()
        text = normalize_ocr_text(observation.text)
        if not text:
            continue
        if observation.time_us >= media_duration_us:
            continue
        cleaned.append(
            OcrObservation(
                time_us=observation.time_us,
                text=text,
                confidence=observation.confidence,
                provider=observation.provider,
                model_version=observation.model_version,
            )
        )

    if not cleaned:
        return []

    groups: list[list[OcrObservation]] = []
    current: list[OcrObservation] = [cleaned[0]]
    max_gap_us = sample_interval_us * max_gap_samples
    for observation in cleaned[1:]:
        previous = current[-1]
        if observation.text == previous.text and observation.time_us - previous.time_us <= max_gap_us:
            current.append(observation)
        else:
            groups.append(current)
            current = [observation]
    groups.append(current)

    segments: list[ConsolidatedSegment] = []
    for group in groups:
        start_us = group[0].time_us
        end_us = min(media_duration_us, group[-1].time_us + sample_interval_us)
        if end_us <= start_us:
            end_us = min(media_duration_us, start_us + 1)
        if end_us <= start_us:
            continue
        confidence = sum(item.confidence for item in group) / len(group)
        segments.append(
            ConsolidatedSegment(
                start_us=start_us,
                end_us=end_us,
                text=group[0].text,
                confidence=confidence,
                evidence_times_us=tuple(item.time_us for item in group),
            )
        )
    return segments
