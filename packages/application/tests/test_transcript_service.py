from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from auto_video_sub_application import TranscriptService
from auto_video_sub_application.ports import TranscriptRecord, TranscriptSnapshot
from auto_video_sub_domain import (
    ConflictError,
    SourceRevision,
    SourceRevisionOrigin,
    SubtitleRegion,
    SubtitleSegment,
    TranscriptStatus,
    new_uuid7,
)


class FakeTranscriptRepository:
    def __init__(self, status: TranscriptStatus = TranscriptStatus.FAILED) -> None:
        now = datetime.now(UTC)
        self.record = TranscriptRecord(
            project_id=new_uuid7(),
            media_asset_id=new_uuid7(),
            status=status,
            region=SubtitleRegion(),
            workflow_id=None,
            error_code="OCR_INFERENCE_FAILED" if status is TranscriptStatus.FAILED else None,
            version=3,
            created_at=now,
            updated_at=now,
        )
        revision = SourceRevision(
            id=new_uuid7(),
            subtitle_segment_id=new_uuid7(),
            version=1,
            text="你好",
            origin=SourceRevisionOrigin.OCR,
            confidence=0.9,
            editor_id=None,
            parent_revision_id=None,
            created_at=now,
        )
        self.segment = SubtitleSegment(
            id=revision.subtitle_segment_id,
            project_id=self.record.project_id,
            media_asset_id=self.record.media_asset_id,
            ordinal=0,
            start_us=0,
            end_us=400_000,
            current_revision=revision,
            version=1,
            created_at=now,
            updated_at=now,
        )

    async def prepare(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        region: SubtitleRegion,
    ) -> TranscriptRecord:
        del owner_id
        assert project_id == self.record.project_id
        assert media_asset_id == self.record.media_asset_id
        if self.record.status in {TranscriptStatus.FAILED, TranscriptStatus.CANCELLED}:
            self.record = replace(
                self.record,
                status=TranscriptStatus.PROCESSING,
                region=region,
                workflow_id=None,
                error_code=None,
                version=self.record.version + 1,
            )
        return self.record

    async def bind_workflow(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        workflow_id: str,
    ) -> TranscriptRecord:
        del owner_id, project_id, media_asset_id
        self.record = replace(self.record, workflow_id=workflow_id)
        return self.record

    async def snapshot(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> TranscriptSnapshot:
        del owner_id
        assert project_id == self.record.project_id
        assert media_asset_id == self.record.media_asset_id
        return TranscriptSnapshot(record=self.record, segments=(self.segment,))

    async def edit_segment(self, **kwargs: object) -> SubtitleSegment:
        raise AssertionError(f"unexpected edit {kwargs}")

    async def approve(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
    ) -> TranscriptRecord:
        del owner_id, project_id, media_asset_id
        assert expected_version == self.record.version
        if self.record.status is not TranscriptStatus.WAITING_FOR_REVIEW:
            raise ConflictError("not waiting")
        self.record = replace(
            self.record,
            status=TranscriptStatus.APPROVED,
            version=self.record.version + 1,
        )
        return self.record

    async def mark_cancelled(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> TranscriptRecord:
        del owner_id, project_id, media_asset_id
        self.record = replace(
            self.record,
            status=TranscriptStatus.CANCELLED,
            version=self.record.version + 1,
        )
        return self.record


class FakeTranscriptWorkflows:
    def __init__(self) -> None:
        self.starts = 0
        self.approvals = 0
        self.cancellations = 0

    async def start_source_transcript(
        self, *, project_id: UUID, media_asset_id: UUID, region: SubtitleRegion
    ) -> str:
        del project_id, region
        self.starts += 1
        return f"source-transcript-v1/{media_asset_id}"

    async def approve_source_transcript(self, *, media_asset_id: UUID) -> None:
        del media_asset_id
        self.approvals += 1

    async def cancel_source_transcript(self, *, media_asset_id: UUID) -> None:
        del media_asset_id
        self.cancellations += 1


@pytest.mark.asyncio
async def test_restart_reuses_region_and_restarts_failed_transcript() -> None:
    repository = FakeTranscriptRepository(TranscriptStatus.FAILED)
    workflows = FakeTranscriptWorkflows()
    service = TranscriptService(repository=repository, workflows=workflows)
    owner_id = new_uuid7()

    snapshot = await service.restart(
        owner_id=owner_id,
        project_id=repository.record.project_id,
        media_asset_id=repository.record.media_asset_id,
    )

    assert snapshot.record.status is TranscriptStatus.PROCESSING
    assert snapshot.record.region == SubtitleRegion()
    assert snapshot.record.error_code is None
    assert workflows.starts == 1


@pytest.mark.asyncio
async def test_restart_rejects_reviewable_transcript() -> None:
    repository = FakeTranscriptRepository(TranscriptStatus.WAITING_FOR_REVIEW)
    service = TranscriptService(repository=repository, workflows=FakeTranscriptWorkflows())

    with pytest.raises(ConflictError):
        await service.restart(
            owner_id=new_uuid7(),
            project_id=repository.record.project_id,
            media_asset_id=repository.record.media_asset_id,
        )


@pytest.mark.asyncio
async def test_approval_signals_workflow_and_is_retryable_after_db_commit() -> None:
    repository = FakeTranscriptRepository(TranscriptStatus.WAITING_FOR_REVIEW)
    workflows = FakeTranscriptWorkflows()
    service = TranscriptService(repository=repository, workflows=workflows)
    owner_id = new_uuid7()

    approved = await service.approve(
        owner_id=owner_id,
        project_id=repository.record.project_id,
        media_asset_id=repository.record.media_asset_id,
        expected_version=repository.record.version,
    )
    repeated = await service.approve(
        owner_id=owner_id,
        project_id=repository.record.project_id,
        media_asset_id=repository.record.media_asset_id,
        expected_version=approved.record.version,
    )

    assert approved.record.status is TranscriptStatus.APPROVED
    assert repeated.record.status is TranscriptStatus.APPROVED
    assert workflows.approvals == 2


@pytest.mark.asyncio
async def test_cancel_is_idempotent_and_approved_transcript_is_protected() -> None:
    repository = FakeTranscriptRepository(TranscriptStatus.PROCESSING)
    workflows = FakeTranscriptWorkflows()
    service = TranscriptService(repository=repository, workflows=workflows)
    owner_id = new_uuid7()

    first = await service.cancel(
        owner_id=owner_id,
        project_id=repository.record.project_id,
        media_asset_id=repository.record.media_asset_id,
    )
    second = await service.cancel(
        owner_id=owner_id,
        project_id=repository.record.project_id,
        media_asset_id=repository.record.media_asset_id,
    )

    assert first.record.status is TranscriptStatus.CANCELLED
    assert second.record.status is TranscriptStatus.CANCELLED
    assert workflows.cancellations == 1
