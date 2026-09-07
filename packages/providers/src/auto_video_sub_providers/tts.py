from __future__ import annotations

import asyncio
import io
import wave
from pathlib import Path
from typing import Any

from auto_video_sub_application.speech_ports import TtsProviderError, TtsRequest, TtsResult


class VieNeuTtsProvider:
    def __init__(
        self,
        *,
        model_root: str,
        model_revision: str,
        voice_id: str,
        precision: str = "fp32",
        threads: int = 0,
    ) -> None:
        self._model_root = Path(model_root).expanduser() if model_root.strip() else None
        self._model_revision = model_revision.strip()
        self._voice_id = voice_id.strip()
        self._precision = precision.strip().lower()
        self._threads = threads
        self._engine: Any | None = None
        self._lock = asyncio.Lock()

    @property
    def provider_name(self) -> str:
        return "vieneu"

    @property
    def model_name(self) -> str:
        return "VieNeu-TTS-v3-Turbo"

    @property
    def model_revision(self) -> str:
        return self._model_revision

    @property
    def sample_rate_hz(self) -> int:
        return 48_000

    async def _get_engine(self) -> Any:
        async with self._lock:
            if self._engine is not None:
                return self._engine
            if self._model_root is None or not self._model_root.is_dir():
                raise TtsProviderError(
                    "Pinned VieNeu model snapshot is not configured",
                    code="TTS_MODEL_UNCONFIGURED",
                    retryable=False,
                )
            if not self._model_revision:
                raise TtsProviderError(
                    "VieNeu model revision is not configured",
                    code="TTS_MODEL_REVISION_UNCONFIGURED",
                    retryable=False,
                )
            if self._precision not in {"fp32", "int8"}:
                raise TtsProviderError(
                    "VieNeu ONNX precision is invalid",
                    code="TTS_MODEL_CONFIGURATION_INVALID",
                    retryable=False,
                )
            subfolder = "onnx_update" if self._precision == "fp32" else "onnx_int8"
            onnx_dir = self._model_root / subfolder
            codec_dir = self._model_root / "codec"
            if not onnx_dir.is_dir() or not codec_dir.is_dir():
                raise TtsProviderError(
                    "Pinned VieNeu ONNX backbone or codec directory is missing",
                    code="TTS_MODEL_UNCONFIGURED",
                    retryable=False,
                )
            try:
                from vieneu import Vieneu
            except ImportError as error:
                raise TtsProviderError(
                    "VieNeu runtime is unavailable",
                    code="TTS_RUNTIME_UNAVAILABLE",
                    retryable=False,
                ) from error
            try:
                self._engine = await asyncio.to_thread(
                    Vieneu,
                    mode="v3turbo",
                    backend="onnx",
                    backbone_repo=str(self._model_root),
                    onnx_dir=str(onnx_dir),
                    codec_dir=str(codec_dir),
                    precision=self._precision,
                    threads=self._threads,
                )
            except Exception as error:
                raise TtsProviderError(
                    "VieNeu model could not be loaded",
                    code="TTS_MODEL_LOAD_FAILED",
                    retryable=False,
                ) from error
            return self._engine

    async def synthesize(self, request: TtsRequest) -> TtsResult:
        text = request.text.strip()
        voice_id = request.voice_id.strip() or self._voice_id
        if not text:
            raise TtsProviderError("TTS input is empty", code="TTS_TEXT_EMPTY", retryable=False)
        if not voice_id:
            raise TtsProviderError(
                "TTS voice is not configured", code="TTS_VOICE_UNCONFIGURED", retryable=False
            )
        engine = await self._get_engine()
        try:
            waveform = await asyncio.to_thread(engine.infer, text, voice=voice_id)
            wav_bytes = self._encode_wav(waveform, self.sample_rate_hz)
        except TtsProviderError:
            raise
        except Exception as error:
            raise TtsProviderError(
                "VieNeu synthesis failed",
                code="TTS_SYNTHESIS_FAILED",
                retryable=False,
            ) from error
        if len(wav_bytes) <= 44:
            raise TtsProviderError(
                "VieNeu returned empty audio", code="TTS_AUDIO_INVALID", retryable=False
            )
        return TtsResult(wav_bytes=wav_bytes, sample_rate_hz=self.sample_rate_hz)

    @staticmethod
    def _encode_wav(waveform: Any, sample_rate_hz: int) -> bytes:
        try:
            pcm = (waveform.clip(-1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        except Exception as error:
            raise TtsProviderError(
                "VieNeu returned malformed audio", code="TTS_AUDIO_INVALID", retryable=False
            ) from error
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate_hz)
            output.writeframes(pcm)
        return buffer.getvalue()
