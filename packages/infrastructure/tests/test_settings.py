import pytest
from auto_video_sub_infrastructure.settings import Settings
from auto_video_sub_infrastructure.storage_init import _cors_rules
from pydantic import ValidationError


def test_settings_accept_explicit_environment_values(monkeypatch: object) -> None:
    monkeypatch.setenv("PORT", "8010")  # type: ignore[attr-defined]
    monkeypatch.setenv("DEPENDENCY_TIMEOUT_SECONDS", "1.5")  # type: ignore[attr-defined]

    settings = Settings(_env_file=None)

    assert settings.port == 8010
    assert settings.dependency_timeout_seconds == 1.5


def test_tailnet_authentication_rejects_the_committed_development_secret() -> None:
    with pytest.raises(ValidationError, match="distinct 32\\+ character secret"):
        Settings(tailscale_auth_enabled=True, _env_file=None)


def test_core_worker_does_not_require_paid_translation_credentials() -> None:
    settings = Settings(
        worker_profile="core",
        translation_provider_model="",
        translation_provider_api_key="",
        _env_file=None,
    )

    assert settings.worker_profile == "core"


@pytest.mark.parametrize(
    ("model", "api_key"),
    [
        ("", "secret-key"),
        ("configured-model", ""),
    ],
)
def test_translation_worker_fails_closed_without_provider_configuration(
    model: str, api_key: str
) -> None:
    with pytest.raises(ValidationError, match="Translation worker requires"):
        Settings(
            worker_profile="translation",
            translation_provider_model=model,
            translation_provider_api_key=api_key,
            _env_file=None,
        )


def test_storage_cors_uses_one_rule_per_origin_for_garage_compatibility() -> None:
    rules = _cors_rules(("http://127.0.0.1:3100", "http://localhost:3100"))

    assert [rule["AllowedOrigins"] for rule in rules] == [
        ["http://127.0.0.1:3100"],
        ["http://localhost:3100"],
    ]
