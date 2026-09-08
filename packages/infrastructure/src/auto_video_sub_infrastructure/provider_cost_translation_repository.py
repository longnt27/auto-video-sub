from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from auto_video_sub_application.translation_ports import TranslationRecord
from auto_video_sub_domain import (
    ConflictError,
    NotFoundError,
    TonePreset,
    TranscriptStatus,
    TranslationStatus,
    new_uuid7,
)
from sqlalchemy import func, select

from auto_video_sub_infrastructure.models import ProjectModel, TranscriptStateModel
from auto_video_sub_infrastructure.translation_models import (
    TranslationPolicyVersionModel,
    TranslationStateModel,
    TranslationUsageModel,
)
from auto_video_sub_infrastructure.translation_repository import (
    SqlAlchemyTranslationRepository,
    _record,
)


class ProviderReportedCostTranslationRepository(SqlAlchemyTranslationRepository):
    """Translation persistence without a local provider price table.

    The legacy budget columns remain for schema compatibility, but new runs reserve no guessed
    monetary amount. Provider/model/prompt are part of policy identity, and monetary usage is
    recorded only when the provider returns an exact request cost.
    """

    def __init__(self, sessions: object) -> None:
        super().__init__(
            sessions,  # type: ignore[arg-type]
            default_translation_budget_micros=0,
            input_cost_micros_per_million_tokens=0,
            output_cost_micros_per_million_tokens=0,
        )

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
        if estimated_cost_micros != 0 or max_cost_micros != 0:
            raise ConflictError("Provider-reported billing does not accept a guessed local budget")

        async with self._sessions.session() as session, session.begin():
            project = await session.scalar(
                select(ProjectModel).where(
                    ProjectModel.id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
            )
            if project is None:
                raise NotFoundError("Project not found")

            transcript = await session.get(
                TranscriptStateModel,
                media_asset_id,
                with_for_update=True,
            )
            if transcript is None or transcript.project_id != project_id:
                raise NotFoundError("Source transcript not found")
            if TranscriptStatus(transcript.status) is not TranscriptStatus.APPROVED:
                raise ConflictError("Source transcript must be approved before translation")

            state = await session.get(TranslationStateModel, media_asset_id, with_for_update=True)
            if state is not None:
                current_policy = await session.get(
                    TranslationPolicyVersionModel,
                    state.policy_version_id,
                )
                if current_policy is None:
                    raise RuntimeError("Translation policy is missing")
                current_status = TranslationStatus(state.status)
                same_policy = (
                    current_policy.preset == preset.value
                    and current_policy.provider == provider
                    and current_policy.model == model
                    and current_policy.prompt_version == prompt_version
                    and current_policy.prompt_checksum == prompt_checksum
                )
                if same_policy and current_status not in {
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
                        "Cancel or finish the current translation before changing "
                        "provider, model, or tone"
                    )

            now = datetime.now(UTC)
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
                    estimated_cost_micros=0,
                    reserved_cost_micros=0,
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
                state.estimated_cost_micros = 0
                state.reserved_cost_micros = 0
                state.actual_cost_micros = 0
                state.findings = {"items": []}
                state.version += 1
                state.updated_at = now

            return _record(state)

    async def record_usage(
        self,
        *,
        media_asset_id: UUID,
        stage_name: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_micros: int | None = None,
        provider_request_id: str | None,
    ) -> None:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Provider token usage cannot be negative")
        if cost_micros is not None and cost_micros < 0:
            raise ValueError("Provider monetary cost cannot be negative")
        persisted_cost = cost_micros or 0
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
                    cost_micros=persisted_cost,
                    provider_request_id=provider_request_id,
                    created_at=datetime.now(UTC),
                )
            )
            if cost_micros is not None:
                state.actual_cost_micros += cost_micros
            state.updated_at = datetime.now(UTC)
