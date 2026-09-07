from __future__ import annotations

import asyncio
from pathlib import Path

from auto_video_sub_application.speech_ports import AudioTransformResult, TtsProviderError


class FFmpegSpeechAudioProcessor:
    def __init__(
        self,
        *,
        ffmpeg_path: str,
        ffprobe_path: str,
        timeout_seconds: int,
    ) -> None:
        self._ffmpeg_path = ffmpeg_path
        self._ffprobe_path = ffprobe_path
        self._timeout = timeout_seconds

    async def probe_duration(self, source: Path) -> int:
        stdout = await self._run(
            (
                self._ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source),
            ),
            code="TTS_AUDIO_PROBE_FAILED",
        )
        try:
            duration_us = int(float(stdout.strip()) * 1_000_000)
        except ValueError as error:
            raise TtsProviderError(
                "Audio duration is invalid",
                code="TTS_AUDIO_PROBE_INVALID",
                retryable=False,
            ) from error
        if duration_us <= 0:
            raise TtsProviderError(
                "Audio duration is invalid",
                code="TTS_AUDIO_PROBE_INVALID",
                retryable=False,
            )
        return duration_us

    async def trim_edge_silence(self, source: Path, destination: Path) -> AudioTransformResult:
        before = await self.probe_duration(source)
        filter_graph = (
            "silenceremove=start_periods=1:start_duration=0.08:start_threshold=-55dB,"
            "areverse,"
            "silenceremove=start_periods=1:start_duration=0.08:start_threshold=-55dB,"
            "areverse"
        )
        await self._run(
            (
                self._ffmpeg_path,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-vn",
                "-af",
                filter_graph,
                "-c:a",
                "pcm_s16le",
                "-y",
                str(destination),
            ),
            code="TTS_SILENCE_TRIM_FAILED",
        )
        after = await self.probe_duration(destination)
        if after > before + 10_000:
            raise TtsProviderError(
                "Silence trim produced invalid duration",
                code="TTS_SILENCE_TRIM_INVALID",
                retryable=False,
            )
        return AudioTransformResult(
            duration_us=after,
            silence_removed_us=max(0, before - after),
        )

    async def speed_up(
        self, source: Path, destination: Path, *, speed_factor_ppm: int
    ) -> AudioTransformResult:
        if not 1_000_000 <= speed_factor_ppm <= 1_500_000:
            raise TtsProviderError(
                "Requested speech speed is outside the safe range",
                code="DURATION_SPEED_INVALID",
                retryable=False,
            )
        factor = speed_factor_ppm / 1_000_000
        await self._run(
            (
                self._ffmpeg_path,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-vn",
                "-af",
                f"atempo={factor:.6f}",
                "-c:a",
                "pcm_s16le",
                "-y",
                str(destination),
            ),
            code="TTS_SPEED_ADJUST_FAILED",
        )
        return AudioTransformResult(duration_us=await self.probe_duration(destination))

    async def _run(self, command: tuple[str, ...], *, code: str) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as error:
            raise TtsProviderError(
                "Audio executable could not be started",
                code="TTS_AUDIO_RUNTIME_UNAVAILABLE",
                retryable=False,
            ) from error
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=self._timeout)
        except TimeoutError as error:
            process.kill()
            await process.wait()
            raise TtsProviderError(
                "Audio processing exceeded its timeout",
                code=f"{code}_TIMEOUT",
                retryable=True,
            ) from error
        except asyncio.CancelledError:
            process.kill()
            await process.wait()
            raise
        if process.returncode != 0:
            raise TtsProviderError(
                "Audio processing failed",
                code=code,
                retryable=False,
            )
        return stdout.decode(errors="replace")
