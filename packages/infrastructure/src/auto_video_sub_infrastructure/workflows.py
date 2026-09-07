from __future__ import annotations

import asyncio
from uuid import UUID

from auto_video_sub_domain import SubtitleRegion
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError


class TemporalWorkflowStarter:
    def __init__(
        self,
        *,
        address: str,
        namespace: str,
        task_queue: str,
        transcript_task_queue: str | None = None,
    ) -> None:
        self._address = address
        self._namespace = namespace
        self._task_queue = task_queue
        self._transcript_task_queue = transcript_task_queue or task_queue
        self._client: Client | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> Client:
        async with self._client_lock:
            if self._client is None:
                self._client = await Client.connect(self._address, namespace=self._namespace)
            return self._client

    async def start_media_ingest(self, *, project_id: UUID, media_asset_id: UUID) -> str:
        workflow_id = f"media-ingest-v1/{media_asset_id}"
        client = await self._get_client()
        try:
            await client.start_workflow(
                "media-ingest-v1",
                {"project_id": str(project_id), "media_asset_id": str(media_asset_id)},
                id=workflow_id,
                task_queue=self._task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            )
        except WorkflowAlreadyStartedError:
            handle = client.get_workflow_handle(workflow_id)
            description = await handle.describe()
            if description.status not in {
                WorkflowExecutionStatus.RUNNING,
                WorkflowExecutionStatus.COMPLETED,
            }:
                raise
        return workflow_id

    async def start_source_transcript(
        self, *, project_id: UUID, media_asset_id: UUID, region: SubtitleRegion
    ) -> str:
        region.validate()
        workflow_id = f"source-transcript-v1/{media_asset_id}"
        client = await self._get_client()
        payload = {
            "project_id": str(project_id),
            "media_asset_id": str(media_asset_id),
            "x_start_ratio": str(region.x_start_ratio),
            "x_end_ratio": str(region.x_end_ratio),
            "y_start_ratio": str(region.y_start_ratio),
            "y_end_ratio": str(region.y_end_ratio),
            "sample_interval_ms": str(region.sample_interval_ms),
        }
        try:
            await client.start_workflow(
                "source-transcript-v1",
                payload,
                id=workflow_id,
                task_queue=self._transcript_task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            )
        except WorkflowAlreadyStartedError:
            handle = client.get_workflow_handle(workflow_id)
            description = await handle.describe()
            if description.status not in {
                WorkflowExecutionStatus.RUNNING,
                WorkflowExecutionStatus.COMPLETED,
            }:
                raise
        return workflow_id

    async def approve_source_transcript(self, *, media_asset_id: UUID) -> None:
        client = await self._get_client()
        handle = client.get_workflow_handle(f"source-transcript-v1/{media_asset_id}")
        await handle.signal("transcript-approved-v1")

    async def cancel_source_transcript(self, *, media_asset_id: UUID) -> None:
        client = await self._get_client()
        handle = client.get_workflow_handle(f"source-transcript-v1/{media_asset_id}")
        description = await handle.describe()
        if description.status is WorkflowExecutionStatus.RUNNING:
            await handle.cancel()
