from __future__ import annotations

import asyncio
import hashlib
import json
import socket
import tempfile
from collections.abc import Awaitable
from pathlib import Path
from uuid import UUID

from auto_video_sub_application.ports import (
    MediaArtifactStorage,
    MediaProcessError,
    MediaProcessor,
    OcrProvider,
    OcrProviderError,
    TranscriptWorkflowRepository,
)
from auto_video_sub_domain import (
    ConflictError,
    OcrObservation,
    SubtitleRegion,
    TranscriptStatus,
    ValidationError,
    consolidate_observations,
    normalize_ocr_text,
)
from temporalio import activity
from temporalio.exceptions import ApplicationError


async def _await_with_heartbeat[T](operation: Awaitable[T], detail: str) -> T:
    task = asyncio.ensure_future(operation)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=30)
            if task in done:
                return await task
            activity.heartbeat(detail)
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def _region(payload: dict[str, str]) -> SubtitleRegion:
    region = SubtitleRegion(
        x_start_ratio=float(payload["x_start_ratio"]),
        x_end_ratio=float(payload["x_end_ratio"]),
        y_start_ratio=float(payload["y_start_ratio"]),
        y_end_ratio=float(payload["y_end_ratio"]),
        sample_interval_ms=int(payload["sample_interval_ms"]),
    )
    region.validate()
    return region


def _fingerprint(parts: dict[str, object]) -> str:
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class SourceTranscriptActivities:
    def __init__(
        self,
        *,
        repository: TranscriptWorkflowRepository,
        storage: MediaArtifactStorage,
        processor: MediaProcessor,
        ocr: OcrProvider,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._processor = processor
        self._ocr = ocr

    @activity.defn(name="extract-and-ocr-source-subtitles-v1")
    async def extract_and_ocr(self, payload: dict[str, str]) -> dict[str, int]:
        project_id = UUID(payload["project_id"])
        media_asset_id = UUID(payload["media_asset_id"])
        region = _region(payload)
        state = await self._repository.get_record_internal(media_asset_id)
        if state.status in {TranscriptStatus.WAITING_FOR_REVIEW, TranscriptStatus.APPROVED}:
            existing_observations = await self._repository.load_ocr_observations(media_asset_id)
            return {"observation_count": len(existing_observations)}
        if state.status is not TranscriptStatus.PROCESSING:
            raise ApplicationError(
                "Transcript processing is no longer active",
                type="TRANSCRIPT_NOT_PROCESSING",
                non_retryable=True,
            )
        media = await self._repository.get_media_asset_internal(media_asset_id)
        if media.probe is None:
            raise ApplicationError(
                "Media probe is missing",
                type="MEDIA_PROBE_MISSING",
                non_retryable=True,
            )
        original = await self._repository.get_artifact_internal(media.original_artifact_id)
        if original is None:
            raise ApplicationError(
                "Original media artifact is missing",
                type="MEDIA_ORIGINAL_MISSING",
                non_retryable=True,
            )
        info = activity.info()
        stage_id = await self._repository.begin_stage(
            project_id=project_id,
            media_asset_id=media_asset_id,
            workflow_id=info.workflow_id or "unknown-workflow",
            stage_name="source_ocr",
            attempt=info.attempt,
            input_fingerprint=_fingerprint(
                {
                    "original_checksum": original.checksum_sha256,
                    "region": payload,
                    "pipeline": "ffmpeg-crop+rapidocr-v1",
                }
            ),
            worker_id=socket.gethostname(),
        )
        try:
            with tempfile.TemporaryDirectory(prefix="auto-video-sub-ocr-") as directory:
                root = Path(directory)
                source = root / "source"
                frames_dir = root / "frames"
                activity.heartbeat("downloading-original")
                await _await_with_heartbeat(
                    self._storage.download_file(original.object_key, source),
                    "downloading-original",
                )
                activity.heartbeat("extracting-frames")
                frames = await _await_with_heartbeat(
                    self._processor.extract_subtitle_frames(source, frames_dir, region),
                    "extracting-frames",
                )
                observations: list[OcrObservation] = []
                total = len(frames)
                for index, frame in enumerate(frames, start=1):
                    activity.heartbeat(f"ocr:{index}/{total}")
                    result = await self._ocr.recognize(frame.path)
                    text = normalize_ocr_text(result.text)
                    if text:
                        observations.append(
                            OcrObservation(
                                time_us=frame.time_us,
                                text=text,
                                confidence=result.confidence,
                                provider=result.provider,
                                model_version=result.model_version,
                            )
                        )
                await self._repository.replace_ocr_observations(
                    media_asset_id=media_asset_id,
                    observations=observations,
                )
            await self._repository.finish_stage(stage_id, status="succeeded")
            return {"observation_count": len(observations)}
        except (ValidationError, ConflictError) as error:
            await self._repository.finish_stage(
                stage_id,
                status="failed",
                error_code=error.code,
                retryable=False,
            )
            raise ApplicationError(error.message, type=error.code, non_retryable=True) from error
        except (MediaProcessError, OcrProviderError) as error:
            await self._repository.finish_stage(
                stage_id,
                status="failed",
                error_code=error.code,
                retryable=error.retryable,
            )
            raise ApplicationError(
                str(error),
                type=error.code,
                non_retryable=not error.retryable,
            ) from error
        except Exception:
            await self._repository.finish_stage(
                stage_id,
                status="failed",
                error_code="OCR_TRANSIENT",
                retryable=True,
            )
            raise

    @activity.defn(name="consolidate-source-transcript-v1")
    async def consolidate(self, payload: dict[str, str]) -> dict[str, int]:
        project_id = UUID(payload["project_id"])
        media_asset_id = UUID(payload["media_asset_id"])
        state = await self._repository.get_record_internal(media_asset_id)
        if state.status in {TranscriptStatus.WAITING_FOR_REVIEW, TranscriptStatus.APPROVED}:
            return {"segment_count": 0}
        if state.status is not TranscriptStatus.PROCESSING:
            raise ApplicationError(
                "Transcript processing is no longer active",
                type="TRANSCRIPT_NOT_PROCESSING",
                non_retryable=True,
            )
        media = await self._repository.get_media_asset_internal(media_asset_id)
        if media.probe is None:
            raise ApplicationError(
                "Media probe is missing",
                type="MEDIA_PROBE_MISSING",
                non_retryable=True,
            )
        observations = await self._repository.load_ocr_observations(media_asset_id)
        digest = hashlib.sha256()
        for item in observations:
            digest.update(
                f"{item.time_us}\0{item.text}\0{item.confidence:.6f}\0{item.model_version}\n".encode()
            )
        info = activity.info()
        stage_id = await self._repository.begin_stage(
            project_id=project_id,
            media_asset_id=media_asset_id,
            workflow_id=info.workflow_id or "unknown-workflow",
            stage_name="source_consolidation",
            attempt=info.attempt,
            input_fingerprint=_fingerprint(
                {
                    "observations_sha256": digest.hexdigest(),
                    "sample_interval_ms": state.region.sample_interval_ms,
                    "consolidation": "exact-text-gap-v1",
                }
            ),
            worker_id=socket.gethostname(),
        )
        try:
            activity.heartbeat("consolidating")
            segments = consolidate_observations(
                observations,
                sample_interval_us=state.region.sample_interval_ms * 1000,
                media_duration_us=media.probe.duration_us,
            )
            published = await self._repository.publish_ocr_segments(
                media_asset_id=media_asset_id,
                segments=segments,
            )
            await self._repository.finish_stage(stage_id, status="succeeded")
            return {"segment_count": len(published)}
        except (ValidationError, ConflictError) as error:
            await self._repository.finish_stage(
                stage_id,
                status="failed",
                error_code=error.code,
                retryable=False,
            )
            raise ApplicationError(error.message, type=error.code, non_retryable=True) from error
        except Exception:
            await self._repository.finish_stage(
                stage_id,
                status="failed",
                error_code="TRANSCRIPT_CONSOLIDATION_TRANSIENT",
                retryable=True,
            )
            raise

    @activity.defn(name="mark-source-transcript-failed-v1")
    async def mark_failed(self, payload: dict[str, str]) -> None:
        await self._repository.set_transcript_status(
            UUID(payload["media_asset_id"]),
            TranscriptStatus.FAILED,
            error_code=payload.get("error_code", "TRANSCRIPT_PROCESSING_EXHAUSTED"),
        )
