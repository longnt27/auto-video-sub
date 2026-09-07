from auto_video_sub_domain import (
    OcrObservation,
    SubtitleRegion,
    ValidationError,
    consolidate_observations,
    normalize_ocr_text,
)
import pytest


def observation(time_us: int, text: str, confidence: float = 0.9) -> OcrObservation:
    return OcrObservation(
        time_us=time_us,
        text=text,
        confidence=confidence,
        provider="rapidocr",
        model_version="PP-OCRv6-small",
    )


def test_subtitle_region_rejects_invalid_bounds() -> None:
    with pytest.raises(ValidationError) as error:
        SubtitleRegion(y_start_ratio=0.9, y_end_ratio=0.8).validate()
    assert error.value.code == "OCR_REGION_INVALID"


def test_subtitle_region_rejects_unbounded_sampling() -> None:
    with pytest.raises(ValidationError) as error:
        SubtitleRegion(sample_interval_ms=50).validate()
    assert error.value.code == "OCR_SAMPLE_INTERVAL_INVALID"


def test_normalize_ocr_text_changes_layout_whitespace_only() -> None:
    assert normalize_ocr_text("  你好\n  世界  ") == "你好 世界"


def test_consolidation_merges_repeated_observations_and_tolerates_one_gap() -> None:
    result = consolidate_observations(
        [
            observation(0, "你好"),
            observation(400_000, "你好", 0.8),
            observation(1_200_000, "你好", 1.0),
            observation(1_600_000, "世界"),
        ],
        sample_interval_us=400_000,
        media_duration_us=2_500_000,
    )
    assert len(result) == 2
    assert result[0].text == "你好"
    assert result[0].start_us == 0
    assert result[0].end_us == 1_600_000
    assert result[0].evidence_times_us == (0, 400_000, 1_200_000)
    assert result[0].confidence == pytest.approx(0.9)
    assert result[1].text == "世界"


def test_consolidation_does_not_merge_different_adjacent_text() -> None:
    result = consolidate_observations(
        [observation(0, "甲"), observation(400_000, "乙"), observation(800_000, "甲")],
        sample_interval_us=400_000,
        media_duration_us=2_000_000,
    )
    assert [item.text for item in result] == ["甲", "乙", "甲"]


def test_consolidation_ignores_empty_and_out_of_range_observations() -> None:
    result = consolidate_observations(
        [observation(0, " "), observation(3_000_000, "too late")],
        sample_interval_us=400_000,
        media_duration_us=2_000_000,
    )
    assert result == []
