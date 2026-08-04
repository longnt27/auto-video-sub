from auto_video_sub_worker.media_ingest_workflow import MediaIngestWorkflow
from temporalio import workflow
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner


async def test_media_ingest_workflow_is_temporal_sandbox_safe() -> None:
    definition = workflow._Definition.must_from_class(MediaIngestWorkflow)
    SandboxedWorkflowRunner().prepare_workflow(definition)
