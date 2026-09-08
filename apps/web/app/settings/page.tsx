"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";

type ProviderOption = {
  id: string;
  label: string;
  suggested_models: string[];
  reports_monetary_cost: boolean;
};

type ProviderSettings = {
  providers: ProviderOption[];
  active: {
    provider: string;
    model: string;
    api_key_configured: boolean;
    api_key_hint: string | null;
  } | null;
};

const API = "/api/backend/v1";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { cache: "no-store", ...init });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? "Request failed");
  return payload as T;
}

export default function ProviderSettingsPage() {
  const [settings, setSettings] = useState<ProviderSettings | null>(null);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Loading provider settings…");

  const selected = useMemo(
    () => settings?.providers.find((item) => item.id === provider) ?? null,
    [provider, settings],
  );

  useEffect(() => {
    void api<ProviderSettings>("/translation/provider-settings")
      .then((next) => {
        setSettings(next);
        const initialProvider = next.active?.provider ?? next.providers[0]?.id ?? "";
        const option = next.providers.find((item) => item.id === initialProvider);
        setProvider(initialProvider);
        setModel(next.active?.model ?? option?.suggested_models[0] ?? "");
        setMessage(
          next.active
            ? `Active: ${next.active.provider} / ${next.active.model}`
            : "Choose a provider, model, and API key.",
        );
      })
      .catch((error) =>
        setMessage(error instanceof Error ? error.message : "Could not load provider settings"),
      );
  }, []);

  function selectProvider(nextProvider: string) {
    setProvider(nextProvider);
    const option = settings?.providers.find((item) => item.id === nextProvider);
    const isCurrent = settings?.active?.provider === nextProvider;
    setModel(isCurrent ? settings.active?.model ?? "" : option?.suggested_models[0] ?? "");
    setApiKey("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!provider || !model.trim()) return;
    setBusy(true);
    try {
      const next = await api<ProviderSettings>("/translation/provider-settings", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          provider,
          model: model.trim(),
          api_key: apiKey.trim() || null,
        }),
      });
      setSettings(next);
      setApiKey("");
      setMessage(`Saved. ${next.active?.provider} / ${next.active?.model} is now active.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save provider settings");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <header className="masthead">
        <div>
          <p className="eyebrow">Runtime configuration</p>
          <h1>AI provider</h1>
        </div>
        <p className="status-line">{message}</p>
      </header>

      <section className="panel controls" style={{ maxWidth: "52rem" }}>
        <div>
          <h2>Translation provider</h2>
          <p className="control-copy">
            This setting controls paid Chinese → Vietnamese context extraction and translation.
            OCR, TTS, rendering, and local rewriting stay local.
          </p>

          <form onSubmit={save}>
            <label htmlFor="provider">Provider</label>
            <select
              id="provider"
              value={provider}
              onChange={(event) => selectProvider(event.target.value)}
              disabled={busy}
            >
              {settings?.providers.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>

            <label htmlFor="model">Model</label>
            <input
              id="model"
              list="provider-models"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder="Provider model ID"
              disabled={busy}
            />
            <datalist id="provider-models">
              {selected?.suggested_models.map((item) => <option key={item} value={item} />)}
            </datalist>
            <p className="control-copy">
              Suggested models are shortcuts only. You can type another valid model ID supported by
              the selected provider.
            </p>

            <label htmlFor="api-key">API key</label>
            <input
              id="api-key"
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={
                settings?.active?.provider === provider && settings.active.api_key_configured
                  ? `Keep existing ${settings.active.api_key_hint ?? "saved key"}`
                  : "Paste provider API key"
              }
              autoComplete="off"
              disabled={busy}
            />
            <p className="control-copy">
              Leaving this empty keeps the saved key for this provider. The API never returns the
              full key to the browser.
            </p>

            <button type="submit" disabled={busy || !provider || !model.trim()}>
              {busy ? "Saving…" : "Save and use provider"}
            </button>
          </form>
        </div>

        <div>
          <h3>Cost reporting</h3>
          <p className="control-copy">
            {selected?.reports_monetary_cost
              ? "This provider reports request cost in its API usage payload, so the app records that provider-reported amount."
              : "This provider reports token usage but not an exact monetary charge per response. The app records tokens and shows monetary cost as unavailable instead of calculating it from a hard-coded price table."}
          </p>
        </div>
      </section>
    </main>
  );
}
