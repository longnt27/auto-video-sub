from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from auto_video_sub_domain.errors import ValidationError
from auto_video_sub_domain.rendering import OriginalAudioPolicy, RenderStatus

from auto_video_sub_application.ports import ObjectStorage
from auto_video_sub_application.render_ports import (
    RenderRepository,
    RenderSnapshot,
    RenderWorkflowControl,
)


class RenderService:
    def __init__(
        self,
        *,
        repository: RenderRepository,
        workflows: RenderWorkflowControl,
        storage: ObjectStorage,
        renderer_version: str,
        reduced_original_gain_ppm: int,
        download_url_ttl: timedelta,
        font_filename: str | None = None,
        font_checksum_sha256: str | None = None,
    ) -> None:
        # Kept temporarily for composition compatibility with older Settings wiring.
        # System-font rendering no longer uses or validates either value.
        del font_filename, font_checksum_sha256
        self._repository = repository
        self._workflows = workflows
        self._storage = storage
        self._renderer_version = renderer_version.strip()
        self._reduced_original_gain_ppm = reduced_original_gain_ppm
        self._download_url_ttl = download_url_ttl

    def _gain(self, policy: OriginalAudioPolicy) -> int:
        if policy is OriginalAudioPolicy.RETAIN:
            return 1_000_000
        if policy is OriginalAudioPolicy.REMOVE:
            return 0
        if not 0 < self._reduced_original_gain_ppm < 1_000_000:
            raise ValidationError(
                "Reduced original-audio gain is not configured safely",
                code="RENDER_AUDIO_INVALID",
            )
        return self._reduced_original_gain_ppm

    def _validate_runtime(self) -> None:
        if not self._renderer_version or len(self._renderer_version) > 160:
            raise ValidationError(
                "Renderer version is not configured", code="RENDER_CONFIG_MISSING"
            )

    async def start(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        audio_policy: OriginalAudioPolicy,
    ) -> RenderSnapshot:
        self._validate_runtime()
        record = await self._repository.prepare(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
            audio_policy=audio_policy,
            original_audio_gain_ppm=self._gain(audio_policy),
            renderer_version=self._renderer_version,
        )
        if record.status is RenderStatus.SUCCEEDED:
            return await self.get(
                owner_id=owner_id,
                project_id=project_id,
                media_asset_id=media_asset_id,
            )
        if record.workflow_id is None:
            workflow_id = await self._workflows.start_render(
                render_id=record.id,
                render_version=record.version,
            )
            await self._repository.bind_workflow(
                owner_id=owner_id,
                project_id=project_id,
                render_id=record.id,
                workflow_id=workflow_id,
            )
        return await self.get(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )

    async def get(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> RenderSnapshot:
        snapshot = await self._repository.snapshot(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )
        if (
            snapshot.record.status is not RenderStatus.SUCCEEDED
            or snapshot.output_object_key is None
        ):
            return snapshot
        expires_at = datetime.now(UTC) + self._download_url_ttl
        return RenderSnapshot(
            record=snapshot.record,
            output_object_key=snapshot.output_object_key,
            output_url=self._storage.sign_download(
                object_key=snapshot.output_object_key,
                expires_at=expires_at,
            ),
            validation=snapshot.validation,
        )

    async def cancel(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> RenderSnapshot:
        snapshot = await self._repository.snapshot(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )
        if snapshot.record.workflow_id is not None and snapshot.record.status in {
            RenderStatus.PROCESSING,
            RenderStatus.VALIDATING,
        }:
            await self._workflows.cancel_render(workflow_id=snapshot.record.workflow_id)
        await self._repository.mark_cancelled(
            owner_id=owner_id,
            project_id=project_id,
            render_id=snapshot.record.id,
        )
        return await self.get(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )
