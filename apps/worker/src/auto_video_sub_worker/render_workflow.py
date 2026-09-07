from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError


@workflow.defn(name="render-output-v1")
class RenderWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, str]) -> dict[str, str]:
        render_id = payload["render_id"]
        try:
            await workflow.execute_activity(
                "freeze-render-manifest-v1",
                payload,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            output_object_key = await workflow.execute_activity(
                "render-video-v1",
                payload,
                start_to_close_timeout=timedelta(hours=4),
                heartbeat_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=10),
                    backoff_coefficient=2.0,
                    maximum_interval=timedelta(minutes=2),
                    maximum_attempts=2,
                ),
            )
            await workflow.execute_activity(
                "validate-render-output-v1",
                {**payload, "output_object_key": output_object_key},
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            return {"status": "succeeded", "render_id": render_id}
        except ActivityError as error:
            error_code = "RENDER_PROCESSING_EXHAUSTED"
            if isinstance(error.cause, ApplicationError) and error.cause.type:
                error_code = error.cause.type
            await workflow.execute_activity(
                "mark-render-failed-v1",
                {**payload, "error_code": error_code},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            raise
