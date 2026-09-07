from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError


@workflow.defn(name="source-transcript-v1")
class SourceTranscriptWorkflow:
    def __init__(self) -> None:
        self._approved = False

    @workflow.signal(name="transcript-approved-v1")
    def approve(self) -> None:
        self._approved = True

    @workflow.query(name="source-transcript-status-v1")
    def status(self) -> str:
        return "approved" if self._approved else "processing_or_review"

    @workflow.run
    async def run(self, payload: dict[str, str]) -> dict[str, str]:
        ocr_retry = RetryPolicy(
            initial_interval=timedelta(seconds=10),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=2),
            maximum_attempts=2,
        )
        consolidation_retry = RetryPolicy(
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=2,
        )
        try:
            await workflow.execute_activity(
                "extract-and-ocr-source-subtitles-v1",
                payload,
                start_to_close_timeout=timedelta(hours=4),
                heartbeat_timeout=timedelta(minutes=2),
                retry_policy=ocr_retry,
            )
            await workflow.execute_activity(
                "consolidate-source-transcript-v1",
                payload,
                start_to_close_timeout=timedelta(minutes=10),
                heartbeat_timeout=timedelta(minutes=2),
                retry_policy=consolidation_retry,
            )
            await workflow.wait_condition(lambda: self._approved)
            return {"status": "approved", "media_asset_id": payload["media_asset_id"]}
        except ActivityError as error:
            error_code = "TRANSCRIPT_PROCESSING_EXHAUSTED"
            if isinstance(error.cause, ApplicationError) and error.cause.type:
                error_code = error.cause.type
            await workflow.execute_activity(
                "mark-source-transcript-failed-v1",
                {**payload, "error_code": error_code},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            raise
