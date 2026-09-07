from __future__ import annotations

import asyncio
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from auto_video_sub_application.ports import ExtractedSubtitleFrame, MediaProcessError
from auto_video_sub_domain import MediaProbe, SubtitleRegion, ValidationError


class FFmpegMediaProcessor:
    def __init__(
        self,
        *,
        ffmpeg_path: str,
        ffprobe_path: str,
        probe_timeout_seconds: int,
        proxy_timeout_seconds: int,
    ) -> None:
        self._ffmpeg_path = ffmpeg_path
        self._ffprobe_path = ffprobe_path
        self._probe_timeout = probe_timeout_seconds
        self._proxy_timeout = proxy_timeout_seconds

    @staticmethod
    def validate_magic(path: Path, declared_content_type: str) -> None:
        with path.open("rb") as source:
            prefix = source.read(64)
        if declared_content_type in {"video/mp4", "video/quicktime"}:
            valid = len(prefix) >= 12 and prefix[4:8] == b"ftyp"
        elif declared_content_type in {"video/x-matroska", "video/webm"}:
            valid = prefix.startswith(b"\x1aE\xdf\xa3")
        else:
            valid = False
        if not valid:
            raise ValidationError(
                "Media signature does not match the declared type",
                code="MEDIA_MAGIC_MISMATCH",
            )

    async def probe(self, path: Path) -> MediaProbe:
        command = (
            self._ffprobe_path,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        )
        stdout = await self._run(
            command,
            timeout_seconds=self._probe_timeout,
            code="MEDIA_PROBE_FAILED",
        )
        try:
            payload: dict[str, Any] = json.loads(stdout)
            streams = payload.get("streams", [])
            if not isinstance(streams, list):
                raise ValueError("streams is not a list")
            video = next(item for item in streams if item.get("codec_type") == "video")
            audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
            format_info = payload.get("format", {})
            duration_value = format_info.get("duration") or video.get("duration")
            duration_us = int(float(duration_value) * 1_000_000)
            frame_rate_raw = video.get("avg_frame_rate") or video.get("r_frame_rate")
            frame_rate = float(Fraction(str(frame_rate_raw)))
            return MediaProbe(
                format_name=str(format_info.get("format_name", "unknown")),
                duration_us=duration_us,
                width=int(video["width"]),
                height=int(video["height"]),
                frame_rate=frame_rate,
                video_codec=str(video["codec_name"]),
                audio_codec=str(audio["codec_name"]) if audio is not None else None,
                stream_count=len(streams),
            )
        except (KeyError, StopIteration, TypeError, ValueError, ZeroDivisionError) as error:
            raise ValidationError(
                "Media probe output is incomplete or invalid",
                code="MEDIA_PROBE_INVALID",
            ) from error

    async def generate_proxy(self, source: Path, destination: Path) -> None:
        command = (
            self._ffmpeg_path,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            "-y",
            str(destination),
        )
        await self._run(
            command,
            timeout_seconds=self._proxy_timeout,
            code="MEDIA_PROXY_FAILED",
        )
        if not destination.is_file() or destination.stat().st_size <= 0:
            raise MediaProcessError(
                "FFmpeg did not create a usable proxy",
                code="MEDIA_PROXY_EMPTY",
                retryable=False,
            )

    async def extract_subtitle_frames(
        self, source: Path, destination: Path, region: SubtitleRegion
    ) -> list[ExtractedSubtitleFrame]:
        region.validate()
        destination.mkdir(parents=True, exist_ok=True)
        width = region.x_end_ratio - region.x_start_ratio
        height = region.y_end_ratio - region.y_start_ratio
        filter_graph = (
            f"fps=1000/{region.sample_interval_ms},"
            f"crop=iw*{width:.8f}:ih*{height:.8f}:"
            f"iw*{region.x_start_ratio:.8f}:ih*{region.y_start_ratio:.8f}"
        )
        pattern = destination / "frame-%08d.jpg"
        command = (
            self._ffmpeg_path,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            filter_graph,
            "-q:v",
            "4",
            "-y",
            str(pattern),
        )
        await self._run(
            command,
            timeout_seconds=self._proxy_timeout,
            code="MEDIA_SUBTITLE_EXTRACTION_FAILED",
        )
        paths = sorted(destination.glob("frame-*.jpg"))
        return [
            ExtractedSubtitleFrame(
                time_us=index * region.sample_interval_ms * 1000,
                path=path,
            )
            for index, path in enumerate(paths)
        ]

    @staticmethod
    async def _terminate(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            process.kill()
            await process.wait()

    async def _run(
        self,
        command: tuple[str, ...],
        *,
        timeout_seconds: int,
        code: str,
    ) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as error:
            raise MediaProcessError(
                "Media executable could not be started",
                code="MEDIA_EXECUTABLE_UNAVAILABLE",
                retryable=False,
            ) from error
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
        except TimeoutError as error:
            await self._terminate(process)
            raise MediaProcessError(
                "Media command exceeded its timeout",
                code=f"{code}_TIMEOUT",
                retryable=True,
            ) from error
        except asyncio.CancelledError:
            await self._terminate(process)
            raise
        if process.returncode != 0:
            detail = stderr.decode(errors="replace")[-1000:]
            raise MediaProcessError(
                f"Media command failed: {detail}",
                code=code,
                retryable=False,
            )
        return stdout.decode()
