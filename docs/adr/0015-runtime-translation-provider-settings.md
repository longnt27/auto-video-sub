# ADR-0015: Configure translation providers at runtime

- Status: Accepted
- Date: 2026-09-08
- Owners: project maintainers
- Supersedes: the single-provider configuration and local price-snapshot portions of ADR-0006 and ADR-0009

## Context

The original Phase 4 design pinned one cloud translation provider, model, credential, token prices, and a local monetary budget through environment variables. That was useful while proving the first adapter, but it is a poor product surface for the single-owner application: changing model or provider requires deployment configuration, price tables drift independently of vendors, and a locally calculated charge is not provider billing truth.

The application now needs a small explicit provider catalog that the owner can configure from the UI while preserving provider/model lineage for every translation run.

## Decision

Expose a server-owned translation provider catalog in the application. The initial supported providers are OpenAI, DeepSeek, and OpenRouter. Each catalog entry fixes the provider endpoint and offers model-ID suggestions; the owner may type another model ID for that provider, but may not supply an arbitrary base URL.

The owner configures provider, model, and API key from the authenticated application settings UI. Credentials are persisted in an owner-only local runtime file on a dedicated Docker volume, not in PostgreSQL, Git, or `.env`. The API mounts that volume only to manage settings. The translation worker mounts the same volume and is the only process that uses those credentials for cloud LLM requests. Core OCR, TTS, media, and render workers do not mount the provider secret volume.

Each translation policy pins provider, model, prompt version/checksum, tone, and source transcript version as execution lineage. Changing the active provider or model affects subsequent runs only; an existing run resolves the key belonging to its pinned provider and keeps its pinned model.

Pre-run estimation reports token scope only. The application does not maintain a hard-coded provider price table and does not infer monetary cost from token counts. When a provider response includes an exact request cost, that provider-reported value is recorded in the usage ledger. When the response includes token usage but no monetary cost, tokens are recorded and monetary cost is treated as unavailable rather than fabricated. OpenRouter currently exposes request cost in its usage payload; adapters for other providers may expose monetary cost later if their response contracts support it.

The paid-operation confirmation remains explicit, but the former locally calculated `max_cost_micros` reservation is no longer a product control. Provider-side account limits, billing controls, and future provider-native budget APIs are the source of truth for spend caps.

## Consequences

- Provider/model switching no longer requires editing deployment environment variables or restarting around a new credential.
- API keys survive ordinary container restarts through the dedicated local volume and are never returned unmasked to the browser.
- Provider and model are part of translation idempotency; same-tone output from a different provider/model cannot be silently reused.
- The app can display exact monetary cost only where the provider reports it. This is intentionally less complete than a local price table but more truthful.
- Arbitrary compatible endpoints are not supported because allowing user-supplied URLs would expand the worker into a generic outbound-request/SSRF surface.
- A real-provider smoke test remains explicit and opt-in because it incurs external cost.

## Reversibility and review triggers

Adding another provider is bounded to a catalog entry plus an adapter/contract test when its request or usage schema differs. Reconsider secret storage if the deployment becomes multi-user or leaves the single-owner host. Reconsider budget enforcement when a supported provider exposes a reliable native spend-control API or the product requires a centrally enforced monetary ceiling.
