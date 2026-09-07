from __future__ import annotations

import asyncio
from uuid import UUID

from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError


class TemporalRenderWorkflowControl:
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

    @staticmethod
    def workflow_id(render_id: UUID, render_version: int) -> str:
        return f"render-output-v1/{render_id}/{render_version}"

    async def start_render(self, *, render_id: UUID, render_version: int) -> str:
        workflow_id = self.workflow_id(render_id, render_version)
        client = await self._get_client()
        try:
            await client.start_workflow(
                "render-output-v1",
                {"render_id": str(render_id), "render_version": str(render_version)},
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

    async def cancel_render(self, *, workflow_id: str) -> None:
        client = await self._get_client()
        handle = client.get_workflow_handle(workflow_id)
        description = await handle.describe()
        if description.status is WorkflowExecutionStatus.RUNNING:
            await handle.cancel()
