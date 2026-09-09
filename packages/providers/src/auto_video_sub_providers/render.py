from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from uuid import UUID

from auto_video_sub_application.render_ports import (
    FrozenRenderInput,
    RenderValidationResult,
)
from auto_video_sub_domain.rendering import OriginalAudioPolicy


class RenderProcessError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def _ass_timestamp(value_us: int) -> str:
    centiseconds = max(0, value_us // 10_000)
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    seconds, centis = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}"


def _ass_color(hex_color: str, *, alpha: int = 0) -> str:
    value = hex_color.removeprefix("#")
    red = value[0:2]
    green = value[2:4]
    blue = value[4:6]
    return f"&H{alpha:02X}{blue}{green}{red}"


def _safe_ass_text(text: str) -> str:
    return (
        text.replace("\\", chr(0xFF3C))
        .replace("{", chr(0xFF5B))
        .replace("}", chr(0xFF5D))
        .replace("\r\n", "\\N")
        .replace("\r", "\\N")
        .replace("\n", "\\N")
    )


class FFmpegRenderProcessor:
    def __init__(
        self,
        *,
        ffmpeg_path: str,
        ffprobe_path: str,
        render_timeout_seconds: int,
        validation_timeout_seconds: int,
        duration_tolerance_us: int,
    ) -> None:
        self._ffmpeg_path = ffmpeg_path
        self._ffprobe_path = ffprobe_path
        self._render_timeout_seconds = render_timeout_seconds
        self._validation_timeout_seconds = validation_timeout_seconds
        self._duration_tolerance_us = duration_tolerance_us

    @staticmethod
    async def _run(
        argv: Sequence[str],
        *,
        timeout_seconds: int,
        error_code: str,
    ) -> tuple[bytes, bytes]:
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        except TimeoutError as error:
            raise RenderProcessError(
                "Media process exceeded its time limit",
                code=error_code,
                retryable=True,
            ) from error
        except OSError as error:
            raise RenderProcessError(
                "Media runtime could not be started",
                code=error_code,
                retryable=False,
            ) from error
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace")[-2000:]
            raise RenderProcessError(
                f"Media process failed: {detail}",
                code=error_code,
                retryable=False,
            )
        return stdout, stderr

    def write_ass(self, render_input: FrozenRenderInput, destination: Path) -> None:
        style = render_input.subtitle_style
        style.validate()
        font_size = max(1, round(render_input.height * style.font_size_pct / 100))
        margin_v = max(8, round(render_input.height * 0.05))
        background_alpha = round(255 * (100 - style.background_opacity_pct) / 100)
        border_style = 3 if style.background_opacity_pct > 0 else 1
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {render_input.width}",
            f"PlayResY: {render_input.height}",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "YCbCr Matrix: TV.709",
            "",
            "[V4+ Styles]",
            (
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
                "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
                "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                "Alignment, MarginL, MarginR, MarginV, Encoding"
            ),
            (
                f"Style: Default,{style.font_family},{font_size},"
                f"{_ass_color(style.text_color)},{_ass_color(style.text_color)},"
                f"{_ass_color(style.outline_color)},"
                f"{_ass_color(style.background_color, alpha=background_alpha)},"
                "0,0,0,0,100,100,0,0,"
                f"{border_style},{style.outline_px:.3f},{style.shadow_px:.3f},"
                f"2,20,20,{margin_v},1"
            ),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        for track in sorted(render_input.speech_tracks, key=lambda item: item.ordinal):
            lines.append(
                "Dialogue: 0,"
                f"{_ass_timestamp(track.start_us)},{_ass_timestamp(track.end_us)},"
                f"Default,,0,0,0,,{_safe_ass_text(track.text)}"
            )
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")

    async def render(
        self,
        *,
        render_input: FrozenRenderInput,
        original_path: Path,
        speech_paths: Mapping[UUID, Path],
        ass_path: Path,
        output_path: Path,
    ) -> None:
        ordered_tracks = sorted(render_input.speech_tracks, key=lambda item: item.ordinal)
        argv: list[str] = [
            self._ffmpeg_path,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i",
            str(original_path),
        ]
        for track in ordered_tracks:
            path = speech_paths.get(track.audio_artifact_id)
            if path is None:
                raise RenderProcessError(
                    "Frozen speech artifact is missing from render inputs",
                    code="RENDER_INPUT_MISSING",
                    retryable=False,
                )
            argv.extend(["-i", str(path)])

        video_filter = f"ass={ass_path}"
        filter_parts: list[str] = []
        audio_labels: list[str] = []
        speech_offset = 1
        for index, track in enumerate(ordered_tracks):
            delay_ms = max(0, track.start_us // 1000)
            label = f"speech{index}"
            filter_parts.append(f"[{speech_offset + index}:a]adelay={delay_ms}:all=1[{label}]")
            audio_labels.append(f"[{label}]")

        if (
            render_input.source_has_audio
            and render_input.audio_policy is not OriginalAudioPolicy.REMOVE
        ):
            gain = render_input.original_audio_gain_ppm / 1_000_000
            filter_parts.append(f"[0:a]volume={gain:.6f}[original_audio]")
            audio_labels.insert(0, "[original_audio]")
        if not audio_labels:
            raise RenderProcessError(
                "Render has no audio source",
                code="RENDER_AUDIO_MISSING",
                retryable=False,
            )
        if len(audio_labels) == 1:
            filter_parts.append(f"{audio_labels[0]}anull[aout]")
        else:
            filter_parts.append(
                "".join(audio_labels)
                + f"amix=inputs={len(audio_labels)}:duration=longest:dropout_transition=0[aout]"
            )

        argv.extend(
            [
                "-vf",
                video_filter,
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                "0:v:0",
                "-map",
                "[aout]",
                "-t",
                f"{render_input.duration_us / 1_000_000:.6f}",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )
        await self._run(
            argv,
            timeout_seconds=self._render_timeout_seconds,
            error_code="RENDER_FFMPEG_FAILED",
        )
        if not output_path.is_file() or output_path.stat().st_size <= 0:
            raise RenderProcessError(
                "Renderer produced no output",
                code="RENDER_OUTPUT_EMPTY",
                retryable=False,
            )

    async def validate(
        self,
        *,
        output_path: Path,
        expected_duration_us: int,
        expected_width: int,
        expected_height: int,
    ) -> RenderValidationResult:
        stdout, _ = await self._run(
            [
                self._ffprobe_path,
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(output_path),
            ],
            timeout_seconds=self._validation_timeout_seconds,
            error_code="RENDER_VALIDATION_PROBE_FAILED",
        )
        try:
            payload = json.loads(stdout)
            streams = list(payload["streams"])
            format_payload = payload["format"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RenderProcessError(
                "Rendered output probe was malformed",
                code="RENDER_VALIDATION_INVALID",
                retryable=False,
            ) from error

        video = next((item for item in streams if item.get("codec_type") == "video"), None)
        audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
        issues: list[str] = []
        if video is None:
            issues.append("missing_video")
            width = 0
            height = 0
            video_codec = ""
        else:
            width = int(video.get("width", 0))
            height = int(video.get("height", 0))
            video_codec = str(video.get("codec_name", ""))
            if width != expected_width or height != expected_height:
                issues.append("unexpected_dimensions")
        if audio is None:
            issues.append("missing_audio")
            audio_codec = None
        else:
            audio_codec = str(audio.get("codec_name", "")) or None
        try:
            duration_us = round(float(format_payload.get("duration", "0")) * 1_000_000)
        except (TypeError, ValueError):
            duration_us = 0
        if duration_us <= 0:
            issues.append("invalid_duration")
        elif abs(duration_us - expected_duration_us) > self._duration_tolerance_us:
            issues.append("duration_mismatch")
        if video_codec != "h264":
            issues.append("unexpected_video_codec")
        if audio_codec != "aac":
            issues.append("unexpected_audio_codec")
        if output_path.stat().st_size <= 0:
            issues.append("empty_file")
        return RenderValidationResult(
            valid=not issues,
            duration_us=duration_us,
            width=width,
            height=height,
            video_codec=video_codec,
            audio_codec=audio_codec,
            stream_count=len(streams),
            issues=tuple(issues),
        )
