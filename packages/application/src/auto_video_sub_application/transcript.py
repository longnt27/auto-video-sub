from __future__ import annotations

from uuid import UUID

from auto_video_sub_domain import ConflictError, SubtitleRegion, SubtitleSegment, ValidationError

from auto_video_sub_application.ports import (
    TranscriptRepository,
    TranscriptSnapshot,
    TranscriptWorkflowControl,
)


class TranscriptService:
    def __init__(
        self,
        *,
        repository: TranscriptRepository,
        workflows: TranscriptWorkflowControl,
    ) -> None:
        self._repository = repository
        self._workflows = workflows

    async def start(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        region: SubtitleRegion,
    ) -> TranscriptSnapshot:
        region.validate()
        await self._repository.prepare(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
            region=region,
        )
        workflow_id = await self._workflows.start_source_transcript(
            project_id=project_id,
            media_asset_id=media_asset_id,
            region=region,
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
    ) -> TranscriptSnapshot:
        return await self._repository.snapshot(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )

    async def edit_segment(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        segment_id: UUID,
        text: str,
        expected_version: int,
    ) -> SubtitleSegment:
        cleaned = text.strip()
        if not cleaned:
            raise ValidationError("Source subtitle text cannot be empty", code="TRANSCRIPT_TEXT_EMPTY")
        if len(cleaned) > 4000:
            raise ValidationError("Source subtitle text is too long", code="TRANSCRIPT_TEXT_TOO_LONG")
        if expected_version < 1:
            raise ValidationError("Expected segment version is invalid", code="VERSION_INVALID")
        return await self._repository.edit_segment(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
            segment_id=segment_id,
            text=cleaned,
            expected_version=expected_version,
        )

    async def approve(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
    ) -> TranscriptSnapshot:
        if expected_version < 1:
            raise ValidationError("Expected transcript version is invalid", code="VERSION_INVALID")
        record = await self._repository.approve(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
            expected_version=expected_version,
        )
        try:
            await self._workflows.approve_source_transcript(media_asset_id=media_asset_id)
        except Exception as error:
            raise ConflictError("Transcript was approved but workflow acknowledgement failed") from error
        return TranscriptSnapshot(
            record=record,
            segments=(
                await self._repository.snapshot(
                    owner_id=owner_id,
                    project_id=project_id,
                    media_asset_id=media_asset_id,
                )
            ).segments,
        )

    async def cancel(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> TranscriptSnapshot:
        await self._workflows.cancel_source_transcript(media_asset_id=media_asset_id)
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
