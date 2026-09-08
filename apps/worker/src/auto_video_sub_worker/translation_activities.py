from __future__ import annotations

from uuid import UUID

from auto_video_sub_application import CONTEXT_INSTRUCTIONS, CONTEXT_PROMPT_VERSION, TONE_POLICIES
from auto_video_sub_application.provider_settings import TranslationProviderSettingsStore
from auto_video_sub_application.translation_ports import (
    ContextExtractionRequest,
    TranslationBatchRequest,
    TranslationProvider,
    TranslationWorkflowRepository,
)
from auto_video_sub_domain import TranslationStatus, plan_translation_batches
from auto_video_sub_providers import OpenAIResponsesTranslationProvider
from temporalio import activity
from temporalio.exceptions import ApplicationError


def _application_error(error: Exception) -> ApplicationError:
    code = getattr(error, "code", "TRANSLATION_ACTIVITY_FAILED")
    retryable = bool(getattr(error, "retryable", False))
    return ApplicationError(str(error), type=code, non_retryable=not retryable)


class TranslationActivities:
    def __init__(
        self,
        *,
        repository: TranslationWorkflowRepository,
        provider_settings: TranslationProviderSettingsStore,
        request_timeout_seconds: int,
    ) -> None:
        self._repository = repository
        self._provider_settings = provider_settings
        self._request_timeout_seconds = request_timeout_seconds

    async def _provider(self, *, provider: str, model: str) -> TranslationProvider:
        try:
            credentials = await self._provider_settings.credentials_for(
                provider=provider,
                model=model,
            )
        except Exception as error:
            raise ApplicationError(
                str(error),
                type="TRANSLATION_PROVIDER_UNCONFIGURED",
                non_retryable=True,
            ) from error
        return OpenAIResponsesTranslationProvider(
            api_key=credentials.api_key,
            model=credentials.model,
            base_url=credentials.base_url,
            provider_name=credentials.provider,
            timeout_seconds=self._request_timeout_seconds,
        )

    @activity.defn(name="extract-translation-context-v1")
    async def extract_context(self, payload: dict[str, str]) -> dict[str, str]:
        media_asset_id = UUID(payload["media_asset_id"])
        policy_version_id = UUID(payload["policy_version_id"])
        state = await self._repository.get_record_internal(media_asset_id)
        if state.policy_version_id != policy_version_id:
            raise ApplicationError(
                "Translation policy was superseded",
                type="TRANSLATION_POLICY_SUPERSEDED",
                non_retryable=True,
            )
        if state.status in {
            TranslationStatus.WAITING_FOR_CONTEXT_REVIEW,
            TranslationStatus.TRANSLATING,
            TranslationStatus.WAITING_FOR_REVIEW,
            TranslationStatus.APPROVED,
        }:
            context = await self._repository.get_context_internal(media_asset_id)
            if context is not None:
                return {"context_version_id": str(context.id)}
        if state.status is not TranslationStatus.CONTEXT_PROCESSING:
            raise ApplicationError(
                "Translation context processing is no longer active",
                type="TRANSLATION_NOT_PROCESSING",
                non_retryable=True,
            )
        policy = await self._repository.get_policy_internal(policy_version_id)
        provider = await self._provider(provider=policy.provider, model=policy.model)
        segments = await self._repository.load_source_segments_internal(media_asset_id)
        activity.heartbeat("context-request")
        try:
            result = await provider.extract_context(
                ContextExtractionRequest(
                    project_id=state.project_id,
                    media_asset_id=media_asset_id,
                    transcript_version=state.transcript_version,
                    segments=segments,
                    prompt_version=CONTEXT_PROMPT_VERSION,
                    instructions=CONTEXT_INSTRUCTIONS,
                )
            )
            context = await self._repository.publish_context(
                media_asset_id=media_asset_id,
                result=result,
                provider=policy.provider,
                model=policy.model,
                prompt_version=CONTEXT_PROMPT_VERSION,
            )
            await self._repository.record_usage(
                media_asset_id=media_asset_id,
                stage_name="context",
                provider=policy.provider,
                model=policy.model,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                cost_micros=result.usage.cost_micros,
                provider_request_id=result.provider_request_id,
            )
            return {"context_version_id": str(context.id)}
        except ApplicationError:
            raise
        except Exception as error:
            raise _application_error(error) from error

    @activity.defn(name="plan-translation-batches-v1")
    async def plan_batches(self, payload: dict[str, str]) -> list[str]:
        media_asset_id = UUID(payload["media_asset_id"])
        policy_version_id = UUID(payload["policy_version_id"])
        state = await self._repository.get_record_internal(media_asset_id)
        if state.policy_version_id != policy_version_id:
            raise ApplicationError(
                "Translation policy was superseded",
                type="TRANSLATION_POLICY_SUPERSEDED",
                non_retryable=True,
            )
        if state.status not in {
            TranslationStatus.TRANSLATING,
            TranslationStatus.WAITING_FOR_REVIEW,
            TranslationStatus.APPROVED,
        }:
            raise ApplicationError(
                "Translation context is not approved",
                type="TRANSLATION_CONTEXT_NOT_APPROVED",
                non_retryable=True,
            )
        source = await self._repository.load_source_segments_internal(media_asset_id)
        plans = plan_translation_batches(
            tuple((item.id, item.start_us, item.end_us) for item in source)
        )
        batches = await self._repository.create_batches(media_asset_id=media_asset_id, plans=plans)
        return [str(item.id) for item in batches]

    @activity.defn(name="translate-semantic-batch-v1")
    async def translate_batch(self, payload: dict[str, str]) -> dict[str, int]:
        batch_id = UUID(payload["batch_id"])
        batch = await self._repository.get_batch_internal(batch_id)
        if batch.status == "succeeded":
            return {"translated": len(batch.plan.owned_segment_ids)}
        state = await self._repository.get_record_internal(batch.media_asset_id)
        if state.policy_version_id != batch.policy_version_id:
            raise ApplicationError(
                "Translation batch belongs to a superseded policy",
                type="TRANSLATION_POLICY_SUPERSEDED",
                non_retryable=True,
            )
        policy = await self._repository.get_policy_internal(batch.policy_version_id)
        context = await self._repository.get_context_internal(batch.media_asset_id)
        if context is None or not context.approved:
            raise ApplicationError(
                "Approved translation context is missing",
                type="TRANSLATION_CONTEXT_NOT_APPROVED",
                non_retryable=True,
            )
        definition = TONE_POLICIES[policy.preset]
        if (
            definition.prompt_version != policy.prompt_version
            or definition.checksum != policy.prompt_checksum
        ):
            raise ApplicationError(
                "Pinned translation prompt does not match the current server catalog",
                type="TRANSLATION_PROMPT_VERSION_MISMATCH",
                non_retryable=True,
            )
        provider = await self._provider(provider=policy.provider, model=policy.model)
        all_segments = await self._repository.load_source_segments_internal(batch.media_asset_id)
        by_id = {item.id: item for item in all_segments}
        try:
            owned = tuple(by_id[item] for item in batch.plan.owned_segment_ids)
            overlap = tuple(by_id[item] for item in batch.plan.overlap_segment_ids)
        except KeyError as error:
            raise ApplicationError(
                "Translation batch references a missing source segment",
                type="TRANSLATION_BATCH_SOURCE_MISSING",
                non_retryable=True,
            ) from error
        activity.heartbeat(f"translation-batch:{batch.ordinal}")
        try:
            result = await provider.translate_batch(
                TranslationBatchRequest(
                    batch_id=batch.id,
                    owned_segments=owned,
                    overlap_segments=overlap,
                    context_summary=context.summary,
                    glossary=context.entities,
                    preset=policy.preset,
                    prompt_version=policy.prompt_version,
                    instructions=definition.instructions,
                )
            )
            await self._repository.publish_batch_result(
                batch_id=batch.id,
                result=result,
                provider=policy.provider,
                model=policy.model,
                prompt_version=policy.prompt_version,
            )
            await self._repository.record_usage(
                media_asset_id=batch.media_asset_id,
                stage_name=f"batch:{batch.id}",
                provider=policy.provider,
                model=policy.model,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                cost_micros=result.usage.cost_micros,
                provider_request_id=result.provider_request_id,
            )
            return {"translated": len(result.items)}
        except ApplicationError:
            raise
        except Exception as error:
            raise _application_error(error) from error

    @activity.defn(name="finalize-translation-review-v1")
    async def finalize(self, payload: dict[str, str]) -> dict[str, int]:
        media_asset_id = UUID(payload["media_asset_id"])
        findings = await self._repository.finalize_translation(media_asset_id)
        await self._repository.reconcile_budget(media_asset_id)
        return {"finding_count": len(findings)}

    @activity.defn(name="mark-translation-failed-v1")
    async def mark_failed(self, payload: dict[str, str]) -> None:
        media_asset_id = UUID(payload["media_asset_id"])
        await self._repository.set_translation_status(
            media_asset_id,
            TranslationStatus.FAILED,
            error_code=payload.get("error_code", "TRANSLATION_PROCESSING_EXHAUSTED"),
        )
        await self._repository.reconcile_budget(media_asset_id)
