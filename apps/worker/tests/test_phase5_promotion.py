from __future__ import annotations

import io
import wave

import pytest
from auto_video_sub_worker.phase5_promotion import _inspect_wav, _percentile


def _wav(*, sample_rate: int = 48_000, channels: int = 1, frames: int = 48_000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\0\0" * frames * channels)
    return buffer.getvalue()


def test_promotion_percentiles_are_deterministic() -> None:
    values = [4.0, 1.0, 3.0, 2.0]

    assert _percentile(values, 0.50) == 2.0
    assert _percentile(values, 0.95) == 4.0
    assert _percentile([], 0.95) == 0.0


def test_promotion_wav_requires_mono_48khz_audio() -> None:
    sample_rate, channels, duration = _inspect_wav(_wav())

    assert sample_rate == 48_000
    assert channels == 1
    assert duration == 1.0

    with pytest.raises(RuntimeError, match="Unexpected VieNeu WAV shape"):
        _inspect_wav(_wav(sample_rate=44_100))
    with pytest.raises(RuntimeError, match="Unexpected VieNeu WAV shape"):
        _inspect_wav(_wav(channels=2))
