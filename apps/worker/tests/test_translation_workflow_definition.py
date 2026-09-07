from auto_video_sub_worker.translation_workflow import TranslationWorkflow


def test_translation_review_signals_expose_deterministic_status() -> None:
    workflow = TranslationWorkflow()

    assert workflow.status() == "context_or_review"

    workflow.approve_context()
    assert workflow.status() == "translating_or_review"

    workflow.approve_translation()
    assert workflow.status() == "approved"
