from __future__ import annotations

import asyncio
from uuid import UUID

from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError


class TemporalSpeechWorkflowControl:
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
    def workflow_id(media_asset_id: UUID, speech_version: int) -> str:
        return f"speech-fit-v1/{media_asset_id}/{speech_version}"

    async def start_speech(
        self, *, project_id: UUID, media_asset_id: UUID, speech_version: int
    ) -> str:
        workflow_id = self.workflow_id(media_asset_id, speech_version)
        client = await self._get_client()
        payload = {
            "project_id": str(project_id),
            "media_asset_id": str(media_asset_id),
            "speech_version": str(speech_version),
        }
        try:
            await client.start_workflow(
                "speech-fit-v1",
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

    async def approve_speech(self, *, media_asset_id: UUID, speech_version: int) -> None:
        client = await self._get_client()
        handle = client.get_workflow_handle(self.workflow_id(media_asset_id, speech_version))
        await handle.signal("speech-approved-v1")

    async def cancel_speech(self, *, media_asset_id: UUID, speech_version: int) -> None:
        client = await self._get_client()
        handle = client.get_workflow_handle(self.workflow_id(media_asset_id, speech_version))
        description = await handle.describe()
        if description.status is WorkflowExecutionStatus.RUNNING:
            await handle.cancel()
