"""External provider adapters."""

from auto_video_sub_application.ports import MediaProcessError

from auto_video_sub_providers.media import FFmpegMediaProcessor

__all__ = ["FFmpegMediaProcessor", "MediaProcessError"]
