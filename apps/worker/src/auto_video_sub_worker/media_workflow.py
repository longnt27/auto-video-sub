from __future__ import annotations

import asyncio
import hashlib
import logging
import socket
import tempfile
from collections.abc import Awaitable
from pathlib import Path
from uuid import UUID

from auto_video_sub_application.ports import (
    MediaArtifactStorage,
    MediaProcessError,
    MediaProcessor,
    MediaWorkflowRepository,
)
from auto_video_sub_domain import (
    MediaLimits,
    MediaStatus,
    QuotaExceededError,
    ValidationError,
    validate_probe,
)
from temporalio import activity
from temporalio.exceptions import ApplicationError

LOGGER = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


class MediaActivities:
    def __init__(
        self,
        *,
        repository: MediaWorkflowRepository,
        storage: MediaArtifactStorage,
        processor: MediaProcessor,
        limits: MediaLimits,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._processor = processor
        self._limits = limits

    async def _delete_best_effort(self, object_key: str, media_asset_id: UUID) -> None:
        try:
            await self._storage.delete_object(object_key)
        except Exception:
            LOGGER.warning(
                "media_object_cleanup_failed",
                extra={
                    "media_asset_id": str(media_asset_id),
                    "code": "STORAGE_CLEANUP_FAILED",
                },
            )

    @activity.defn(name="validate-original-media-v1")
    async def validate_original(self, payload: dict[str, str]) -> dict[str, str]:
        project_id = UUID(payload["project_id"])
        media_asset_id = UUID(payload["media_asset_id"])
        media = await self._repository.get_media_asset_internal(media_asset_id)
        existing = await self._repository.get_artifact_internal(media.original_artifact_id)
        if existing is not None:
            return {"original_artifact_id": str(existing.id)}
        upload = await self._repository.get_upload_for_media_internal(media_asset_id)
        info = activity.info()
        input_fingerprint = hashlib.sha256(
            f"{upload.original_artifact_id}:{upload.sealed_object_key}:media-validation-v1".encode()
        ).hexdigest()
        stage_id = await self._repository.begin_stage(
            project_id=project_id,
            media_asset_id=media_asset_id,
            workflow_id=info.workflow_id or "unknown-workflow",
            stage_name="media_validation",
            attempt=info.attempt,
            input_fingerprint=input_fingerprint,
            worker_id=socket.gethostname(),
        )
        await self._repository.set_media_status(media_asset_id, MediaStatus.VALIDATING)
        try:
            with tempfile.TemporaryDirectory(prefix="auto-video-sub-validate-") as directory:
                source = Path(directory) / "source"
                activity.heartbeat("downloading")
                await self._storage.download_file(upload.sealed_object_key, source)
                activity.heartbeat("probing")
                self._processor.validate_magic(source, upload.declared_content_type)
                probe = await self._processor.probe(source)
                validate_probe(probe, self._limits)
                checksum = _sha256(source)
                metadata = await self._storage.object_metadata(upload.sealed_object_key)
                artifact = await self._repository.register_original(
                    media_asset_id=media_asset_id,
                    media_type=upload.declared_content_type,
                    byte_size=metadata.byte_size,
                    checksum_sha256=checksum,
                    probe=probe,
                    stage_execution_id=stage_id,
                )
            await self._repository.finish_stage(stage_id, status="succeeded")
            return {"original_artifact_id": str(artifact.id)}
        except (ValidationError, QuotaExceededError) as error:
            await self._delete_best_effort(upload.sealed_object_key, media_asset_id)
            await self._repository.reject_upload(
                upload_intent_id=upload.id,
                error_code=error.code,
            )
            await self._repository.finish_stage(
                stage_id,
                status="failed",
                error_code=error.code,
                retryable=False,
            )
            raise ApplicationError(error.message, type=error.code, non_retryable=True) from error
        except MediaProcessError as error:
            if not error.retryable:
                await self._delete_best_effort(upload.sealed_object_key, media_asset_id)
                await self._repository.reject_upload(
                    upload_intent_id=upload.id,
                    error_code=error.code,
                )
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
                error_code="MEDIA_VALIDATION_TRANSIENT",
                retryable=True,
            )
            raise

    @activity.defn(name="generate-proxy-media-v1")
    async def generate_proxy(self, payload: dict[str, str]) -> dict[str, str]:
        project_id = UUID(payload["project_id"])
        media_asset_id = UUID(payload["media_asset_id"])
        media = await self._repository.get_media_asset_internal(media_asset_id)
        if media.status is MediaStatus.READY and media.proxy_artifact_id is not None:
            return {"proxy_artifact_id": str(media.proxy_artifact_id)}
        original = await self._repository.get_artifact_internal(media.original_artifact_id)
        if original is None:
            raise ApplicationError(
                "Validated original artifact is missing",
                type="MEDIA_ORIGINAL_MISSING",
                non_retryable=True,
            )
        proxy_artifact_id = await self._repository.ensure_proxy_artifact_id(media_asset_id)
        proxy_key = f"artifacts/{project_id}/{proxy_artifact_id}/proxy.mp4"
        info = activity.info()
        input_fingerprint = hashlib.sha256(
            f"{original.checksum_sha256}:proxy-720p-h264-v1".encode()
        ).hexdigest()
        stage_id = await self._repository.begin_stage(
            project_id=project_id,
            media_asset_id=media_asset_id,
            workflow_id=info.workflow_id or "unknown-workflow",
            stage_name="proxy_generation",
            attempt=info.attempt,
            input_fingerprint=input_fingerprint,
            worker_id=socket.gethostname(),
        )
        await self._repository.set_media_status(media_asset_id, MediaStatus.PROXY_GENERATING)
        try:
            with tempfile.TemporaryDirectory(prefix="auto-video-sub-proxy-") as directory:
                source = Path(directory) / "source"
                proxy = Path(directory) / "proxy.mp4"
                activity.heartbeat("downloading")
                await self._storage.download_file(original.object_key, source)
                activity.heartbeat("encoding")
                await _await_with_heartbeat(
                    self._processor.generate_proxy(source, proxy),
                    "encoding",
                )
                activity.heartbeat("publishing")
                checksum = _sha256(proxy)
                metadata = await self._storage.upload_file(proxy, proxy_key, "video/mp4")
                try:
                    artifact = await self._repository.register_proxy(
                        media_asset_id=media_asset_id,
                        artifact_id=proxy_artifact_id,
                        object_key=proxy_key,
                        byte_size=metadata.byte_size,
                        checksum_sha256=checksum,
                        stage_execution_id=stage_id,
                    )
                except Exception:
                    await self._delete_best_effort(proxy_key, media_asset_id)
                    raise
            await self._repository.finish_stage(stage_id, status="succeeded")
            return {"proxy_artifact_id": str(artifact.id)}
        except (ValidationError, QuotaExceededError) as error:
            await self._repository.finish_stage(
                stage_id,
                status="failed",
                error_code=error.code,
                retryable=False,
            )
            await self._repository.set_media_status(
                media_asset_id,
                MediaStatus.FAILED,
                error_code=error.code,
            )
            raise ApplicationError(error.message, type=error.code, non_retryable=True) from error
        except MediaProcessError as error:
            await self._repository.finish_stage(
                stage_id,
                status="failed",
                error_code=error.code,
                retryable=error.retryable,
            )
            if not error.retryable:
                await self._repository.set_media_status(
                    media_asset_id,
                    MediaStatus.FAILED,
                    error_code=error.code,
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
                error_code="MEDIA_PROXY_TRANSIENT",
                retryable=True,
            )
            raise

    @activity.defn(name="mark-media-ingest-failed-v1")
    async def mark_failed(self, payload: dict[str, str]) -> None:
        await self._repository.mark_media_failed(
            UUID(payload["media_asset_id"]),
            error_code=payload.get("error_code", "MEDIA_INGEST_EXHAUSTED"),
        )
