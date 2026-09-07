"""External provider adapters."""

from auto_video_sub_application.ports import MediaProcessError, OcrProviderError
from auto_video_sub_application.speech_ports import RewriteProviderError, TtsProviderError
from auto_video_sub_application.translation_ports import TranslationProviderError

from auto_video_sub_providers.media import FFmpegMediaProcessor
from auto_video_sub_providers.ocr import RapidOcrProvider
from auto_video_sub_providers.render import FFmpegRenderProcessor, RenderProcessError
from auto_video_sub_providers.rewrite import LlamaCppRewriteProvider
from auto_video_sub_providers.speech_audio import FFmpegSpeechAudioProcessor
from auto_video_sub_providers.translation import OpenAIResponsesTranslationProvider
from auto_video_sub_providers.tts import VieNeuTtsProvider

__all__ = [
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
