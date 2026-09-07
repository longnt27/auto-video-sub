from __future__ import annotations

import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from auto_video_sub_application.speech_ports import (
    RewriteProviderError,
    RewriteRequest,
    RewriteResult,
)


class LlamaCppRewriteProvider:
    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        model_revision: str,
        timeout_seconds: int,
    ) -> None:
        self._endpoint = endpoint.strip()
        self._model = model.strip()
        self._model_revision = model_revision.strip()
        self._timeout = timeout_seconds

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def model_revision(self) -> str:
        return self._model_revision

    async def rewrite(self, request: RewriteRequest) -> RewriteResult:
        if not self._endpoint or not self._model or not self._model_revision:
            raise RewriteProviderError(
                "Local rewrite model is not configured",
                code="DURATION_REWRITE_UNCONFIGURED",
                retryable=False,
            )
        return await asyncio.to_thread(self._rewrite_sync, request)

    def _rewrite_sync(self, request: RewriteRequest) -> RewriteResult:
        protected = ", ".join(request.protected_terms) or "(none)"
        previous = "\n".join(f"- {value}" for value in request.previous_rewrites) or "(none)"
        system = (
            "You shorten Vietnamese dialogue for speech timing. Preserve meaning, facts, names, "
            "relationships, tone, and every protected term. Never translate Chinese, alter timing, "
            "merge/split segments, add jokes/events, or omit semantic content. Return strict JSON "
            "with exactly segment_id and text."
        )
        user = (
            f"segment_id={request.segment_id}\n"
            f"tone={request.tone.value}\n"
            f"target_us={request.target_duration_us}\n"
            f"measured_us={request.measured_duration_us}\n"
            f"protected_terms={protected}\n"
            f"previous_rewrites:\n{previous}\n"
            f"text:\n{request.text}"
        )
        payload = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            }
        ).encode()
        http_request = Request(
            self._endpoint,
            data=payload,
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=self._timeout) as response:
                body = response.read()
        except HTTPError as error:
            raise RewriteProviderError(
                "Local rewrite request failed",
                code="DURATION_REWRITE_HTTP_ERROR",
                retryable=error.code == 429 or error.code >= 500,
            ) from error
        except (URLError, TimeoutError) as error:
            raise RewriteProviderError(
                "Local rewrite runtime is unavailable",
                code="DURATION_REWRITE_UNAVAILABLE",
                retryable=True,
            ) from error
        try:
            envelope = json.loads(body)
            content = envelope["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            segment_id = UUID(str(parsed["segment_id"]))
            text = str(parsed["text"]).strip()
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RewriteProviderError(
                "Local rewrite returned invalid structured output",
                code="DURATION_REWRITE_INVALID",
                retryable=False,
            ) from error
        if segment_id != request.segment_id or not text or len(text) > 4000:
            raise RewriteProviderError(
                "Local rewrite violated the segment contract",
                code="DURATION_REWRITE_INVALID",
                retryable=False,
            )
        if any(term not in text for term in request.protected_terms):
            raise RewriteProviderError(
                "Local rewrite removed protected terminology",
                code="DURATION_REWRITE_PROTECTED_TERM",
                retryable=False,
            )
        return RewriteResult(
            segment_id=segment_id,
            text=text,
            model=self._model,
            model_revision=self._model_revision,
        )
