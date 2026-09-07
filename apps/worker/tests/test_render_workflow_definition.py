from auto_video_sub_worker.render_workflow import RenderWorkflow


def test_render_workflow_is_constructible_for_replay_registration() -> None:
    workflow = RenderWorkflow()

    assert workflow is not None
