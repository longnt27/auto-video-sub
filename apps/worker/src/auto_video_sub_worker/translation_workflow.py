from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError


@workflow.defn(name="translation-v1")
class TranslationWorkflow:
    def __init__(self) -> None:
        self._context_approved = False
        self._translation_approved = False

    @workflow.signal(name="translation-context-approved-v1")
    def approve_context(self) -> None:
        self._context_approved = True

    @workflow.signal(name="translation-approved-v1")
    def approve_translation(self) -> None:
        self._translation_approved = True

    @workflow.query(name="translation-status-v1")
    def status(self) -> str:
        if self._translation_approved:
            return "approved"
        if self._context_approved:
            return "translating_or_review"
        return "context_or_review"

    @workflow.run
    async def run(self, payload: dict[str, str]) -> dict[str, str]:
        paid_retry = RetryPolicy(
            initial_interval=timedelta(seconds=15),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=2),
            maximum_attempts=2,
        )
        local_retry = RetryPolicy(
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )
        try:
            await workflow.execute_activity(
                "extract-translation-context-v1",
                payload,
                start_to_close_timeout=timedelta(minutes=15),
                heartbeat_timeout=timedelta(minutes=2),
                retry_policy=paid_retry,
            )
            await workflow.wait_condition(lambda: self._context_approved)
            batch_ids = await workflow.execute_activity(
                "plan-translation-batches-v1",
                payload,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=local_retry,
            )
            for batch_id in batch_ids:
                await workflow.execute_activity(
                    "translate-semantic-batch-v1",
                    {**payload, "batch_id": batch_id},
                    start_to_close_timeout=timedelta(minutes=15),
                    heartbeat_timeout=timedelta(minutes=2),
                    retry_policy=paid_retry,
                )
            await workflow.execute_activity(
                "finalize-translation-review-v1",
                payload,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=local_retry,
            )
            await workflow.wait_condition(lambda: self._translation_approved)
            return {
                "status": "approved",
                "media_asset_id": payload["media_asset_id"],
                "policy_version_id": payload["policy_version_id"],
            }
        except ActivityError as error:
            error_code = "TRANSLATION_PROCESSING_EXHAUSTED"
            if isinstance(error.cause, ApplicationError) and error.cause.type:
                error_code = error.cause.type
            await workflow.execute_activity(
                "mark-translation-failed-v1",
                {**payload, "error_code": error_code},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            raise
