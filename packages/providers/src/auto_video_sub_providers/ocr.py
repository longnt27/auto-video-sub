from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from auto_video_sub_application.ports import OcrProviderError, OcrResult


class RapidOcrProvider:
    """Local RapidOCR adapter with provider-specific objects contained at this boundary."""

    provider_name = "rapidocr"
    model_version = "rapidocr-3.9-pp-ocrv6-small-default"

    def __init__(self) -> None:
        try:
            from rapidocr import RapidOCR
        except ImportError as error:
            raise OcrProviderError(
                "RapidOCR is not installed",
                code="OCR_RUNTIME_UNAVAILABLE",
                retryable=False,
            ) from error
        try:
            self._engine: Any = RapidOCR()
        except Exception as error:
            raise OcrProviderError(
                "RapidOCR could not initialize its local models",
                code="OCR_MODEL_UNAVAILABLE",
                retryable=False,
            ) from error

    async def recognize(self, path: Path) -> OcrResult:
        try:
            result = await asyncio.to_thread(self._engine, str(path))
        except Exception as error:
            raise OcrProviderError(
                "RapidOCR inference failed",
                code="OCR_INFERENCE_FAILED",
                retryable=True,
            ) from error

        texts_raw = getattr(result, "txts", None)
        scores_raw = getattr(result, "scores", None)
        if texts_raw is None:
            return OcrResult(
                text="",
                confidence=0.0,
                provider=self.provider_name,
                model_version=self.model_version,
            )
        try:
            texts = [str(item).strip() for item in texts_raw if str(item).strip()]
            scores = [float(item) for item in (scores_raw or ())]
        except (TypeError, ValueError) as error:
            raise OcrProviderError(
                "RapidOCR returned malformed output",
                code="OCR_OUTPUT_INVALID",
                retryable=False,
            ) from error
        if scores and len(scores) != len(tuple(texts_raw)):
            raise OcrProviderError(
                "RapidOCR returned inconsistent text and score counts",
                code="OCR_OUTPUT_INVALID",
                retryable=False,
            )
        confidence = sum(scores) / len(scores) if scores else (1.0 if texts else 0.0)
        if not 0.0 <= confidence <= 1.0:
            raise OcrProviderError(
                "RapidOCR returned an invalid confidence",
                code="OCR_OUTPUT_INVALID",
                retryable=False,
            )
        return OcrResult(
            text="\n".join(texts),
            confidence=confidence,
            provider=self.provider_name,
            model_version=self.model_version,
        )
