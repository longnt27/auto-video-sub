from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from auto_video_sub_application.ports import TranscriptRecord, TranscriptSnapshot
from auto_video_sub_domain import (
    Artifact,
    ConflictError,
    ConsolidatedSegment,
    MediaAsset,
    MediaStatus,
    NotFoundError,
    OcrObservation,
    SourceRevision,
    SourceRevisionOrigin,
    SubtitleRegion,
    SubtitleSegment,
    TranscriptStatus,
    new_uuid7,
)
from sqlalchemy import delete, select

from auto_video_sub_infrastructure.database import SessionProvider
from auto_video_sub_infrastructure.models import (
    MediaAssetModel,
    OcrObservationModel,
    ProjectModel,
    SourceRevisionModel,
    SubtitleSegmentModel,
    TranscriptStateModel,
)
from auto_video_sub_infrastructure.repository import SqlAlchemyProductRepository


def _region_payload(region: SubtitleRegion) -> dict[str, object]:
    return {
        "x_start_ratio": region.x_start_ratio,
        "x_end_ratio": region.x_end_ratio,
        "y_start_ratio": region.y_start_ratio,
        "y_end_ratio": region.y_end_ratio,
        "sample_interval_ms": region.sample_interval_ms,
    }


def _region(value: dict[str, object]) -> SubtitleRegion:
    return SubtitleRegion(
        x_start_ratio=float(value["x_start_ratio"]),
        x_end_ratio=float(value["x_end_ratio"]),
        y_start_ratio=float(value["y_start_ratio"]),
        y_end_ratio=float(value["y_end_ratio"]),
        sample_interval_ms=int(value["sample_interval_ms"]),
    )


def _record(row: TranscriptStateModel) -> TranscriptRecord:
    return TranscriptRecord(
        project_id=row.project_id,
        media_asset_id=row.media_asset_id,
        status=TranscriptStatus(row.status),
        region=_region(row.region_config),
        workflow_id=row.workflow_id,
        error_code=row.error_code,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _revision(row: SourceRevisionModel) -> SourceRevision:
    return SourceRevision(
        id=row.id,
        subtitle_segment_id=row.subtitle_segment_id,
        version=row.version,
        text=row.text,
        origin=SourceRevisionOrigin(row.origin),
        confidence=(row.confidence_ppm / 1_000_000 if row.confidence_ppm is not None else None),
        editor_id=row.editor_id,
        parent_revision_id=row.parent_revision_id,
        created_at=row.created_at,
    )


class SqlAlchemyTranscriptRepository:
    def __init__(
        self,
        sessions: SessionProvider,
        media_repository: SqlAlchemyProductRepository,
    ) -> None:
        self._sessions = sessions
        self._media_repository = media_repository

    async def _owned_media(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> MediaAssetModel:
        async with self._sessions.session() as session:
            row = await session.scalar(
                select(MediaAssetModel)
                .join(ProjectModel, ProjectModel.id == MediaAssetModel.project_id)
                .where(
                    MediaAssetModel.id == media_asset_id,
                    MediaAssetModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
            )
            if row is None:
                raise NotFoundError("Media asset not found")
            return row

    async def prepare(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        region: SubtitleRegion,
    ) -> TranscriptRecord:
        region.validate()
        async with self._sessions.session() as session, session.begin():
            media = await session.scalar(
                select(MediaAssetModel)
                .join(ProjectModel, ProjectModel.id == MediaAssetModel.project_id)
                .where(
                    MediaAssetModel.id == media_asset_id,
                    MediaAssetModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
                .with_for_update()
            )
            if media is None:
                raise NotFoundError("Media asset not found")
            if MediaStatus(media.status) is not MediaStatus.READY or media.probe is None:
                raise ConflictError("Media must be ready before source transcript processing")
            now = datetime.now(UTC)
            row = await session.get(TranscriptStateModel, media_asset_id, with_for_update=True)
            if row is None:
                row = TranscriptStateModel(
                    media_asset_id=media_asset_id,
                    project_id=project_id,
                    status=TranscriptStatus.PROCESSING,
                    region_config=_region_payload(region),
                    workflow_id=None,
                    error_code=None,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            elif TranscriptStatus(row.status) in {
                TranscriptStatus.FAILED,
                TranscriptStatus.CANCELLED,
            }:
                row.status = TranscriptStatus.PROCESSING
                row.region_config = _region_payload(region)
                row.workflow_id = None
                row.error_code = None
                row.version += 1
                row.updated_at = now
            return _record(row)

    async def bind_workflow(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        workflow_id: str,
    ) -> TranscriptRecord:
        async with self._sessions.session() as session, session.begin():
            row = await session.scalar(
                select(TranscriptStateModel)
                .join(ProjectModel, ProjectModel.id == TranscriptStateModel.project_id)
                .where(
                    TranscriptStateModel.media_asset_id == media_asset_id,
                    TranscriptStateModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
                .with_for_update()
            )
            if row is None:
                raise NotFoundError("Transcript state not found")
            if row.workflow_id is not None and row.workflow_id != workflow_id:
                raise ConflictError("Transcript is already bound to a different workflow")
            row.workflow_id = workflow_id
            row.updated_at = datetime.now(UTC)
            return _record(row)

    async def _segments(self, session: object, media_asset_id: UUID) -> tuple[SubtitleSegment, ...]:
        # AsyncSession is intentionally duck-typed here to keep repository helpers private.
        rows = (
            await session.scalars(  # type: ignore[attr-defined]
                select(SubtitleSegmentModel)
                .where(SubtitleSegmentModel.media_asset_id == media_asset_id)
                .order_by(SubtitleSegmentModel.ordinal)
            )
        ).all()
        result: list[SubtitleSegment] = []
        for row in rows:
            if row.current_source_revision_id is None:
                raise RuntimeError("Subtitle segment has no current source revision")
            revision_row = await session.get(  # type: ignore[attr-defined]
                SourceRevisionModel, row.current_source_revision_id
            )
            if revision_row is None:
                raise RuntimeError("Current source revision is missing")
            result.append(
                SubtitleSegment(
                    id=row.id,
                    project_id=row.project_id,
                    media_asset_id=row.media_asset_id,
                    ordinal=row.ordinal,
                    start_us=row.start_us,
                    end_us=row.end_us,
                    current_revision=_revision(revision_row),
                    version=row.version,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        return tuple(result)

    async def snapshot(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> TranscriptSnapshot:
        async with self._sessions.session() as session:
            row = await session.scalar(
                select(TranscriptStateModel)
                .join(ProjectModel, ProjectModel.id == TranscriptStateModel.project_id)
                .where(
                    TranscriptStateModel.media_asset_id == media_asset_id,
                    TranscriptStateModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
            )
            if row is None:
                raise NotFoundError("Transcript not found")
            return TranscriptSnapshot(
                record=_record(row),
                segments=await self._segments(session, media_asset_id),
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
        async with self._sessions.session() as session, session.begin():
            state = await session.scalar(
                select(TranscriptStateModel)
                .join(ProjectModel, ProjectModel.id == TranscriptStateModel.project_id)
                .where(
                    TranscriptStateModel.media_asset_id == media_asset_id,
                    TranscriptStateModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
                .with_for_update()
            )
            if state is None:
                raise NotFoundError("Transcript not found")
            if TranscriptStatus(state.status) is not TranscriptStatus.WAITING_FOR_REVIEW:
                raise ConflictError("Transcript is not editable in its current state")
            segment = await session.scalar(
                select(SubtitleSegmentModel)
                .where(
                    SubtitleSegmentModel.id == segment_id,
                    SubtitleSegmentModel.project_id == project_id,
                    SubtitleSegmentModel.media_asset_id == media_asset_id,
                )
                .with_for_update()
            )
            if segment is None:
                raise NotFoundError("Subtitle segment not found")
            if segment.version != expected_version:
                raise ConflictError("Subtitle segment was edited by another request")
            if segment.current_source_revision_id is None:
                raise RuntimeError("Subtitle segment has no current revision")
            parent = await session.get(SourceRevisionModel, segment.current_source_revision_id)
            if parent is None:
                raise RuntimeError("Current source revision is missing")
            now = datetime.now(UTC)
            revision = SourceRevisionModel(
                id=new_uuid7(),
                subtitle_segment_id=segment.id,
                version=parent.version + 1,
                text=text,
                origin=SourceRevisionOrigin.USER,
                confidence_ppm=None,
                editor_id=owner_id,
                parent_revision_id=parent.id,
                created_at=now,
            )
            session.add(revision)
            await session.flush()
            segment.current_source_revision_id = revision.id
            segment.version += 1
            segment.updated_at = now
            state.version += 1
            state.updated_at = now
            return SubtitleSegment(
                id=segment.id,
                project_id=segment.project_id,
                media_asset_id=segment.media_asset_id,
                ordinal=segment.ordinal,
                start_us=segment.start_us,
                end_us=segment.end_us,
                current_revision=_revision(revision),
                version=segment.version,
                created_at=segment.created_at,
                updated_at=segment.updated_at,
            )

    async def approve(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
    ) -> TranscriptRecord:
        async with self._sessions.session() as session, session.begin():
            row = await session.scalar(
                select(TranscriptStateModel)
                .join(ProjectModel, ProjectModel.id == TranscriptStateModel.project_id)
                .where(
                    TranscriptStateModel.media_asset_id == media_asset_id,
                    TranscriptStateModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
                .with_for_update()
            )
            if row is None:
                raise NotFoundError("Transcript not found")
            if TranscriptStatus(row.status) is not TranscriptStatus.WAITING_FOR_REVIEW:
                raise ConflictError("Transcript is not waiting for review")
            if row.version != expected_version:
                raise ConflictError("Transcript changed after it was loaded")
            row.status = TranscriptStatus.APPROVED
            row.version += 1
            row.updated_at = datetime.now(UTC)
            return _record(row)

    async def mark_cancelled(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> TranscriptRecord:
        async with self._sessions.session() as session, session.begin():
            row = await session.scalar(
                select(TranscriptStateModel)
                .join(ProjectModel, ProjectModel.id == TranscriptStateModel.project_id)
                .where(
                    TranscriptStateModel.media_asset_id == media_asset_id,
                    TranscriptStateModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
                .with_for_update()
            )
            if row is None:
                raise NotFoundError("Transcript not found")
            if TranscriptStatus(row.status) is TranscriptStatus.APPROVED:
                raise ConflictError("Approved transcript cannot be cancelled")
            if TranscriptStatus(row.status) is not TranscriptStatus.CANCELLED:
                row.status = TranscriptStatus.CANCELLED
                row.error_code = "CANCELLED"
                row.version += 1
                row.updated_at = datetime.now(UTC)
            return _record(row)

    async def get_record_internal(self, media_asset_id: UUID) -> TranscriptRecord:
        async with self._sessions.session() as session:
            row = await session.get(TranscriptStateModel, media_asset_id)
            if row is None:
                raise NotFoundError("Transcript state not found")
            return _record(row)

    async def get_media_asset_internal(self, media_asset_id: UUID) -> MediaAsset:
        return await self._media_repository.get_media_asset_internal(media_asset_id)

    async def get_artifact_internal(self, artifact_id: UUID) -> Artifact | None:
        return await self._media_repository.get_artifact_internal(artifact_id)

    async def replace_ocr_observations(
        self, *, media_asset_id: UUID, observations: list[OcrObservation]
    ) -> None:
        async with self._sessions.session() as session, session.begin():
            state = await session.get(TranscriptStateModel, media_asset_id, with_for_update=True)
            if state is None:
                raise NotFoundError("Transcript state not found")
            if TranscriptStatus(state.status) is not TranscriptStatus.PROCESSING:
                if TranscriptStatus(state.status) in {
                    TranscriptStatus.WAITING_FOR_REVIEW,
                    TranscriptStatus.APPROVED,
                }:
                    return
                raise ConflictError("Transcript processing is no longer active")
            await session.execute(
                delete(OcrObservationModel).where(OcrObservationModel.media_asset_id == media_asset_id)
            )
            now = datetime.now(UTC)
            for observation in observations:
                observation.validate()
                session.add(
                    OcrObservationModel(
                        id=new_uuid7(),
                        project_id=state.project_id,
                        media_asset_id=media_asset_id,
                        time_us=observation.time_us,
                        text=observation.text,
                        confidence_ppm=round(observation.confidence * 1_000_000),
                        provider=observation.provider,
                        model_version=observation.model_version,
                        created_at=now,
                    )
                )

    async def load_ocr_observations(self, media_asset_id: UUID) -> list[OcrObservation]:
        async with self._sessions.session() as session:
            rows = (
                await session.scalars(
                    select(OcrObservationModel)
                    .where(OcrObservationModel.media_asset_id == media_asset_id)
                    .order_by(OcrObservationModel.time_us)
                )
            ).all()
            return [
                OcrObservation(
                    time_us=row.time_us,
                    text=row.text,
                    confidence=row.confidence_ppm / 1_000_000,
                    provider=row.provider,
                    model_version=row.model_version,
                )
                for row in rows
            ]

    async def publish_ocr_segments(
        self, *, media_asset_id: UUID, segments: list[ConsolidatedSegment]
    ) -> tuple[SubtitleSegment, ...]:
        async with self._sessions.session() as session, session.begin():
            state = await session.get(TranscriptStateModel, media_asset_id, with_for_update=True)
            if state is None:
                raise NotFoundError("Transcript state not found")
            if TranscriptStatus(state.status) in {
                TranscriptStatus.WAITING_FOR_REVIEW,
                TranscriptStatus.APPROVED,
            }:
                return await self._segments(session, media_asset_id)
            if TranscriptStatus(state.status) is not TranscriptStatus.PROCESSING:
                raise ConflictError("Transcript processing is no longer active")
            existing = await session.scalar(
                select(SubtitleSegmentModel.id).where(
                    SubtitleSegmentModel.media_asset_id == media_asset_id
                )
            )
            if existing is not None:
                raise RuntimeError("Partial transcript publication detected")
            now = datetime.now(UTC)
            created: list[SubtitleSegment] = []
            for ordinal, item in enumerate(segments):
                segment_id = new_uuid7()
                revision_id = new_uuid7()
                segment = SubtitleSegmentModel(
                    id=segment_id,
                    project_id=state.project_id,
                    media_asset_id=media_asset_id,
                    ordinal=ordinal,
                    start_us=item.start_us,
                    end_us=item.end_us,
                    current_source_revision_id=None,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(segment)
                await session.flush()
                revision = SourceRevisionModel(
                    id=revision_id,
                    subtitle_segment_id=segment_id,
                    version=1,
                    text=item.text,
                    origin=SourceRevisionOrigin.OCR,
                    confidence_ppm=round(item.confidence * 1_000_000),
                    editor_id=None,
                    parent_revision_id=None,
                    created_at=now,
                )
                session.add(revision)
                await session.flush()
                segment.current_source_revision_id = revision_id
                created.append(
                    SubtitleSegment(
                        id=segment_id,
                        project_id=state.project_id,
                        media_asset_id=media_asset_id,
                        ordinal=ordinal,
                        start_us=item.start_us,
                        end_us=item.end_us,
                        current_revision=_revision(revision),
                        version=1,
                        created_at=now,
                        updated_at=now,
                    )
                )
            state.status = TranscriptStatus.WAITING_FOR_REVIEW
            state.error_code = None
            state.version += 1
            state.updated_at = now
            return tuple(created)

    async def set_transcript_status(
        self,
        media_asset_id: UUID,
        status: TranscriptStatus,
        *,
        error_code: str | None = None,
    ) -> None:
        async with self._sessions.session() as session, session.begin():
            row = await session.get(TranscriptStateModel, media_asset_id, with_for_update=True)
            if row is None:
                raise NotFoundError("Transcript state not found")
            current = TranscriptStatus(row.status)
            if current in {TranscriptStatus.APPROVED, TranscriptStatus.CANCELLED} and status in {
                TranscriptStatus.FAILED,
                TranscriptStatus.PROCESSING,
            }:
                return
            if current != status or row.error_code != error_code:
                row.status = status
                row.error_code = error_code
                row.version += 1
                row.updated_at = datetime.now(UTC)

    async def begin_stage(
        self,
        *,
        project_id: UUID,
        media_asset_id: UUID,
        workflow_id: str,
        stage_name: str,
        attempt: int,
        input_fingerprint: str,
        worker_id: str,
    ) -> UUID:
        return await self._media_repository.begin_stage(
            project_id=project_id,
            media_asset_id=media_asset_id,
            workflow_id=workflow_id,
            stage_name=stage_name,
            attempt=attempt,
            input_fingerprint=input_fingerprint,
            worker_id=worker_id,
        )

    async def finish_stage(
        self,
        stage_execution_id: UUID,
        *,
        status: str,
        error_code: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        await self._media_repository.finish_stage(
            stage_execution_id,
            status=status,
            error_code=error_code,
            retryable=retryable,
        )
