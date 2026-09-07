from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from auto_video_sub_application.speech_ports import (
    PublishedSpeechArtifact,
    SpeechInputSegment,
    SpeechRecord,
    SpeechSegmentView,
    SpeechSnapshot,
)
from auto_video_sub_domain import (
    ArtifactState,
    ConflictError,
    DurationFitPolicy,
    NotFoundError,
    RetentionClass,
    SpeechAttempt,
    SpeechAttemptOutcome,
    SpeechSegmentStatus,
    SpeechStatus,
    SpeechTextOrigin,
    TonePreset,
    TranslationStatus,
    new_uuid7,
)
from sqlalchemy import select

from auto_video_sub_infrastructure.database import SessionProvider
from auto_video_sub_infrastructure.models import (
    ArtifactEdgeModel,
    ArtifactModel,
    ProjectModel,
    SubtitleSegmentModel,
)
from auto_video_sub_infrastructure.speech_models import (
    SpeechAttemptModel,
    SpeechSegmentStateModel,
    SpeechStateModel,
)
from auto_video_sub_infrastructure.translation_models import (
    ContextEntityModel,
    SegmentTranslationHeadModel,
    TranslationPolicyVersionModel,
    TranslationRevisionModel,
    TranslationStateModel,
)


def _policy(row: SpeechStateModel) -> DurationFitPolicy:
    return DurationFitPolicy(
        version=row.policy_version,
        tolerance_us=row.tolerance_us,
        max_speed_factor_ppm=row.max_speed_factor_ppm,
        max_rewrite_attempts=row.max_rewrite_attempts,
    )


def _record(row: SpeechStateModel) -> SpeechRecord:
    return SpeechRecord(
        project_id=row.project_id,
        media_asset_id=row.media_asset_id,
        status=SpeechStatus(row.status),
        workflow_id=row.workflow_id,
        error_code=row.error_code,
        provider=row.provider,
        model=row.model,
        model_revision=row.model_revision,
        voice_id=row.voice_id,
        policy=_policy(row),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _attempt(row: SpeechAttemptModel) -> SpeechAttempt:
    value = SpeechAttempt(
        id=row.id,
        project_id=row.project_id,
        media_asset_id=row.media_asset_id,
        subtitle_segment_id=row.subtitle_segment_id,
        attempt_index=row.attempt_index,
        parent_attempt_id=row.parent_attempt_id,
        translation_revision_id=row.translation_revision_id,
        text=row.text,
        text_origin=SpeechTextOrigin(row.text_origin),
        provider=row.provider,
        model=row.model,
        model_revision=row.model_revision,
        voice_id=row.voice_id,
        policy_version=row.policy_version,
        raw_audio_artifact_id=row.raw_audio_artifact_id,
        trimmed_audio_artifact_id=row.trimmed_audio_artifact_id,
        final_audio_artifact_id=row.final_audio_artifact_id,
        envelope_artifact_id=row.envelope_artifact_id,
        measured_duration_us=row.measured_duration_us,
        trimmed_duration_us=row.trimmed_duration_us,
        final_duration_us=row.final_duration_us,
        silence_removed_us=row.silence_removed_us,
        speed_factor_ppm=row.speed_factor_ppm,
        slot_us=row.slot_us,
        tolerance_us=row.tolerance_us,
        outcome=SpeechAttemptOutcome(row.outcome) if row.outcome is not None else None,
        error_code=row.error_code,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )
    value.validate()
    return value


class SqlAlchemySpeechRepository:
    def __init__(self, sessions: SessionProvider) -> None:
        self._sessions = sessions

    async def _owned_state(
        self, session: object, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> SpeechStateModel | None:
        result = await session.scalar(  # type: ignore[attr-defined]
            select(SpeechStateModel)
            .join(ProjectModel, ProjectModel.id == SpeechStateModel.project_id)
            .where(
                SpeechStateModel.media_asset_id == media_asset_id,
                SpeechStateModel.project_id == project_id,
                ProjectModel.owner_id == owner_id,
            )
        )
        return cast(SpeechStateModel | None, result)

    async def _inputs(
        self, session: object, media_asset_id: UUID
    ) -> tuple[SpeechInputSegment, ...]:
        translation = await session.get(TranslationStateModel, media_asset_id)  # type: ignore[attr-defined]
        if translation is None:
            raise NotFoundError("Translation not found")
        if TranslationStatus(translation.status) is not TranslationStatus.APPROVED:
            raise ConflictError("Vietnamese translation must be approved before speech fitting")
        policy = await session.get(  # type: ignore[attr-defined]
            TranslationPolicyVersionModel, translation.policy_version_id
        )
        if policy is None:
            raise RuntimeError("Translation policy is missing")

        protected_terms: tuple[str, ...] = ()
        if translation.context_version_id is not None:
            entity_rows = (
                await session.scalars(  # type: ignore[attr-defined]
                    select(ContextEntityModel).where(
                        ContextEntityModel.context_version_id == translation.context_version_id
                    )
                )
            ).all()
            protected_terms = tuple(
                sorted(
                    {
                        item.preferred_vietnamese.strip()
                        for item in entity_rows
                        if item.preferred_vietnamese and item.preferred_vietnamese.strip()
                    }
                )
            )

        segment_rows = (
            await session.scalars(  # type: ignore[attr-defined]
                select(SubtitleSegmentModel)
                .where(SubtitleSegmentModel.media_asset_id == media_asset_id)
                .order_by(SubtitleSegmentModel.ordinal)
            )
        ).all()
        result: list[SpeechInputSegment] = []
        for segment in segment_rows:
            head = await session.get(SegmentTranslationHeadModel, segment.id)  # type: ignore[attr-defined]
            if head is None:
                raise ConflictError(
                    "Every subtitle segment needs an approved Vietnamese translation"
                )
            revision = await session.get(  # type: ignore[attr-defined]
                TranslationRevisionModel, head.translation_revision_id
            )
            if revision is None or revision.policy_version_id != translation.policy_version_id:
                raise ConflictError("Vietnamese translation is stale for the current tone policy")
            result.append(
                SpeechInputSegment(
                    id=segment.id,
                    project_id=segment.project_id,
                    media_asset_id=segment.media_asset_id,
                    ordinal=segment.ordinal,
                    start_us=segment.start_us,
                    end_us=segment.end_us,
                    translation_revision_id=revision.id,
                    text=revision.text,
                    tone=TonePreset(policy.preset),
                    protected_terms=protected_terms,
                )
            )
        if not result:
            raise ConflictError("Approved translation has no segments to synthesize")
        return tuple(result)

    async def prepare(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        provider: str,
        model: str,
        model_revision: str,
        voice_id: str,
        policy: DurationFitPolicy,
    ) -> SpeechRecord:
        policy.validate()
        async with self._sessions.session() as session, session.begin():
            project = await session.scalar(
                select(ProjectModel).where(
                    ProjectModel.id == project_id, ProjectModel.owner_id == owner_id
                )
            )
            if project is None:
                raise NotFoundError("Project not found")
            inputs = await self._inputs(session, media_asset_id)
            if any(item.project_id != project_id for item in inputs):
                raise NotFoundError("Media asset not found")

            state = await session.get(SpeechStateModel, media_asset_id, with_for_update=True)
            now = datetime.now(UTC)
            same_configuration = (
                state is not None
                and state.provider == provider
                and state.model == model
                and state.model_revision == model_revision
                and state.voice_id == voice_id
                and state.policy_version == policy.version
                and state.tolerance_us == policy.tolerance_us
                and state.max_speed_factor_ppm == policy.max_speed_factor_ppm
                and state.max_rewrite_attempts == policy.max_rewrite_attempts
            )
            existing_segments = {
                row.subtitle_segment_id: row
                for row in (
                    await session.scalars(
                        select(SpeechSegmentStateModel).where(
                            SpeechSegmentStateModel.media_asset_id == media_asset_id
                        )
                    )
                ).all()
            }
            inputs_unchanged = all(
                (existing := existing_segments.get(item.id)) is not None
                and existing.translation_revision_id == item.translation_revision_id
                for item in inputs
            )
            if (
                state is not None
                and same_configuration
                and inputs_unchanged
                and SpeechStatus(state.status)
                in {
                    SpeechStatus.PROCESSING,
                    SpeechStatus.WAITING_FOR_REVIEW,
                    SpeechStatus.APPROVED,
                }
            ):
                return _record(state)
            if state is not None and SpeechStatus(state.status) is SpeechStatus.PROCESSING:
                raise ConflictError("Cancel the active speech workflow before changing its inputs")

            if state is None:
                state = SpeechStateModel(
                    media_asset_id=media_asset_id,
                    project_id=project_id,
                    status=SpeechStatus.PROCESSING,
                    workflow_id=None,
                    error_code=None,
                    provider=provider,
                    model=model,
                    model_revision=model_revision,
                    voice_id=voice_id,
                    policy_version=policy.version,
                    tolerance_us=policy.tolerance_us,
                    max_speed_factor_ppm=policy.max_speed_factor_ppm,
                    max_rewrite_attempts=policy.max_rewrite_attempts,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(state)
            else:
                state.status = SpeechStatus.PROCESSING
                state.workflow_id = None
                state.error_code = None
                state.provider = provider
                state.model = model
                state.model_revision = model_revision
                state.voice_id = voice_id
                state.policy_version = policy.version
                state.tolerance_us = policy.tolerance_us
                state.max_speed_factor_ppm = policy.max_speed_factor_ppm
                state.max_rewrite_attempts = policy.max_rewrite_attempts
                state.version += 1
                state.updated_at = now

            for item in inputs:
                segment_state = existing_segments.get(item.id)
                keep_fit = (
                    same_configuration
                    and segment_state is not None
                    and segment_state.translation_revision_id == item.translation_revision_id
                    and SpeechSegmentStatus(segment_state.status) is SpeechSegmentStatus.FIT
                    and segment_state.current_attempt_id is not None
                )
                if segment_state is None:
                    session.add(
                        SpeechSegmentStateModel(
                            subtitle_segment_id=item.id,
                            project_id=project_id,
                            media_asset_id=media_asset_id,
                            translation_revision_id=item.translation_revision_id,
                            status=SpeechSegmentStatus.PENDING,
                            current_attempt_id=None,
                            version=1,
                            updated_at=now,
                        )
                    )
                elif not keep_fit:
                    segment_state.translation_revision_id = item.translation_revision_id
                    segment_state.status = SpeechSegmentStatus.PENDING
                    segment_state.current_attempt_id = None
                    segment_state.version += 1
                    segment_state.updated_at = now
            await session.flush()
            return _record(state)

    async def bind_workflow(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        workflow_id: str,
    ) -> SpeechRecord:
        async with self._sessions.session() as session, session.begin():
            state = await self._owned_state(session, owner_id, project_id, media_asset_id)
            if state is None:
                raise NotFoundError("Speech state not found")
            await session.refresh(state, with_for_update=True)
            if state.workflow_id is not None and state.workflow_id != workflow_id:
                raise ConflictError("Speech is already bound to another workflow")
            state.workflow_id = workflow_id
            state.updated_at = datetime.now(UTC)
            return _record(state)

    async def snapshot(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> SpeechSnapshot:
        async with self._sessions.session() as session:
            state = await self._owned_state(session, owner_id, project_id, media_asset_id)
            if state is None:
                raise NotFoundError("Speech not found")
            inputs = await self._inputs(session, media_asset_id)
            views: list[SpeechSegmentView] = []
            for item in inputs:
                segment_state = await session.get(SpeechSegmentStateModel, item.id)
                if segment_state is None:
                    raise RuntimeError("Speech segment state is missing")
                attempt_rows = (
                    await session.scalars(
                        select(SpeechAttemptModel)
                        .where(
                            SpeechAttemptModel.subtitle_segment_id == item.id,
                            SpeechAttemptModel.translation_revision_id
                            == segment_state.translation_revision_id,
                        )
                        .order_by(SpeechAttemptModel.attempt_index)
                    )
                ).all()
                attempts = tuple(_attempt(row) for row in attempt_rows)
                current = None
                audio_key = None
                if segment_state.current_attempt_id is not None:
                    current_row = await session.get(
                        SpeechAttemptModel, segment_state.current_attempt_id
                    )
                    if current_row is None:
                        raise RuntimeError("Current speech attempt is missing")
                    current = _attempt(current_row)
                    if current_row.final_audio_artifact_id is not None:
                        artifact = await session.get(
                            ArtifactModel, current_row.final_audio_artifact_id
                        )
                        if artifact is None:
                            raise RuntimeError("Selected speech artifact is missing")
                        audio_key = artifact.object_key
                views.append(
                    SpeechSegmentView(
                        input=item,
                        status=SpeechSegmentStatus(segment_state.status),
                        current_attempt=current,
                        attempts=attempts,
                        audio_object_key=audio_key,
                    )
                )
            return SpeechSnapshot(record=_record(state), segments=tuple(views))

    async def approve(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
    ) -> SpeechRecord:
        async with self._sessions.session() as session, session.begin():
            state = await self._owned_state(session, owner_id, project_id, media_asset_id)
            if state is None:
                raise NotFoundError("Speech not found")
            await session.refresh(state, with_for_update=True)
            if state.version != expected_version:
                raise ConflictError("Speech state changed after it was loaded")
            if SpeechStatus(state.status) is SpeechStatus.APPROVED:
                return _record(state)
            if SpeechStatus(state.status) is not SpeechStatus.WAITING_FOR_REVIEW:
                raise ConflictError("Speech is not waiting for review")
            statuses = (
                await session.scalars(
                    select(SpeechSegmentStateModel.status).where(
                        SpeechSegmentStateModel.media_asset_id == media_asset_id
                    )
                )
            ).all()
            if not statuses or any(
                SpeechSegmentStatus(value) is not SpeechSegmentStatus.FIT for value in statuses
            ):
                raise ConflictError("Every speech segment must fit before approval")
            state.status = SpeechStatus.APPROVED
            state.version += 1
            state.updated_at = datetime.now(UTC)
            return _record(state)

    async def mark_cancelled(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> SpeechRecord:
        async with self._sessions.session() as session, session.begin():
            state = await self._owned_state(session, owner_id, project_id, media_asset_id)
            if state is None:
                raise NotFoundError("Speech not found")
            await session.refresh(state, with_for_update=True)
            state.status = SpeechStatus.CANCELLED
            state.version += 1
            state.updated_at = datetime.now(UTC)
            return _record(state)

    async def get_record_internal(self, media_asset_id: UUID) -> SpeechRecord:
        async with self._sessions.session() as session:
            state = await session.get(SpeechStateModel, media_asset_id)
            if state is None:
                raise NotFoundError("Speech not found")
            return _record(state)

    async def list_inputs_internal(self, media_asset_id: UUID) -> tuple[SpeechInputSegment, ...]:
        async with self._sessions.session() as session:
            return await self._inputs(session, media_asset_id)

    async def begin_attempt(
        self,
        *,
        segment: SpeechInputSegment,
        attempt_index: int,
        parent_attempt_id: UUID | None,
        text: str,
        text_origin: SpeechTextOrigin,
        provider: str,
        model: str,
        model_revision: str,
        voice_id: str,
        policy: DurationFitPolicy,
    ) -> SpeechAttempt:
        key = (
            f"speech-fit-v1/{segment.id}/{segment.translation_revision_id}/"
            f"{attempt_index}/{policy.version}/{provider}/{model_revision}/{voice_id}"
        )
        async with self._sessions.session() as session, session.begin():
            existing = await session.scalar(
                select(SpeechAttemptModel).where(SpeechAttemptModel.idempotency_key == key)
            )
            if existing is not None:
                return _attempt(existing)
            now = datetime.now(UTC)
            row = SpeechAttemptModel(
                id=new_uuid7(),
                project_id=segment.project_id,
                media_asset_id=segment.media_asset_id,
                subtitle_segment_id=segment.id,
                attempt_index=attempt_index,
                parent_attempt_id=parent_attempt_id,
                translation_revision_id=segment.translation_revision_id,
                text=text.strip(),
                text_origin=text_origin,
                provider=provider,
                model=model,
                model_revision=model_revision,
                voice_id=voice_id,
                policy_version=policy.version,
                idempotency_key=key,
                raw_audio_artifact_id=None,
                trimmed_audio_artifact_id=None,
                final_audio_artifact_id=None,
                envelope_artifact_id=None,
                measured_duration_us=None,
                trimmed_duration_us=None,
                final_duration_us=None,
                silence_removed_us=0,
                speed_factor_ppm=1_000_000,
                slot_us=segment.slot_us,
                tolerance_us=policy.tolerance_us,
                outcome=None,
                error_code=None,
                created_at=now,
                completed_at=None,
            )
            session.add(row)
            await session.flush()
            return _attempt(row)

    async def finish_attempt(
        self,
        *,
        attempt_id: UUID,
        artifacts: tuple[PublishedSpeechArtifact, ...],
        raw_audio_artifact_id: UUID,
        trimmed_audio_artifact_id: UUID,
        final_audio_artifact_id: UUID | None,
        envelope_artifact_id: UUID,
        measured_duration_us: int,
        trimmed_duration_us: int,
        final_duration_us: int | None,
        silence_removed_us: int,
        speed_factor_ppm: int,
        outcome: str,
        error_code: str | None = None,
    ) -> SpeechAttempt:
        parsed_outcome = SpeechAttemptOutcome(outcome)
        async with self._sessions.session() as session, session.begin():
            row = await session.get(SpeechAttemptModel, attempt_id, with_for_update=True)
            if row is None:
                raise NotFoundError("Speech attempt not found")
            if row.outcome is not None:
                return _attempt(row)
            now = datetime.now(UTC)
            for artifact in artifacts:
                existing = await session.get(ArtifactModel, artifact.id)
                if existing is None:
                    session.add(
                        ArtifactModel(
                            id=artifact.id,
                            project_id=row.project_id,
                            media_asset_id=row.media_asset_id,
                            kind=artifact.kind,
                            media_type=artifact.media_type,
                            byte_size=artifact.byte_size,
                            checksum_sha256=artifact.checksum_sha256,
                            object_key=artifact.object_key,
                            retention_class=RetentionClass.DERIVED_REUSABLE,
                            state=ArtifactState.AVAILABLE,
                            producer_stage_execution_id=None,
                            created_at=now,
                        )
                    )
            await session.flush()
            edge_pairs = [(raw_audio_artifact_id, trimmed_audio_artifact_id, "trimmed_from")]
            if (
                final_audio_artifact_id is not None
                and final_audio_artifact_id != trimmed_audio_artifact_id
            ):
                edge_pairs.append(
                    (trimmed_audio_artifact_id, final_audio_artifact_id, "speed_adjusted_from")
                )
            for parent, child, relation in edge_pairs:
                existing_edge = await session.scalar(
                    select(ArtifactEdgeModel).where(
                        ArtifactEdgeModel.parent_artifact_id == parent,
                        ArtifactEdgeModel.child_artifact_id == child,
                        ArtifactEdgeModel.relation == relation,
                    )
                )
                if existing_edge is None:
                    session.add(
                        ArtifactEdgeModel(
                            id=new_uuid7(),
                            parent_artifact_id=parent,
                            child_artifact_id=child,
                            relation=relation,
                            created_at=now,
                        )
                    )
            row.raw_audio_artifact_id = raw_audio_artifact_id
            row.trimmed_audio_artifact_id = trimmed_audio_artifact_id
            row.final_audio_artifact_id = final_audio_artifact_id
            row.envelope_artifact_id = envelope_artifact_id
            row.measured_duration_us = measured_duration_us
            row.trimmed_duration_us = trimmed_duration_us
            row.final_duration_us = final_duration_us
            row.silence_removed_us = silence_removed_us
            row.speed_factor_ppm = speed_factor_ppm
            row.outcome = parsed_outcome
            row.error_code = error_code
            row.completed_at = now
            await session.flush()
            return _attempt(row)

    async def mark_attempt_failed(self, *, attempt_id: UUID, error_code: str) -> None:
        async with self._sessions.session() as session, session.begin():
            row = await session.get(SpeechAttemptModel, attempt_id, with_for_update=True)
            if row is None or row.outcome is not None:
                return
            row.outcome = SpeechAttemptOutcome.FAILED
            row.error_code = error_code
            row.completed_at = datetime.now(UTC)

    async def mark_segment_fitting(self, segment_id: UUID) -> None:
        await self._set_segment(segment_id, SpeechSegmentStatus.FITTING, None)

    async def mark_segment_needs_review(self, segment_id: UUID, attempt_id: UUID) -> None:
        await self._set_segment(segment_id, SpeechSegmentStatus.NEEDS_REVIEW, attempt_id)

    async def mark_segment_fit(self, segment_id: UUID, attempt_id: UUID) -> None:
        await self._set_segment(segment_id, SpeechSegmentStatus.FIT, attempt_id)

    async def _set_segment(
        self, segment_id: UUID, status: SpeechSegmentStatus, attempt_id: UUID | None
    ) -> None:
        async with self._sessions.session() as session, session.begin():
            row = await session.get(SpeechSegmentStateModel, segment_id, with_for_update=True)
            if row is None:
                raise NotFoundError("Speech segment state not found")
            row.status = status
            if attempt_id is not None:
                row.current_attempt_id = attempt_id
            row.version += 1
            row.updated_at = datetime.now(UTC)

    async def finalize_speech(self, media_asset_id: UUID) -> SpeechStatus:
        async with self._sessions.session() as session, session.begin():
            state = await session.get(SpeechStateModel, media_asset_id, with_for_update=True)
            if state is None:
                raise NotFoundError("Speech not found")
            statuses = (
                await session.scalars(
                    select(SpeechSegmentStateModel.status).where(
                        SpeechSegmentStateModel.media_asset_id == media_asset_id
                    )
                )
            ).all()
            if not statuses:
                state.status = SpeechStatus.FAILED
                state.error_code = "TTS_NO_SEGMENTS"
            elif any(
                SpeechSegmentStatus(value) is SpeechSegmentStatus.FAILED for value in statuses
            ):
                state.status = SpeechStatus.FAILED
                state.error_code = "TTS_SEGMENT_FAILED"
            elif all(SpeechSegmentStatus(value) is SpeechSegmentStatus.FIT for value in statuses):
                state.status = SpeechStatus.APPROVED
                state.error_code = None
            else:
                state.status = SpeechStatus.WAITING_FOR_REVIEW
                state.error_code = None
            state.version += 1
            state.updated_at = datetime.now(UTC)
            return SpeechStatus(state.status)

    async def set_speech_status(
        self, media_asset_id: UUID, status: SpeechStatus, *, error_code: str | None = None
    ) -> None:
        async with self._sessions.session() as session, session.begin():
            state = await session.get(SpeechStateModel, media_asset_id, with_for_update=True)
            if state is None:
                return
            state.status = status
            state.error_code = error_code
            state.version += 1
            state.updated_at = datetime.now(UTC)
