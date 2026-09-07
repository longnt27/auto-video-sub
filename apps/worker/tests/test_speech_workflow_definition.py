from auto_video_sub_worker.speech_workflow import SpeechWorkflow


def test_speech_review_signals_expose_deterministic_status() -> None:
    workflow = SpeechWorkflow()

    assert workflow.status() == "processing_or_review"

    workflow.retry_segment(
        {
            "segment_id": "00000000-0000-0000-0000-000000000001",
            "text": "Ngắn hơn một chút.",
        }
    )
    assert workflow.status() == "repair_requested"

    workflow.approve()
    assert workflow.status() == "approved"
