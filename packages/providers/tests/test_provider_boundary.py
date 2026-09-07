import auto_video_sub_providers


def test_provider_package_exports_approved_adapters() -> None:
    assert auto_video_sub_providers.__all__ == [
        "FFmpegMediaProcessor",
        "FFmpegRenderProcessor",
        "FFmpegSpeechAudioProcessor",
        "LlamaCppRewriteProvider",
        "MediaProcessError",
        "OcrProviderError",
        "OpenAIResponsesTranslationProvider",
        "RapidOcrProvider",
        "RenderProcessError",
        "RewriteProviderError",
        "TranslationProviderError",
        "TtsProviderError",
        "VieNeuTtsProvider",
    ]
