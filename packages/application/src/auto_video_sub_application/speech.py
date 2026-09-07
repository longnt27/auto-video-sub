from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from auto_video_sub_domain import ConflictError, DurationFitPolicy, SpeechStatus, ValidationError

from auto_video_sub_application.ports import ObjectStorage
from auto_video_sub_application.speech_ports import (
    SpeechRepository,
    SpeechSnapshot,
    SpeechWorkflowControl,
)


class SpeechService:
    def __init__(
        self,
        *,
        repository: SpeechRepository,
        workflows: SpeechWorkflowControl,
        storage: ObjectStorage,
        provider: str,
        model: str,
        model_revision: str,
        voice_id: str,
        policy: DurationFitPolicy,
        download_url_ttl: timedelta,
    ) -> None:
        self._repository = repository
        self._workflows = workflows
        self._storage = storage
        self._provider = provider.strip()
        self._model = model.strip()
        self._model_revision = model_revision.strip()
        self._voice_id = voice_id.strip()
        self._policy = policy
        self._download_url_ttl = download_url_ttl

    async def start(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> SpeechSnapshot:
        self._validate_configuration()
        record = await self._repository.prepare(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
            provider=self._provider,
            model=self._model,
            model_revision=self._model_revision,
            voice_id=self._voice_id,
            policy=self._policy,
        )
        if record.status is SpeechStatus.PROCESSING and record.workflow_id is None:
            workflow_id = await self._workflows.start_speech(
                project_id=project_id,
                media_asset_id=media_asset_id,
                speech_version=record.version,
            )
            await self._repository.bind_workflow(
                owner_id=owner_id,
                project_id=project_id,
                media_asset_id=media_asset_id,
                workflow_id=workflow_id,
            )
        return await self.get(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )

    async def get(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> SpeechSnapshot:
        snapshot = await self._repository.snapshot(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )
        expires_at = datetime.now(UTC) + self._download_url_ttl
        segments = []
        for segment in snapshot.segments:
            audio_url = None
            if segment.audio_object_key is not None:
                audio_url = self._storage.sign_download(
                    object_key=segment.audio_object_key,
                    expires_at=expires_at,
                )
            segments.append(replace(segment, audio_url=audio_url))
        return replace(snapshot, segments=tuple(segments))

    async def retry_segment(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        segment_id: UUID,
        text: str | None,
    ) -> SpeechSnapshot:
        snapshot = await self.get(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )
        if snapshot.record.status is not SpeechStatus.WAITING_FOR_REVIEW:
            raise ConflictError("Speech is not waiting for segment review")
        if snapshot.record.workflow_id is None:
            raise ConflictError("Speech workflow is not available for retry")
        segment = next((item for item in snapshot.segments if item.input.id == segment_id), None)
        if segment is None:
            raise ConflictError("Speech segment does not belong to this media asset")
        cleaned = text.strip() if text is not None else None
        if cleaned is not None and (not cleaned or len(cleaned) > 4000):
            raise ValidationError("Speech repair text is invalid", code="TTS_TEXT_INVALID")
        await self._workflows.retry_speech_segment(
            workflow_id=snapshot.record.workflow_id,
            segment_id=segment_id,
            text=cleaned,
        )
        return snapshot

    async def approve(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
    ) -> SpeechSnapshot:
        if expected_version < 1:
            raise ValidationError("Expected speech version is invalid", code="VERSION_INVALID")
        snapshot = await self.get(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )
        if snapshot.record.status is SpeechStatus.APPROVED:
            return snapshot
        if snapshot.record.status is not SpeechStatus.WAITING_FOR_REVIEW:
            raise ConflictError("Speech is not ready for approval")
        if snapshot.record.workflow_id is None:
            raise ConflictError("Speech workflow is not available for approval")
        if any(segment.status.value != "fit" for segment in snapshot.segments):
            raise ConflictError("Every speech segment must fit before approval")
        await self._repository.approve(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
            expected_version=expected_version,
        )
        await self._workflows.approve_speech(workflow_id=snapshot.record.workflow_id)
        return await self.get(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )

    async def cancel(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> SpeechSnapshot:
        snapshot = await self.get(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )
        if snapshot.record.status is SpeechStatus.CANCELLED:
            return snapshot
        if snapshot.record.status is SpeechStatus.APPROVED:
            raise ConflictError("Approved speech cannot be cancelled")
        if snapshot.record.workflow_id is not None:
            await self._workflows.cancel_speech(workflow_id=snapshot.record.workflow_id)
        await self._repository.mark_cancelled(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )
        return await self.get(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )

    def _validate_configuration(self) -> None:
        self._policy.validate()
        if not self._provider or not self._model or not self._model_revision:
            raise ValidationError(
                "TTS provider is not configured", code="TTS_PROVIDER_UNCONFIGURED"
            )
        if not self._voice_id:
            raise ValidationError("TTS voice is not configured", code="TTS_VOICE_UNCONFIGURED")
