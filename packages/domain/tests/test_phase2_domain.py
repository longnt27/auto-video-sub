from __future__ import annotations

import pytest
from auto_video_sub_domain import (
    MediaLimits,
    MediaProbe,
    ValidationError,
    new_uuid7,
    validate_probe,
)


def test_uuid7_contains_expected_version_and_variant() -> None:
    identifier = new_uuid7()
    assert identifier.version == 7
    assert identifier.variant == "specified in RFC 4122"


def test_media_limits_reject_extreme_dimensions() -> None:
    limits = MediaLimits(
        max_upload_bytes=1000,
        max_duration_us=10_000_000,
        max_width=1920,
        max_height=1080,
        max_frame_rate=60,
        max_streams=4,
        allowed_content_types=frozenset({"video/mp4"}),
    )
    probe = MediaProbe("mov,mp4", 1_000_000, 7680, 4320, 30, "h264", "aac", 2)
    with pytest.raises(ValidationError, match="dimensions") as captured:
        validate_probe(probe, limits)
    assert captured.value.code == "MEDIA_DIMENSIONS_EXCEEDED"
