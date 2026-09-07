import pytest
from auto_video_sub_domain import (
    DurationFitAction,
    DurationFitPolicy,
    ValidationError,
    decide_duration_fit,
)


def test_duration_fit_accepts_trimmed_audio_with_tolerance() -> None:
    decision = decide_duration_fit(
        slot_us=2_000_000,
        measured_us=2_250_000,
        trimmed_us=2_080_000,
        rewrite_attempts_used=0,
        policy=DurationFitPolicy(),
    )

    assert decision.action is DurationFitAction.ACCEPT
    assert decision.speed_factor_ppm == 1_000_000
    assert decision.target_us == 2_100_000


def test_duration_fit_uses_bounded_speed_up() -> None:
    decision = decide_duration_fit(
        slot_us=2_000_000,
        measured_us=2_300_000,
        trimmed_us=2_200_000,
        rewrite_attempts_used=0,
        policy=DurationFitPolicy(),
    )

    assert decision.action is DurationFitAction.SPEED_UP
    assert 1_000_000 < decision.speed_factor_ppm <= 1_080_000


def test_duration_fit_rewrites_then_escalates_to_review() -> None:
    policy = DurationFitPolicy(max_rewrite_attempts=2)

    first = decide_duration_fit(
        slot_us=1_000_000,
        measured_us=1_800_000,
        trimmed_us=1_700_000,
        rewrite_attempts_used=1,
        policy=policy,
    )
    exhausted = decide_duration_fit(
        slot_us=1_000_000,
        measured_us=1_800_000,
        trimmed_us=1_700_000,
        rewrite_attempts_used=2,
        policy=policy,
    )

    assert first.action is DurationFitAction.REWRITE
    assert exhausted.action is DurationFitAction.REVIEW


def test_duration_fit_rejects_invalid_measurements() -> None:
    with pytest.raises(ValidationError) as error:
        decide_duration_fit(
            slot_us=1_000_000,
            measured_us=1_000_000,
            trimmed_us=1_100_000,
            rewrite_attempts_used=0,
            policy=DurationFitPolicy(),
        )

    assert error.value.code == "DURATION_MEASUREMENT_INVALID"
