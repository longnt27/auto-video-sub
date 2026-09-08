import pytest
from auto_video_sub_infrastructure.settings import Settings
from auto_video_sub_infrastructure.storage_init import _cors_rules
from pydantic import ValidationError


def test_settings_accept_explicit_environment_values(monkeypatch: object) -> None:
    monkeypatch.setenv("PORT", "8010")  # type: ignore[attr-defined]
    monkeypatch.setenv("DEPENDENCY_TIMEOUT_SECONDS", "1.5")  # type: ignore[attr-defined]
    monkeypatch.setenv(  # type: ignore[attr-defined]
        "TRANSLATION_PROVIDER_CONFIG_PATH",
        "/tmp/auto-video-sub-provider.json",
    )

    settings = Settings(_env_file=None)

    assert settings.port == 8010
    assert settings.dependency_timeout_seconds == 1.5
    assert settings.translation_provider_config_path == "/tmp/auto-video-sub-provider.json"


def test_tailnet_authentication_rejects_the_committed_development_secret() -> None:
    with pytest.raises(ValidationError, match="distinct 32\\+ character secret"):
        Settings(tailscale_auth_enabled=True, _env_file=None)


def test_core_worker_does_not_require_paid_or_promoted_provider_credentials() -> None:
    settings = Settings(
        worker_profile="core",
        tts_model_revision="",
        tts_voice_id="",
        rewrite_provider_endpoint="",
        _env_file=None,
    )

    assert settings.worker_profile == "core"
    assert settings.tts_model_revision == ""
    assert settings.tts_voice_id == ""


def test_translation_worker_reads_provider_credentials_from_runtime_store() -> None:
    settings = Settings(
        worker_profile="translation",
        translation_provider_config_path="/config/translation-provider.json",
        _env_file=None,
    )

    assert settings.worker_profile == "translation"
    assert settings.translation_provider_config_path == "/config/translation-provider.json"


def test_speech_precision_rejects_unknown_runtime_variant() -> None:
    with pytest.raises(ValidationError, match="TTS_PRECISION"):
        Settings(tts_precision="fp16", _env_file=None)


def test_storage_cors_uses_one_rule_per_origin_for_garage_compatibility() -> None:
    rules = _cors_rules(("http://127.0.0.1:3100", "http://localhost:3100"))

    assert [rule["AllowedOrigins"] for rule in rules] == [
        ["http://127.0.0.1:3100"],
        ["http://localhost:3100"],
    ]
