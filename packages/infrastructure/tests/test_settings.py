from auto_video_sub_infrastructure.settings import Settings


def test_settings_accept_explicit_environment_values(monkeypatch: object) -> None:
    monkeypatch.setenv("PORT", "8010")  # type: ignore[attr-defined]
    monkeypatch.setenv("DEPENDENCY_TIMEOUT_SECONDS", "1.5")  # type: ignore[attr-defined]

    settings = Settings(_env_file=None)

    assert settings.port == 8010
    assert settings.dependency_timeout_seconds == 1.5
