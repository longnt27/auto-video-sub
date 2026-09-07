import auto_video_sub_providers


def test_provider_package_exports_approved_phase5_adapters() -> None:
    assert auto_video_sub_providers.__all__ == [
        "FFmpegMediaProcessor",
        "FFmpegSpeechAudioProcessor",
        "LlamaCppRewriteProvider",
        "MediaProcessError",
        "OcrProviderError",
        "OpenAIResponsesTranslationProvider",
        "RapidOcrProvider",
        "RewriteProviderError",
        "TranslationProviderError",
        "TtsProviderError",
        "VieNeuTtsProvider",
    ]
