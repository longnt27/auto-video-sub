from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from auto_video_sub_application.ports import OcrProviderError, OcrResult


class RapidOcrProvider:
    """Local RapidOCR adapter with provider-specific objects contained at this boundary."""

    provider_name = "rapidocr"
    model_version = "rapidocr-3.9.2-pp-ocrv6-small-default"

    def __init__(self, *, engine: Any | None = None) -> None:
        self._engine = engine if engine is not None else self._build_engine()

    @staticmethod
    def _build_engine() -> Any:
        try:
            from rapidocr import RapidOCR
        except ImportError as error:
            raise OcrProviderError(
                "RapidOCR is not installed",
                code="OCR_RUNTIME_UNAVAILABLE",
                retryable=False,
            ) from error
        try:
            return RapidOCR()
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
            raw_texts = tuple(str(item).strip() for item in texts_raw)
            raw_scores = tuple(float(item) for item in (scores_raw or ()))
        except (TypeError, ValueError) as error:
            raise OcrProviderError(
                "RapidOCR returned malformed output",
                code="OCR_OUTPUT_INVALID",
                retryable=False,
            ) from error
        if raw_scores and len(raw_scores) != len(raw_texts):
            raise OcrProviderError(
                "RapidOCR returned inconsistent text and score counts",
                code="OCR_OUTPUT_INVALID",
                retryable=False,
            )

        kept: list[tuple[str, float | None]] = []
        for index, text in enumerate(raw_texts):
            if text:
                kept.append((text, raw_scores[index] if raw_scores else None))
        if not kept:
            return OcrResult(
                text="",
                confidence=0.0,
                provider=self.provider_name,
                model_version=self.model_version,
            )

        confidence = (
            sum(score for _, score in kept if score is not None) / len(kept)
            if raw_scores
            else 1.0
        )
        if not 0.0 <= confidence <= 1.0:
            raise OcrProviderError(
                "RapidOCR returned an invalid confidence",
                code="OCR_OUTPUT_INVALID",
                retryable=False,
            )
        return OcrResult(
            text="\n".join(text for text, _ in kept),
            confidence=confidence,
            provider=self.provider_name,
            model_version=self.model_version,
        )
