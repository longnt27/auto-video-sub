import pytest
from auto_video_sub_application.speech_ports import TtsProviderError, TtsRequest
from auto_video_sub_providers import VieNeuTtsProvider


@pytest.mark.asyncio
async def test_vieneu_adapter_fails_closed_without_local_model_snapshot() -> None:
    provider = VieNeuTtsProvider(
        model_root="",
        model_revision="reviewed-revision",
        voice_id="approved-voice",
    )

    with pytest.raises(TtsProviderError) as error:
        await provider.synthesize(
            TtsRequest(
                segment_id=__import__("uuid").uuid4(),
                text="Xin chào.",
                voice_id="approved-voice",
            )
        )

    assert error.value.code == "TTS_MODEL_UNCONFIGURED"
    assert error.value.retryable is False
