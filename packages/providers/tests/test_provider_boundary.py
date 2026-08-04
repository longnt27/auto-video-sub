import auto_video_sub_providers


def test_provider_package_exports_only_the_approved_phase2_media_adapter() -> None:
    assert auto_video_sub_providers.__all__ == ["FFmpegMediaProcessor", "MediaProcessError"]
