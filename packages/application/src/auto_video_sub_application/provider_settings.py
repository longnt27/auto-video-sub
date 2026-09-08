from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TranslationProviderDefinition:
    id: str
    label: str
    base_url: str
    suggested_models: tuple[str, ...]
    reports_monetary_cost: bool = False


TRANSLATION_PROVIDER_CATALOG: tuple[TranslationProviderDefinition, ...] = (
    TranslationProviderDefinition(
        id="openai",
        label="OpenAI",
        base_url="https://api.openai.com/v1/responses",
        suggested_models=("gpt-5.6-luna", "gpt-5.6-sol"),
    ),
    TranslationProviderDefinition(
        id="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com/responses",
        suggested_models=("deepseek-v4-flash", "deepseek-v4-pro"),
    ),
    TranslationProviderDefinition(
        id="openrouter",
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1/responses",
        suggested_models=("openai/gpt-5.6-luna", "deepseek/deepseek-v4-flash"),
        reports_monetary_cost=True,
    ),
)


@dataclass(frozen=True, slots=True)
class TranslationProviderSettingsView:
    provider: str
    model: str
    api_key_configured: bool
    api_key_hint: str | None


@dataclass(frozen=True, slots=True)
class TranslationProviderCredentials:
    provider: str
    model: str
    base_url: str
    api_key: str
    reports_monetary_cost: bool


class TranslationProviderSettingsStore(Protocol):
    async def get_active(self) -> TranslationProviderSettingsView | None: ...

    async def configure(
        self,
        *,
        provider: str,
        model: str,
        api_key: str | None,
    ) -> TranslationProviderSettingsView: ...

    async def credentials_for(
        self,
        *,
        provider: str,
        model: str,
    ) -> TranslationProviderCredentials: ...
