from __future__ import annotations

import asyncio
from uuid import UUID

from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError


class TemporalTranslationWorkflowControl:
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
    def workflow_id(media_asset_id: UUID, policy_version_id: UUID) -> str:
        return f"translation-v1/{media_asset_id}/{policy_version_id}"

    async def start_translation(
        self,
        *,
        project_id: UUID,
        media_asset_id: UUID,
        policy_version_id: UUID,
    ) -> str:
        workflow_id = self.workflow_id(media_asset_id, policy_version_id)
        client = await self._get_client()
        payload = {
            "project_id": str(project_id),
            "media_asset_id": str(media_asset_id),
            "policy_version_id": str(policy_version_id),
        }
        try:
            await client.start_workflow(
                "translation-v1",
                payload,
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

    async def approve_translation_context(
        self, *, media_asset_id: UUID, policy_version_id: UUID
    ) -> None:
        client = await self._get_client()
        handle = client.get_workflow_handle(self.workflow_id(media_asset_id, policy_version_id))
        await handle.signal("translation-context-approved-v1")

    async def approve_translation(self, *, media_asset_id: UUID, policy_version_id: UUID) -> None:
        client = await self._get_client()
        handle = client.get_workflow_handle(self.workflow_id(media_asset_id, policy_version_id))
        await handle.signal("translation-approved-v1")

    async def cancel_translation(self, *, media_asset_id: UUID, policy_version_id: UUID) -> None:
        client = await self._get_client()
        handle = client.get_workflow_handle(self.workflow_id(media_asset_id, policy_version_id))
        description = await handle.describe()
        if description.status is WorkflowExecutionStatus.RUNNING:
            await handle.cancel()
