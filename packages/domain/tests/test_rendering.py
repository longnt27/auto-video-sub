from datetime import UTC, datetime
from uuid import UUID

import pytest
from auto_video_sub_domain.errors import ValidationError
from auto_video_sub_domain.rendering import OriginalAudioPolicy, RenderJob, RenderStatus


def _job(*, policy: OriginalAudioPolicy, gain: int) -> RenderJob:
    now = datetime.now(UTC)
    return RenderJob(
        id=UUID(int=1),
        project_id=UUID(int=2),
        media_asset_id=UUID(int=3),
        status=RenderStatus.PROCESSING,
        workflow_id=None,
        input_fingerprint="a" * 64,
        audio_policy=policy,
        original_audio_gain_ppm=gain,
        renderer_version="ffmpeg-libass-v1",
        font_filename="NotoSans-Regular.ttf",
        font_checksum_sha256="b" * 64,
        manifest_artifact_id=None,
        subtitle_artifact_id=None,
        output_artifact_id=None,
        validation_artifact_id=None,
        error_code=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.parametrize(
    ("policy", "gain"),
    [
        (OriginalAudioPolicy.RETAIN, 1_000_000),
        (OriginalAudioPolicy.REDUCE, 200_000),
        (OriginalAudioPolicy.REMOVE, 0),
    ],
)
def test_render_job_accepts_exact_audio_policy_gain_pairs(
    policy: OriginalAudioPolicy, gain: int
) -> None:
    _job(policy=policy, gain=gain).validate()


@pytest.mark.parametrize(
    ("policy", "gain"),
    [
        (OriginalAudioPolicy.RETAIN, 999_999),
        (OriginalAudioPolicy.REDUCE, 0),
        (OriginalAudioPolicy.REDUCE, 1_000_000),
        (OriginalAudioPolicy.REMOVE, 1),
    ],
)
def test_render_job_rejects_audio_policy_gain_mismatch(
    policy: OriginalAudioPolicy, gain: int
) -> None:
    with pytest.raises(ValidationError, match="audio"):
        _job(policy=policy, gain=gain).validate()


def test_render_job_requires_pinned_font_checksum() -> None:
    value = _job(policy=OriginalAudioPolicy.REMOVE, gain=0)
    invalid = RenderJob(
        **{field: getattr(value, field) for field in value.__dataclass_fields__ if field != "font_checksum_sha256"},
        font_checksum_sha256="floating-font",
    )
    with pytest.raises(ValidationError, match="checksum"):
        invalid.validate()
