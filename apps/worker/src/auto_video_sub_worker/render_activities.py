from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from auto_video_sub_application.render_ports import (
    FrozenRenderInput,
    PublishedRenderArtifact,
    RenderObjectStorage,
    RenderProcessor,
    RenderWorkflowRepository,
)
from auto_video_sub_domain.rendering import RenderStatus
from auto_video_sub_providers.render import RenderProcessError
from temporalio import activity
from temporalio.exceptions import ApplicationError


class RenderActivities:
    def __init__(
        self,
        *,
        repository: RenderWorkflowRepository,
        storage: RenderObjectStorage,
        processor: RenderProcessor,
        font_path: Path,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._processor = processor
        self._font_path = font_path

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _manifest(render_input: FrozenRenderInput) -> dict[str, object]:
        return {
            "schema_version": "render-manifest-v1",
            "render_id": str(render_input.render_id),
            "project_id": str(render_input.project_id),
            "media_asset_id": str(render_input.media_asset_id),
            "input_fingerprint": render_input.input_fingerprint,
            "original": {
                "artifact_id": str(render_input.original_artifact_id),
                "object_key": render_input.original_object_key,
                "checksum_sha256": render_input.original_checksum_sha256,
                "duration_us": render_input.duration_us,
                "width": render_input.width,
                "height": render_input.height,
                "source_has_audio": render_input.source_has_audio,
            },
            "transcript_version": render_input.transcript_version,
            "translation_policy_version_id": str(
                render_input.translation_policy_version_id
            ),
            "subtitle_style_version_id": str(render_input.subtitle_style_version_id),
            "subtitle_style": {
                "font_id": render_input.subtitle_style.font_id,
                "font_family": render_input.subtitle_style.font_family,
                "font_license": render_input.subtitle_style.font_license,
                "font_size_pct": render_input.subtitle_style.font_size_pct,
                "text_color": render_input.subtitle_style.text_color,
                "outline_color": render_input.subtitle_style.outline_color,
                "background_color": render_input.subtitle_style.background_color,
                "background_opacity_pct": (
                    render_input.subtitle_style.background_opacity_pct
                ),
                "outline_px": render_input.subtitle_style.outline_px,
                "shadow_px": render_input.subtitle_style.shadow_px,
                "alignment": render_input.subtitle_style.alignment.value,
            },
            "speech_tracks": [
                {
                    "segment_id": str(track.segment_id),
                    "ordinal": track.ordinal,
                    "start_us": track.start_us,
                    "end_us": track.end_us,
                    "text": track.text,
                    "translation_revision_id": str(track.translation_revision_id),
                    "speech_attempt_id": str(track.speech_attempt_id),
                    "audio_artifact_id": str(track.audio_artifact_id),
                    "audio_object_key": track.audio_object_key,
                    "audio_checksum_sha256": track.audio_checksum_sha256,
                }
                for track in render_input.speech_tracks
            ],
            "audio_policy": render_input.audio_policy.value,
            "original_audio_gain_ppm": render_input.original_audio_gain_ppm,
            "renderer_version": render_input.renderer_version,
            "font": {
                "filename": render_input.font_filename,
                "checksum_sha256": render_input.font_checksum_sha256,
            },
        }

    async def _publish(
        self,
        *,
        render_input: FrozenRenderInput,
        source: Path,
        role: str,
        media_type: str,
    ) -> PublishedRenderArtifact:
        checksum = self._sha256(source)
        artifact_id = uuid5(
            NAMESPACE_URL,
            f"auto-video-sub:render:{render_input.render_id}:{role}:{checksum}",
        )
        suffix = source.suffix or ".bin"
        object_key = f"artifacts/{render_input.project_id}/{artifact_id}/{role}{suffix}"
        metadata = await self._storage.upload_file(source, object_key, media_type)
        return PublishedRenderArtifact(
            id=artifact_id,
            object_key=object_key,
            media_type=media_type,
            byte_size=metadata.byte_size,
            checksum_sha256=checksum,
        )

    @activity.defn(name="freeze-render-manifest-v1")
    async def freeze_manifest(self, payload: dict[str, str]) -> str:
        render_input = await self._repository.get_input_internal(UUID(payload["render_id"]))
        with tempfile.TemporaryDirectory(prefix="auto-video-sub-render-manifest-") as root:
            path = Path(root) / "manifest.json"
            path.write_text(
                json.dumps(
                    self._manifest(render_input),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            artifact = await self._publish(
                render_input=render_input,
                source=path,
                role="manifest",
                media_type="application/json",
            )
            await self._repository.register_artifact(
                render_id=render_input.render_id,
                role="manifest",
                artifact=artifact,
            )
            return artifact.object_key

    @activity.defn(name="render-video-v1")
    async def render_video(self, payload: dict[str, str]) -> str:
        render_input = await self._repository.get_input_internal(UUID(payload["render_id"]))
        try:
            with tempfile.TemporaryDirectory(prefix="auto-video-sub-render-") as root_value:
                root = Path(root_value)
                original_path = root / "original"
                ass_path = root / "subtitles.ass"
                output_path = root / "localized.mp4"
                fonts_dir = root / "fonts"
                fonts_dir.mkdir()
                local_font_path = fonts_dir / render_input.font_filename

                activity.heartbeat({"stage": "download_original"})
                await self._storage.download_file(
                    render_input.original_object_key,
                    original_path,
                )
                if self._sha256(original_path) != render_input.original_checksum_sha256:
                    raise ApplicationError(
                        "Original artifact checksum no longer matches the frozen manifest",
                        type="RENDER_INPUT_CHECKSUM_MISMATCH",
                        non_retryable=True,
                    )

                if (
                    not self._font_path.is_file()
                    or self._font_path.name != render_input.font_filename
                    or self._sha256(self._font_path) != render_input.font_checksum_sha256
                ):
                    raise ApplicationError(
                        "Pinned subtitle font is missing or has the wrong checksum",
                        type="RENDER_FONT_INVALID",
                        non_retryable=True,
                    )
                shutil.copyfile(self._font_path, local_font_path)

                speech_paths: dict[UUID, Path] = {}
                for track in render_input.speech_tracks:
                    activity.heartbeat(
                        {"stage": "download_speech", "segment_id": str(track.segment_id)}
                    )
                    path = root / f"speech-{track.ordinal:06d}.wav"
                    await self._storage.download_file(track.audio_object_key, path)
                    if self._sha256(path) != track.audio_checksum_sha256:
                        raise ApplicationError(
                            "Speech artifact checksum no longer matches the frozen manifest",
                            type="RENDER_INPUT_CHECKSUM_MISMATCH",
                            non_retryable=True,
                        )
                    speech_paths[track.audio_artifact_id] = path

                self._processor.write_ass(render_input, ass_path)
                subtitle_artifact = await self._publish(
                    render_input=render_input,
                    source=ass_path,
                    role="subtitle",
                    media_type="text/x-ssa",
                )
                await self._repository.register_artifact(
                    render_id=render_input.render_id,
                    role="subtitle",
                    artifact=subtitle_artifact,
                )

                activity.heartbeat({"stage": "ffmpeg_render"})
                await self._processor.render(
                    render_input=render_input,
                    original_path=original_path,
                    speech_paths=speech_paths,
                    ass_path=ass_path,
                    font_path=local_font_path,
                    output_path=output_path,
                )
                output_artifact = await self._publish(
                    render_input=render_input,
                    source=output_path,
                    role="output",
                    media_type="video/mp4",
                )
                await self._repository.register_artifact(
                    render_id=render_input.render_id,
                    role="output",
                    artifact=output_artifact,
                )
                return output_artifact.object_key
        except RenderProcessError as error:
            raise ApplicationError(
                str(error),
                type=error.code,
                non_retryable=not error.retryable,
            ) from error

    @activity.defn(name="validate-render-output-v1")
    async def validate_output(self, payload: dict[str, str]) -> str:
        render_input = await self._repository.get_input_internal(UUID(payload["render_id"]))
        output_object_key = payload["output_object_key"]
        try:
            with tempfile.TemporaryDirectory(prefix="auto-video-sub-render-validation-") as root:
                output_path = Path(root) / "localized.mp4"
                report_path = Path(root) / "validation.json"
                await self._storage.download_file(output_object_key, output_path)
                result = await self._processor.validate(
                    output_path=output_path,
                    expected_duration_us=render_input.duration_us,
                    expected_width=render_input.width,
                    expected_height=render_input.height,
                )
                report = asdict(result)
                report["schema_version"] = "render-validation-v1"
                report["render_id"] = str(render_input.render_id)
                report["input_fingerprint"] = render_input.input_fingerprint
                report_path.write_text(
                    json.dumps(
                        report,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n",
                    encoding="utf-8",
                )
                artifact = await self._publish(
                    render_input=render_input,
                    source=report_path,
                    role="validation",
                    media_type="application/json",
                )
                await self._repository.register_artifact(
                    render_id=render_input.render_id,
                    role="validation",
                    artifact=artifact,
                    validation=report,
                )
                if not result.valid:
                    raise ApplicationError(
                        "Rendered output failed validation",
                        type="RENDER_VALIDATION_FAILED",
                        non_retryable=True,
                    )
                return artifact.object_key
        except RenderProcessError as error:
            raise ApplicationError(
                str(error),
                type=error.code,
                non_retryable=not error.retryable,
            ) from error

    @activity.defn(name="mark-render-failed-v1")
    async def mark_failed(self, payload: dict[str, str]) -> None:
        await self._repository.set_status(
            UUID(payload["render_id"]),
            RenderStatus.FAILED,
            error_code=payload.get("error_code", "RENDER_PROCESSING_EXHAUSTED"),
        )
