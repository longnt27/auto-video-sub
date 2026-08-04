import auto_video_sub_providers


def test_provider_package_has_no_eager_sdk_exports() -> None:
    assert auto_video_sub_providers.__all__ == []
