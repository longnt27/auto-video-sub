import auto_video_sub_providers


def test_provider_package_exports_approved_phase4_adapters() -> None:
    assert auto_video_sub_providers.__all__ == [
        "FFmpegMediaProcessor",
        "MediaProcessError",
        "OcrProviderError",
        "OpenAIResponsesTranslationProvider",
        "RapidOcrProvider",
        "TranslationProviderError",
    ]
