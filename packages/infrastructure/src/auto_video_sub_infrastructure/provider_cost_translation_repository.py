from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from auto_video_sub_domain import NotFoundError, new_uuid7

from auto_video_sub_infrastructure.translation_models import (
    TranslationStateModel,
    TranslationUsageModel,
)
from auto_video_sub_infrastructure.translation_repository import SqlAlchemyTranslationRepository


class ProviderReportedCostTranslationRepository(SqlAlchemyTranslationRepository):
    """Compatibility repository that removes local price-table billing decisions.

    Existing translation state/budget columns remain for schema compatibility. New runs reserve
    zero local budget and monetary usage is copied only from a provider response. A zero in the
    legacy aggregate therefore means either no provider-reported charge or no reported currency
    cost; the HTTP contract distinguishes those cases using provider capability metadata.
    """

    def __init__(self, sessions: object) -> None:
        super().__init__(
            sessions,  # type: ignore[arg-type]
            default_translation_budget_micros=0,
            input_cost_micros_per_million_tokens=0,
            output_cost_micros_per_million_tokens=0,
        )

    async def record_usage(
        self,
        *,
        media_asset_id: UUID,
        stage_name: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_micros: int | None,
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
