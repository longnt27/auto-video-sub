from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from auto_video_sub_application.translation_ports import (
    ContextProviderResult,
    TranslationBatchRecord,
    TranslationProviderResult,
    TranslationRecord,
    TranslationSegmentView,
    TranslationSnapshot,
    TranslationSourceSegment,
)
from auto_video_sub_domain import (
    ConflictError,
    ContextEntity,
    ContextVersion,
    NotFoundError,
    QuotaExceededError,
    SourceRevision,
    SourceRevisionOrigin,
    SubtitleSegment,
    TonePreset,
    TranscriptStatus,
    TranslationBatchPlan,
    TranslationFinding,
    TranslationPolicyVersion,
    TranslationRevision,
    TranslationRevisionOrigin,
    TranslationStatus,
    contains_han,
    new_uuid7,
    validate_translation_items,
)
from sqlalchemy import func, select

from auto_video_sub_infrastructure.database import SessionProvider
from auto_video_sub_infrastructure.models import (
    ProjectModel,
    SourceRevisionModel,
    SubtitleSegmentModel,
    TranscriptStateModel,
)
from auto_video_sub_infrastructure.translation_models import (
    ContextEntityModel,
    ContextVersionModel,
    SegmentTranslationHeadModel,
    TranslationBatchModel,
    TranslationBudgetAccountModel,
    TranslationPolicyVersionModel,
    TranslationRevisionModel,
    TranslationStateModel,
    TranslationUsageModel,
)


def _policy(row: TranslationPolicyVersionModel) -> TranslationPolicyVersion:
    return TranslationPolicyVersion(
        id=row.id,
        project_id=row.project_id,
        preset=TonePreset(row.preset),
        prompt_version=row.prompt_version,
        prompt_checksum=row.prompt_checksum,
        provider=row.provider,
        model=row.model,
        version=row.version,
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _revision(row: TranslationRevisionModel) -> TranslationRevision:
    return TranslationRevision(
        id=row.id,
        subtitle_segment_id=row.subtitle_segment_id,
        version=row.version,
        text=row.text,
        origin=TranslationRevisionOrigin(row.origin),
        context_version_id=row.context_version_id,
        policy_version_id=row.policy_version_id,
        provider=row.provider,
        model=row.model,
        prompt_version=row.prompt_version,
        editor_id=row.editor_id,
        parent_revision_id=row.parent_revision_id,
        created_at=row.created_at,
    )


def _record(row: TranslationStateModel) -> TranslationRecord:
    return TranslationRecord(
        project_id=row.project_id,
        media_asset_id=row.media_asset_id,
        status=TranslationStatus(row.status),
        transcript_version=row.transcript_version,
        policy_version_id=row.policy_version_id,
        context_version_id=row.context_version_id,
        workflow_id=row.workflow_id,
        error_code=row.error_code,
        estimated_cost_micros=row.estimated_cost_micros,
        reserved_cost_micros=row.reserved_cost_micros,
        actual_cost_micros=row.actual_cost_micros,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyTranslationRepository:
    def __init__(
        self,
        sessions: SessionProvider,
        *,
        default_translation_budget_micros: int,
        input_cost_micros_per_million_tokens: int,
        output_cost_micros_per_million_tokens: int,
    ) -> None:
        self._sessions = sessions
        self._default_budget = default_translation_budget_micros
        self._input_price = input_cost_micros_per_million_tokens
        self._output_price = output_cost_micros_per_million_tokens

    async def _owned_state(
        self, session: object, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> TranslationStateModel | None:
        result = await session.scalar(  # type: ignore[attr-defined]
            select(TranslationStateModel)
            .join(ProjectModel, ProjectModel.id == TranslationStateModel.project_id)
            .where(
                TranslationStateModel.media_asset_id == media_asset_id,
                TranslationStateModel.project_id == project_id,
                ProjectModel.owner_id == owner_id,
            )
        )
        return cast(TranslationStateModel | None, result)

    async def _source_segments(
        self, session: object, media_asset_id: UUID
    ) -> tuple[SubtitleSegment, ...]:
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
            source = await session.get(SourceRevisionModel, row.current_source_revision_id)  # type: ignore[attr-defined]
            if source is None:
                raise RuntimeError("Current source revision is missing")
            result.append(
                SubtitleSegment(
                    id=row.id,
                    project_id=row.project_id,
                    media_asset_id=row.media_asset_id,
                    ordinal=row.ordinal,
                    start_us=row.start_us,
                    end_us=row.end_us,
                    current_revision=SourceRevision(
                        id=source.id,
                        subtitle_segment_id=source.subtitle_segment_id,
                        version=source.version,
                        text=source.text,
                        origin=SourceRevisionOrigin(source.origin),
                        confidence=(
                            source.confidence_ppm / 1_000_000
                            if source.confidence_ppm is not None
                            else None
                        ),
                        editor_id=source.editor_id,
                        parent_revision_id=source.parent_revision_id,
                        created_at=source.created_at,
                    ),
                    version=row.version,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        return tuple(result)

    async def _context(self, session: object, context_id: UUID | None) -> ContextVersion | None:
        if context_id is None:
            return None
        row = await session.get(ContextVersionModel, context_id)  # type: ignore[attr-defined]
        if row is None:
            raise RuntimeError("Translation context version is missing")
        entity_rows = (
            await session.scalars(  # type: ignore[attr-defined]
                select(ContextEntityModel).where(ContextEntityModel.context_version_id == row.id)
            )
        ).all()
        entities = tuple(
            ContextEntity(
                id=item.id,
                kind=item.kind,
                source_forms=tuple(str(value) for value in item.source_forms.get("items", [])),
                preferred_vietnamese=item.preferred_vietnamese,
                confidence=item.confidence_ppm / 1_000_000,
                ambiguous=item.ambiguous,
                notes=item.notes,
                evidence_segment_ids=tuple(
                    UUID(str(value)) for value in item.evidence_segment_ids.get("items", [])
                ),
            )
            for item in entity_rows
        )
        return ContextVersion(
            id=row.id,
            project_id=row.project_id,
            media_asset_id=row.media_asset_id,
            transcript_version=row.transcript_version,
            version=row.version,
            summary=row.summary,
            entities=entities,
            approved=row.approved,
            parent_version_id=row.parent_version_id,
            created_by=row.created_by,
            created_at=row.created_at,
        )

    async def source_for_estimate(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> tuple[int, tuple[SubtitleSegment, ...]]:
        async with self._sessions.session() as session:
            transcript = await session.scalar(
                select(TranscriptStateModel)
                .join(ProjectModel, ProjectModel.id == TranscriptStateModel.project_id)
                .where(
                    TranscriptStateModel.media_asset_id == media_asset_id,
                    TranscriptStateModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
            )
            if transcript is None:
                raise NotFoundError("Source transcript not found")
            if TranscriptStatus(transcript.status) is not TranscriptStatus.APPROVED:
                raise ConflictError("Source transcript must be approved before translation")
            segments = await self._source_segments(session, media_asset_id)
            return transcript.version, segments

    async def prepare(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        preset: TonePreset,
        provider: str,
        model: str,
        prompt_version: str,
        prompt_checksum: str,
        estimated_cost_micros: int,
        max_cost_micros: int,
    ) -> TranslationRecord:
        if estimated_cost_micros < 0 or max_cost_micros < estimated_cost_micros:
            raise ConflictError("Confirmed translation budget does not cover the estimate")
        async with self._sessions.session() as session, session.begin():
            project = await session.scalar(
                select(ProjectModel).where(
                    ProjectModel.id == project_id, ProjectModel.owner_id == owner_id
                )
            )
            if project is None:
                raise NotFoundError("Project not found")
            transcript = await session.get(
                TranscriptStateModel, media_asset_id, with_for_update=True
            )
            if transcript is None or transcript.project_id != project_id:
                raise NotFoundError("Source transcript not found")
            if TranscriptStatus(transcript.status) is not TranscriptStatus.APPROVED:
                raise ConflictError("Source transcript must be approved before translation")

            state = await session.get(TranslationStateModel, media_asset_id, with_for_update=True)
            if state is not None:
                current_policy = await session.get(
                    TranslationPolicyVersionModel, state.policy_version_id
                )
                if current_policy is None:
                    raise RuntimeError("Translation policy is missing")
                current_status = TranslationStatus(state.status)
                if current_policy.preset == preset and current_status not in {
                    TranslationStatus.FAILED,
                    TranslationStatus.CANCELLED,
                }:
                    return _record(state)
                if current_status not in {
                    TranslationStatus.APPROVED,
                    TranslationStatus.FAILED,
                    TranslationStatus.CANCELLED,
                }:
                    raise ConflictError(
                        "Cancel or finish the current translation before changing tone"
                    )
                if state.reserved_cost_micros:
                    await self._reconcile_budget_locked(session, state, owner_id)

            budget = await session.get(
                TranslationBudgetAccountModel, owner_id, with_for_update=True
            )
            now = datetime.now(UTC)
            if budget is None:
                budget = TranslationBudgetAccountModel(
                    user_id=owner_id,
                    max_cost_micros=self._default_budget,
                    reserved_cost_micros=0,
                    used_cost_micros=0,
                    updated_at=now,
                )
                session.add(budget)
                await session.flush()
            if (
                budget.used_cost_micros + budget.reserved_cost_micros + max_cost_micros
                > budget.max_cost_micros
            ):
                raise QuotaExceededError(
                    "Translation budget exceeded", code="TRANSLATION_BUDGET_EXCEEDED"
                )
            budget.reserved_cost_micros += max_cost_micros
            budget.updated_at = now

            latest_policy_version = await session.scalar(
                select(func.max(TranslationPolicyVersionModel.version)).where(
                    TranslationPolicyVersionModel.project_id == project_id
                )
            )
            policy = TranslationPolicyVersionModel(
                id=new_uuid7(),
                project_id=project_id,
                preset=preset,
                prompt_version=prompt_version,
                prompt_checksum=prompt_checksum,
                provider=provider,
                model=model,
                version=(latest_policy_version or 0) + 1,
                created_by=owner_id,
                created_at=now,
            )
            session.add(policy)
            await session.flush()

            if state is None:
                state = TranslationStateModel(
                    media_asset_id=media_asset_id,
                    project_id=project_id,
                    status=TranslationStatus.CONTEXT_PROCESSING,
                    transcript_version=transcript.version,
                    policy_version_id=policy.id,
                    context_version_id=None,
                    workflow_id=None,
                    error_code=None,
                    estimated_cost_micros=estimated_cost_micros,
                    reserved_cost_micros=max_cost_micros,
                    actual_cost_micros=0,
                    findings={"items": []},
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(state)
            else:
                state.status = TranslationStatus.CONTEXT_PROCESSING
                state.transcript_version = transcript.version
                state.policy_version_id = policy.id
                state.context_version_id = None
                state.workflow_id = None
                state.error_code = None
                state.estimated_cost_micros = estimated_cost_micros
                state.reserved_cost_micros = max_cost_micros
                state.actual_cost_micros = 0
                state.findings = {"items": []}
                state.version += 1
                state.updated_at = now
            return _record(state)

    async def bind_workflow(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        workflow_id: str,
    ) -> TranslationRecord:
        async with self._sessions.session() as session, session.begin():
            state = await self._owned_state(session, owner_id, project_id, media_asset_id)
            if state is None:
                raise NotFoundError("Translation state not found")
            if state.workflow_id is not None and state.workflow_id != workflow_id:
                raise ConflictError("Translation is already bound to another workflow")
            state.workflow_id = workflow_id
            state.updated_at = datetime.now(UTC)
            return _record(state)

    async def snapshot(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> TranslationSnapshot:
        async with self._sessions.session() as session:
            state = await self._owned_state(session, owner_id, project_id, media_asset_id)
            if state is None:
                raise NotFoundError("Translation not found")
            policy_row = await session.get(TranslationPolicyVersionModel, state.policy_version_id)
            if policy_row is None:
                raise RuntimeError("Translation policy is missing")
            context = await self._context(session, state.context_version_id)
            source_segments = await self._source_segments(session, media_asset_id)
            views: list[TranslationSegmentView] = []
            for source in source_segments:
                head = await session.get(SegmentTranslationHeadModel, source.id)
                revision = None
                if head is not None:
                    revision_row = await session.get(
                        TranslationRevisionModel, head.translation_revision_id
                    )
                    if revision_row is None:
                        raise RuntimeError("Translation head revision is missing")
                    if revision_row.policy_version_id == state.policy_version_id:
                        revision = _revision(revision_row)
                views.append(TranslationSegmentView(source=source, translation=revision))
            findings = tuple(
                TranslationFinding(
                    code=str(item.get("code", "TRANSLATION_FINDING")),
                    segment_id=(UUID(str(item["segment_id"])) if item.get("segment_id") else None),
                    message=str(item.get("message", "")),
                )
                for item in state.findings.get("items", [])
            )
            return TranslationSnapshot(
                record=_record(state),
                policy=_policy(policy_row),
                context=context,
                segments=tuple(views),
                findings=findings,
            )

    async def approve_context(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
        summary: str | None,
        entities: tuple[ContextEntity, ...] | None,
    ) -> ContextVersion:
        async with self._sessions.session() as session, session.begin():
            state = await self._owned_state(session, owner_id, project_id, media_asset_id)
            if state is None:
                raise NotFoundError("Translation not found")
            await session.refresh(state, with_for_update=True)
            if TranslationStatus(state.status) is not TranslationStatus.WAITING_FOR_CONTEXT_REVIEW:
                raise ConflictError("Translation context is not waiting for review")
            if state.version != expected_version:
                raise ConflictError("Translation state changed after it was loaded")
            current = await self._context(session, state.context_version_id)
            if current is None:
                raise RuntimeError("Translation context is missing")
            selected_entities = entities if entities is not None else current.entities
            selected_summary = summary if summary is not None else current.summary
            now = datetime.now(UTC)
            version = ContextVersionModel(
                id=new_uuid7(),
                project_id=project_id,
                media_asset_id=media_asset_id,
                transcript_version=state.transcript_version,
                version=current.version + 1,
                summary=selected_summary,
                approved=True,
                parent_version_id=current.id,
                created_by=owner_id,
                created_at=now,
            )
            session.add(version)
            await session.flush()
            for entity in selected_entities:
                entity.validate()
                session.add(
                    ContextEntityModel(
                        id=entity.id,
                        context_version_id=version.id,
                        kind=entity.kind,
                        source_forms={"items": list(entity.source_forms)},
                        preferred_vietnamese=entity.preferred_vietnamese,
                        confidence_ppm=round(entity.confidence * 1_000_000),
                        ambiguous=entity.ambiguous,
                        notes=entity.notes,
                        evidence_segment_ids={
                            "items": [str(value) for value in entity.evidence_segment_ids]
                        },
                    )
                )
            state.context_version_id = version.id
            state.status = TranslationStatus.TRANSLATING
            state.version += 1
            state.updated_at = now
            await session.flush()
            result = await self._context(session, version.id)
            if result is None:
                raise RuntimeError("Approved context was not persisted")
            return result

    async def edit_segment(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        segment_id: UUID,
        text: str,
        expected_version: int,
    ) -> TranslationRevision:
        async with self._sessions.session() as session, session.begin():
            state = await self._owned_state(session, owner_id, project_id, media_asset_id)
            if state is None:
                raise NotFoundError("Translation not found")
            if TranslationStatus(state.status) is not TranslationStatus.WAITING_FOR_REVIEW:
                raise ConflictError("Translation is not editable in its current state")
            if state.context_version_id is None:
                raise RuntimeError("Translation context is missing")
            segment = await session.scalar(
                select(SubtitleSegmentModel).where(
                    SubtitleSegmentModel.id == segment_id,
                    SubtitleSegmentModel.media_asset_id == media_asset_id,
                    SubtitleSegmentModel.project_id == project_id,
                )
            )
            if segment is None:
                raise NotFoundError("Subtitle segment not found")
            head = await session.get(SegmentTranslationHeadModel, segment_id, with_for_update=True)
            if head is None:
                raise ConflictError("Subtitle segment has no translation to edit")
            if head.version != expected_version:
                raise ConflictError("Translation segment was edited by another request")
            parent = await session.get(TranslationRevisionModel, head.translation_revision_id)
            if parent is None:
                raise RuntimeError("Current translation revision is missing")
            now = datetime.now(UTC)
            revision = TranslationRevisionModel(
                id=new_uuid7(),
                subtitle_segment_id=segment_id,
                version=parent.version + 1,
                text=text,
                origin=TranslationRevisionOrigin.USER,
                context_version_id=state.context_version_id,
                policy_version_id=state.policy_version_id,
                provider=None,
                model=None,
                prompt_version=None,
                editor_id=owner_id,
                parent_revision_id=parent.id,
                created_at=now,
            )
            session.add(revision)
            await session.flush()
            head.translation_revision_id = revision.id
            head.version += 1
            head.updated_at = now
            state.version += 1
            state.updated_at = now
            return _revision(revision)

    async def approve_translation(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
    ) -> TranslationRecord:
        async with self._sessions.session() as session, session.begin():
            state = await self._owned_state(session, owner_id, project_id, media_asset_id)
            if state is None:
                raise NotFoundError("Translation not found")
            await session.refresh(state, with_for_update=True)
            if TranslationStatus(state.status) is not TranslationStatus.WAITING_FOR_REVIEW:
                raise ConflictError("Translation is not waiting for review")
            if state.version != expected_version:
                raise ConflictError("Translation changed after it was loaded")
            source_segments = await self._source_segments(session, media_asset_id)
            for segment in source_segments:
                head = await session.get(SegmentTranslationHeadModel, segment.id)
                if head is None:
                    raise ConflictError("Translation is incomplete")
                revision = await session.get(TranslationRevisionModel, head.translation_revision_id)
                if revision is None or revision.policy_version_id != state.policy_version_id:
                    raise ConflictError("Translation is incomplete for the selected tone")
            state.status = TranslationStatus.APPROVED
            state.version += 1
            state.updated_at = datetime.now(UTC)
            return _record(state)

    async def mark_cancelled(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> TranslationRecord:
        async with self._sessions.session() as session, session.begin():
            state = await self._owned_state(session, owner_id, project_id, media_asset_id)
            if state is None:
                raise NotFoundError("Translation not found")
            await session.refresh(state, with_for_update=True)
            if TranslationStatus(state.status) is TranslationStatus.APPROVED:
                raise ConflictError("Approved translation cannot be cancelled")
            if TranslationStatus(state.status) is not TranslationStatus.CANCELLED:
                state.status = TranslationStatus.CANCELLED
                state.error_code = "CANCELLED"
                state.version += 1
                state.updated_at = datetime.now(UTC)
            await self._reconcile_budget_locked(session, state, owner_id)
            return _record(state)

    async def get_record_internal(self, media_asset_id: UUID) -> TranslationRecord:
        async with self._sessions.session() as session:
            row = await session.get(TranslationStateModel, media_asset_id)
            if row is None:
                raise NotFoundError("Translation state not found")
            return _record(row)

    async def get_policy_internal(self, policy_version_id: UUID) -> TranslationPolicyVersion:
        async with self._sessions.session() as session:
            row = await session.get(TranslationPolicyVersionModel, policy_version_id)
            if row is None:
                raise NotFoundError("Translation policy not found")
            return _policy(row)

    async def get_context_internal(self, media_asset_id: UUID) -> ContextVersion | None:
        async with self._sessions.session() as session:
            state = await session.get(TranslationStateModel, media_asset_id)
            if state is None:
                raise NotFoundError("Translation state not found")
            return await self._context(session, state.context_version_id)

    async def load_source_segments_internal(
        self, media_asset_id: UUID
    ) -> tuple[TranslationSourceSegment, ...]:
        async with self._sessions.session() as session:
            segments = await self._source_segments(session, media_asset_id)
            return tuple(
                TranslationSourceSegment(
                    id=item.id,
                    start_us=item.start_us,
                    end_us=item.end_us,
                    text=item.current_revision.text,
                )
                for item in segments
            )

    async def publish_context(
        self,
        *,
        media_asset_id: UUID,
        result: ContextProviderResult,
        provider: str,
        model: str,
        prompt_version: str,
    ) -> ContextVersion:
        del provider, model, prompt_version
        async with self._sessions.session() as session, session.begin():
            state = await session.get(TranslationStateModel, media_asset_id, with_for_update=True)
            if state is None:
                raise NotFoundError("Translation state not found")
            if (
                TranslationStatus(state.status)
                in {
                    TranslationStatus.WAITING_FOR_CONTEXT_REVIEW,
                    TranslationStatus.TRANSLATING,
                    TranslationStatus.WAITING_FOR_REVIEW,
                    TranslationStatus.APPROVED,
                }
                and state.context_version_id is not None
            ):
                existing_context = await self._context(session, state.context_version_id)
                if existing_context is None:
                    raise RuntimeError("Translation context is missing")
                return existing_context
            if TranslationStatus(state.status) is not TranslationStatus.CONTEXT_PROCESSING:
                raise ConflictError("Translation context processing is no longer active")
            latest_version = await session.scalar(
                select(func.max(ContextVersionModel.version)).where(
                    ContextVersionModel.media_asset_id == media_asset_id
                )
            )
            now = datetime.now(UTC)
            context_row = ContextVersionModel(
                id=new_uuid7(),
                project_id=state.project_id,
                media_asset_id=media_asset_id,
                transcript_version=state.transcript_version,
                version=(latest_version or 0) + 1,
                summary=result.summary.strip(),
                approved=False,
                parent_version_id=None,
                created_by=None,
                created_at=now,
            )
            session.add(context_row)
            await session.flush()
            for item in result.entities:
                session.add(
                    ContextEntityModel(
                        id=new_uuid7(),
                        context_version_id=context_row.id,
                        kind=item.kind,
                        source_forms={"items": list(item.source_forms)},
                        preferred_vietnamese=item.preferred_vietnamese,
                        confidence_ppm=round(item.confidence * 1_000_000),
                        ambiguous=item.ambiguous,
                        notes=item.notes,
                        evidence_segment_ids={
                            "items": [str(value) for value in item.evidence_segment_ids]
                        },
                    )
                )
            for question in result.unresolved_questions:
                session.add(
                    ContextEntityModel(
                        id=new_uuid7(),
                        context_version_id=context_row.id,
                        kind="ambiguity",
                        source_forms={"items": [question]},
                        preferred_vietnamese=None,
                        confidence_ppm=0,
                        ambiguous=True,
                        notes="Provider flagged this question for human review.",
                        evidence_segment_ids={"items": []},
                    )
                )
            state.context_version_id = context_row.id
            state.status = TranslationStatus.WAITING_FOR_CONTEXT_REVIEW
            state.version += 1
            state.updated_at = now
            await session.flush()
            published = await self._context(session, context_row.id)
            if published is None:
                raise RuntimeError("Translation context was not persisted")
            return published

    async def create_batches(
        self, *, media_asset_id: UUID, plans: tuple[TranslationBatchPlan, ...]
    ) -> tuple[TranslationBatchRecord, ...]:
        async with self._sessions.session() as session, session.begin():
            state = await session.get(TranslationStateModel, media_asset_id, with_for_update=True)
            if state is None:
                raise NotFoundError("Translation state not found")
            if state.context_version_id is None:
                raise ConflictError("Translation context is not approved")
            context = await session.get(ContextVersionModel, state.context_version_id)
            if context is None or not context.approved:
                raise ConflictError("Translation context is not approved")
            existing = (
                await session.scalars(
                    select(TranslationBatchModel)
                    .where(TranslationBatchModel.policy_version_id == state.policy_version_id)
                    .order_by(TranslationBatchModel.ordinal)
                )
            ).all()
            if existing:
                return tuple(self._batch_record(row) for row in existing)
            now = datetime.now(UTC)
            rows: list[TranslationBatchModel] = []
            for plan in plans:
                row = TranslationBatchModel(
                    id=new_uuid7(),
                    project_id=state.project_id,
                    media_asset_id=media_asset_id,
                    ordinal=plan.ordinal,
                    owned_segment_ids={"items": [str(value) for value in plan.owned_segment_ids]},
                    overlap_segment_ids={
                        "items": [str(value) for value in plan.overlap_segment_ids]
                    },
                    context_version_id=state.context_version_id,
                    policy_version_id=state.policy_version_id,
                    status="pending",
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                rows.append(row)
            return tuple(self._batch_record(row) for row in rows)

    def _batch_record(self, row: TranslationBatchModel) -> TranslationBatchRecord:
        plan = TranslationBatchPlan(
            ordinal=row.ordinal,
            owned_segment_ids=tuple(
                UUID(str(value)) for value in row.owned_segment_ids.get("items", [])
            ),
            overlap_segment_ids=tuple(
                UUID(str(value)) for value in row.overlap_segment_ids.get("items", [])
            ),
        )
        return TranslationBatchRecord(
            id=row.id,
            project_id=row.project_id,
            media_asset_id=row.media_asset_id,
            ordinal=row.ordinal,
            plan=plan,
            status=row.status,
            context_version_id=row.context_version_id,
            policy_version_id=row.policy_version_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_batch_internal(self, batch_id: UUID) -> TranslationBatchRecord:
        async with self._sessions.session() as session:
            row = await session.get(TranslationBatchModel, batch_id)
            if row is None:
                raise NotFoundError("Translation batch not found")
            return self._batch_record(row)

    async def publish_batch_result(
        self,
        *,
        batch_id: UUID,
        result: TranslationProviderResult,
        provider: str,
        model: str,
        prompt_version: str,
    ) -> None:
        async with self._sessions.session() as session, session.begin():
            batch = await session.get(TranslationBatchModel, batch_id, with_for_update=True)
            if batch is None:
                raise NotFoundError("Translation batch not found")
            if batch.status == "succeeded":
                return
            state = await session.get(
                TranslationStateModel, batch.media_asset_id, with_for_update=True
            )
            if state is None:
                raise NotFoundError("Translation state not found")
            if state.policy_version_id != batch.policy_version_id:
                raise ConflictError("Translation batch belongs to a superseded tone policy")
            validated = validate_translation_items(
                owned_segment_ids=tuple(
                    UUID(str(value)) for value in batch.owned_segment_ids.get("items", [])
                ),
                items=tuple((item.segment_id, item.text) for item in result.items),
            )
            now = datetime.now(UTC)
            for segment_id, text in validated:
                segment = await session.get(SubtitleSegmentModel, segment_id)
                if segment is None or segment.media_asset_id != batch.media_asset_id:
                    raise ConflictError("Translation batch references an invalid segment")
                latest_revision_version = await session.scalar(
                    select(func.max(TranslationRevisionModel.version)).where(
                        TranslationRevisionModel.subtitle_segment_id == segment_id
                    )
                )
                head = await session.get(
                    SegmentTranslationHeadModel, segment_id, with_for_update=True
                )
                parent_id = head.translation_revision_id if head is not None else None
                revision = TranslationRevisionModel(
                    id=new_uuid7(),
                    subtitle_segment_id=segment_id,
                    version=(latest_revision_version or 0) + 1,
                    text=text,
                    origin=TranslationRevisionOrigin.CLOUD_TRANSLATION,
                    context_version_id=batch.context_version_id,
                    policy_version_id=batch.policy_version_id,
                    provider=provider,
                    model=model,
                    prompt_version=prompt_version,
                    editor_id=None,
                    parent_revision_id=parent_id,
                    created_at=now,
                )
                session.add(revision)
                await session.flush()
                if head is None:
                    head = SegmentTranslationHeadModel(
                        subtitle_segment_id=segment_id,
                        translation_revision_id=revision.id,
                        version=1,
                        updated_at=now,
                    )
                    session.add(head)
                else:
                    head.translation_revision_id = revision.id
                    head.version += 1
                    head.updated_at = now
            batch.status = "succeeded"
            batch.updated_at = now

    async def finalize_translation(self, media_asset_id: UUID) -> tuple[TranslationFinding, ...]:
        async with self._sessions.session() as session, session.begin():
            state = await session.get(TranslationStateModel, media_asset_id, with_for_update=True)
            if state is None:
                raise NotFoundError("Translation state not found")
            segments = await self._source_segments(session, media_asset_id)
            findings: list[TranslationFinding] = []
            for segment in segments:
                head = await session.get(SegmentTranslationHeadModel, segment.id)
                if head is None:
                    findings.append(
                        TranslationFinding(
                            code="TRANSLATION_MISSING_SEGMENT",
                            segment_id=segment.id,
                            message="No Vietnamese translation was produced for this segment.",
                        )
                    )
                    continue
                revision = await session.get(TranslationRevisionModel, head.translation_revision_id)
                if revision is None or revision.policy_version_id != state.policy_version_id:
                    findings.append(
                        TranslationFinding(
                            code="TRANSLATION_MISSING_SEGMENT",
                            segment_id=segment.id,
                            message="No Vietnamese translation was produced for the current tone.",
                        )
                    )
                    continue
                if contains_han(revision.text):
                    findings.append(
                        TranslationFinding(
                            code="TRANSLATION_RESIDUAL_HAN",
                            segment_id=segment.id,
                            message=(
                                "Vietnamese output still contains Han characters; "
                                "review before approval."
                            ),
                        )
                    )
            state.findings = {
                "items": [
                    {
                        "code": finding.code,
                        "segment_id": str(finding.segment_id) if finding.segment_id else None,
                        "message": finding.message,
                    }
                    for finding in findings
                ]
            }
            state.status = TranslationStatus.WAITING_FOR_REVIEW
            state.version += 1
            state.updated_at = datetime.now(UTC)
            return tuple(findings)

    async def set_translation_status(
        self,
        media_asset_id: UUID,
        status: TranslationStatus,
        *,
        error_code: str | None = None,
    ) -> None:
        async with self._sessions.session() as session, session.begin():
            state = await session.get(TranslationStateModel, media_asset_id, with_for_update=True)
            if state is None:
                raise NotFoundError("Translation state not found")
            state.status = status
            state.error_code = error_code
            state.version += 1
            state.updated_at = datetime.now(UTC)

    async def record_usage(
        self,
        *,
        media_asset_id: UUID,
        stage_name: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        provider_request_id: str | None,
    ) -> None:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Provider token usage cannot be negative")
        cost_micros = (
            input_tokens * self._input_price + output_tokens * self._output_price
        ) // 1_000_000
        async with self._sessions.session() as session, session.begin():
            state = await session.get(TranslationStateModel, media_asset_id, with_for_update=True)
            if state is None:
                raise NotFoundError("Translation state not found")
            session.add(
                TranslationUsageModel(
                    id=new_uuid7(),
                    project_id=state.project_id,
                    media_asset_id=media_asset_id,
                    policy_version_id=state.policy_version_id,
                    stage_name=stage_name,
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_micros=cost_micros,
                    provider_request_id=provider_request_id,
                    created_at=datetime.now(UTC),
                )
            )
            new_actual_cost = state.actual_cost_micros + cost_micros
            ceiling_exceeded = new_actual_cost > state.reserved_cost_micros
            state.actual_cost_micros = new_actual_cost
            state.updated_at = datetime.now(UTC)
            if ceiling_exceeded:
                state.status = TranslationStatus.FAILED
                state.error_code = "TRANSLATION_BUDGET_CEILING_EXCEEDED"
                state.version += 1

        if ceiling_exceeded:
            raise QuotaExceededError(
                "Translation provider usage exceeded the confirmed cost ceiling",
                code="TRANSLATION_BUDGET_CEILING_EXCEEDED",
            )

    async def _reconcile_budget_locked(
        self, session: object, state: TranslationStateModel, owner_id: UUID
    ) -> None:
        if state.reserved_cost_micros <= 0:
            return
        budget = await session.get(TranslationBudgetAccountModel, owner_id, with_for_update=True)  # type: ignore[attr-defined]
        if budget is None:
            raise RuntimeError("Translation budget account is missing")
        budget.reserved_cost_micros = max(
            0, budget.reserved_cost_micros - state.reserved_cost_micros
        )
        budget.used_cost_micros += state.actual_cost_micros
        budget.updated_at = datetime.now(UTC)
        state.reserved_cost_micros = 0

    async def reconcile_budget(self, media_asset_id: UUID) -> None:
        async with self._sessions.session() as session, session.begin():
            state = await session.get(TranslationStateModel, media_asset_id, with_for_update=True)
            if state is None:
                raise NotFoundError("Translation state not found")
            owner_id = await session.scalar(
                select(ProjectModel.owner_id).where(ProjectModel.id == state.project_id)
            )
            if owner_id is None:
                raise RuntimeError("Translation project owner is missing")
            await self._reconcile_budget_locked(session, state, owner_id)
