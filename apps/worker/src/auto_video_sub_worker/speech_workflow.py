from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError


@workflow.defn(name="speech-fit-v1")
class SpeechWorkflow:
    def __init__(self) -> None:
        self._approved = False
        self._repair_requests: list[dict[str, str]] = []
        self._repair_cycles: dict[str, int] = {}

    @workflow.signal(name="speech-segment-retry-v1")
    def retry_segment(self, payload: dict[str, str]) -> None:
        self._repair_requests.append(payload)

    @workflow.signal(name="speech-approved-v1")
    def approve(self) -> None:
        self._approved = True

    @workflow.query(name="speech-status-v1")
    def status(self) -> str:
        if self._approved:
            return "approved"
        if self._repair_requests:
            return "repair_requested"
        return "processing_or_review"

    async def _fit_segment(
        self,
        payload: dict[str, str],
        *,
        segment_id: str,
        cycle_index: int,
        text: str = "",
    ) -> None:
        activity_payload = {
            **payload,
            "segment_id": segment_id,
            "cycle_index": str(cycle_index),
        }
        if text:
            activity_payload["text"] = text
        await workflow.execute_activity(
            "fit-speech-segment-v1",
            activity_payload,
            start_to_close_timeout=timedelta(minutes=30),
            heartbeat_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=30),
                maximum_attempts=3,
            ),
        )

    @workflow.run
    async def run(self, payload: dict[str, str]) -> dict[str, str]:
        local_retry = RetryPolicy(
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )
        try:
            segment_ids = await workflow.execute_activity(
                "list-speech-segments-v1",
                payload,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=local_retry,
            )
            for segment_id in segment_ids:
                self._repair_cycles[segment_id] = 1
                await self._fit_segment(payload, segment_id=segment_id, cycle_index=0)
            speech_status = await workflow.execute_activity(
                "finalize-speech-review-v1",
                payload,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=local_retry,
            )
            if speech_status == "approved":
                self._approved = True

            while not self._approved:
                await workflow.wait_condition(lambda: self._approved or bool(self._repair_requests))
                while self._repair_requests and not self._approved:
                    request = self._repair_requests.pop(0)
                    segment_id = request["segment_id"]
                    cycle_index = self._repair_cycles.get(segment_id, 1)
                    self._repair_cycles[segment_id] = cycle_index + 1
                    await self._fit_segment(
                        payload,
                        segment_id=segment_id,
                        cycle_index=cycle_index,
                        text=request.get("text", ""),
                    )
                    speech_status = await workflow.execute_activity(
                        "finalize-speech-review-v1",
                        payload,
                        start_to_close_timeout=timedelta(minutes=2),
                        retry_policy=local_retry,
                    )
                    if speech_status == "approved":
                        self._approved = True

            return {
                "status": "approved",
                "media_asset_id": payload["media_asset_id"],
                "speech_version": payload["speech_version"],
            }
        except ActivityError as error:
            error_code = "TTS_PROCESSING_EXHAUSTED"
            if isinstance(error.cause, ApplicationError) and error.cause.type:
                error_code = error.cause.type
            await workflow.execute_activity(
                "mark-speech-failed-v1",
                {**payload, "error_code": error_code},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            raise
