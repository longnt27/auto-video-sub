from __future__ import annotations

import asyncio
from uuid import UUID

from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError


class TemporalWorkflowStarter:
    def __init__(self, *, address: str, namespace: str, task_queue: str) -> None:
        self._address = address
        self._namespace = namespace
        self._task_queue = task_queue
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
