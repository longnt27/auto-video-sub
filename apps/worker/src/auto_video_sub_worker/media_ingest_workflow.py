from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError


@workflow.defn(name="media-ingest-v1")
class MediaIngestWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, str]) -> dict[str, str]:
        validation_retry = RetryPolicy(
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=1),
            maximum_attempts=3,
        )
        proxy_retry = RetryPolicy(
            initial_interval=timedelta(seconds=10),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=2),
            maximum_attempts=2,
        )
        try:
            await workflow.execute_activity(
                "validate-original-media-v1",
                payload,
                start_to_close_timeout=timedelta(minutes=30),
                heartbeat_timeout=timedelta(minutes=15),
                retry_policy=validation_retry,
            )
            result = await workflow.execute_activity(
                "generate-proxy-media-v1",
                payload,
                start_to_close_timeout=timedelta(hours=3),
                heartbeat_timeout=timedelta(minutes=15),
                retry_policy=proxy_retry,
            )
            if not isinstance(result, dict):
                raise ApplicationError(
                    "Proxy activity returned an invalid result",
                    type="INTERNAL_INVARIANT",
                    non_retryable=True,
                )
            return {str(key): str(value) for key, value in result.items()}
        except ActivityError as error:
            error_code = "MEDIA_INGEST_EXHAUSTED"
            if isinstance(error.cause, ApplicationError) and error.cause.type:
                error_code = error.cause.type
            await workflow.execute_activity(
                "mark-media-ingest-failed-v1",
                {**payload, "error_code": error_code},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            raise
