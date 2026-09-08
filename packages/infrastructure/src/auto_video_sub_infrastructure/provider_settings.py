from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from auto_video_sub_application.provider_settings import (
    TRANSLATION_PROVIDER_CATALOG,
    TranslationProviderCredentials,
    TranslationProviderSettingsView,
)


class LocalTranslationProviderSettingsStore:
    """Small local secret store for the single-owner deployment.

    Provider credentials intentionally live outside PostgreSQL so database/media backups do
    not automatically contain API keys. The file is written atomically with owner-only mode.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = asyncio.Lock()

    @staticmethod
    def _definitions() -> dict[str, Any]:
        return {item.id: item for item in TRANSLATION_PROVIDER_CATALOG}

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"active_provider": None, "providers": {}}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError("Translation provider settings file is unreadable") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("providers", {}), dict):
            raise RuntimeError("Translation provider settings file is invalid")
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        temp_path.write_text(encoded, encoding="utf-8")
        os.chmod(temp_path, 0o600)
        temp_path.replace(self._path)
        os.chmod(self._path, 0o600)

    @staticmethod
    def _view(provider: str, entry: dict[str, Any]) -> TranslationProviderSettingsView:
        key = str(entry.get("api_key", ""))
        return TranslationProviderSettingsView(
            provider=provider,
            model=str(entry.get("model", "")),
            api_key_configured=bool(key),
            api_key_hint=(f"••••{key[-4:]}" if len(key) >= 4 else ("••••" if key else None)),
        )

    async def get_active(self) -> TranslationProviderSettingsView | None:
        async with self._lock:
            payload = self._read()
            provider = payload.get("active_provider")
            if not isinstance(provider, str):
                return None
            entry = payload.get("providers", {}).get(provider)
            if not isinstance(entry, dict):
                return None
            return self._view(provider, entry)

    async def configure(
        self,
        *,
        provider: str,
        model: str,
        api_key: str | None,
    ) -> TranslationProviderSettingsView:
        definitions = self._definitions()
        selected_provider = provider.strip().casefold()
        if selected_provider not in definitions:
            raise ValueError("Unsupported translation provider")
        selected_model = model.strip()
        if not selected_model or len(selected_model) > 160:
            raise ValueError("Translation model is required")
        async with self._lock:
            payload = self._read()
            providers = payload.setdefault("providers", {})
            existing = providers.get(selected_provider)
            current_key = str(existing.get("api_key", "")) if isinstance(existing, dict) else ""
            replacement = api_key.strip() if api_key is not None else current_key
            if not replacement:
                raise ValueError("Translation provider API key is required")
            if len(replacement) > 4096:
                raise ValueError("Translation provider API key is invalid")
            entry = {"model": selected_model, "api_key": replacement}
            providers[selected_provider] = entry
            payload["active_provider"] = selected_provider
            self._write(payload)
            return self._view(selected_provider, entry)

    async def credentials_for(
        self,
        *,
        provider: str,
        model: str,
    ) -> TranslationProviderCredentials:
        definitions = self._definitions()
        selected_provider = provider.strip().casefold()
        definition = definitions.get(selected_provider)
        if definition is None:
            raise RuntimeError("Translation policy references an unsupported provider")
        async with self._lock:
            payload = self._read()
            entry = payload.get("providers", {}).get(selected_provider)
            if not isinstance(entry, dict) or not str(entry.get("api_key", "")).strip():
                raise RuntimeError(
                    f"No API key is configured for translation provider {selected_provider}"
                )
            return TranslationProviderCredentials(
                provider=selected_provider,
                model=model.strip(),
                base_url=definition.base_url,
                api_key=str(entry["api_key"]).strip(),
                reports_monetary_cost=definition.reports_monetary_cost,
            )
