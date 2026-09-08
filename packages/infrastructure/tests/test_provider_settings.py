from __future__ import annotations

import stat

import pytest
from auto_video_sub_infrastructure.provider_settings import LocalTranslationProviderSettingsStore


@pytest.mark.asyncio
async def test_provider_settings_masks_key_and_writes_owner_only_file(tmp_path: object) -> None:
    path = tmp_path / "translation-provider.json"  # type: ignore[operator]
    store = LocalTranslationProviderSettingsStore(path)

    view = await store.configure(
        provider="openai",
        model="gpt-5.6-luna",
        api_key="sk-secret-1234",
    )

    assert view.provider == "openai"
    assert view.model == "gpt-5.6-luna"
    assert view.api_key_configured is True
    assert view.api_key_hint == "••••1234"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "sk-secret-1234" not in repr(view)


@pytest.mark.asyncio
async def test_provider_settings_keep_existing_key_when_only_model_changes(tmp_path: object) -> None:
    path = tmp_path / "translation-provider.json"  # type: ignore[operator]
    store = LocalTranslationProviderSettingsStore(path)
    await store.configure(
        provider="openai",
        model="gpt-5.6-luna",
        api_key="sk-openai-1234",
    )

    await store.configure(
        provider="openai",
        model="gpt-5.6-sol",
        api_key=None,
    )
    credentials = await store.credentials_for(provider="openai", model="gpt-5.6-sol")

    assert credentials.api_key == "sk-openai-1234"
    assert credentials.model == "gpt-5.6-sol"


@pytest.mark.asyncio
async def test_credentials_for_pinned_policy_use_requested_model_and_provider_key(
    tmp_path: object,
) -> None:
    path = tmp_path / "translation-provider.json"  # type: ignore[operator]
    store = LocalTranslationProviderSettingsStore(path)
    await store.configure(
        provider="openai",
        model="gpt-5.6-luna",
        api_key="sk-openai-1234",
    )
    await store.configure(
        provider="deepseek",
        model="deepseek-v4-flash",
        api_key="sk-deepseek-5678",
    )

    old_openai_policy = await store.credentials_for(
        provider="openai",
        model="gpt-5.6-luna",
    )
    active = await store.get_active()

    assert old_openai_policy.api_key == "sk-openai-1234"
    assert old_openai_policy.model == "gpt-5.6-luna"
    assert active is not None
    assert active.provider == "deepseek"


@pytest.mark.asyncio
async def test_provider_settings_reject_unknown_provider(tmp_path: object) -> None:
    path = tmp_path / "translation-provider.json"  # type: ignore[operator]
    store = LocalTranslationProviderSettingsStore(path)

    with pytest.raises(ValueError, match="Unsupported translation provider"):
        await store.configure(
            provider="https://attacker.invalid",
            model="anything",
            api_key="secret",
        )
