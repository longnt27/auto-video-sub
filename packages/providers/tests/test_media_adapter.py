from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest
from auto_video_sub_providers import FFmpegMediaProcessor


@pytest.mark.media
async def test_ffmpeg_probe_and_proxy_are_structurally_valid(tmp_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.fail("ffmpeg and ffprobe are required for the media test suite")
    source = tmp_path / "fixture.mp4"
    proxy = tmp_path / "proxy.mp4"
    await asyncio.to_thread(
        subprocess.run,
        [
            ffmpeg,
            "-nostdin",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x240:d=0.5",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-shortest",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-y",
            str(source),
        ],
        check=True,
        timeout=30,
    )
    processor = FFmpegMediaProcessor(
        ffmpeg_path=ffmpeg,
        ffprobe_path=ffprobe,
        probe_timeout_seconds=30,
        proxy_timeout_seconds=60,
    )
    processor.validate_magic(source, "video/mp4")
    source_probe = await processor.probe(source)
    await processor.generate_proxy(source, proxy)
    proxy_probe = await processor.probe(proxy)

    assert source_probe.width == 320
    assert source_probe.video_codec == "h264"
    assert proxy_probe.width <= 1280
    assert proxy_probe.height <= 720
    assert proxy_probe.video_codec == "h264"
