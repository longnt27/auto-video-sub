# Architecture Decision Records

ADRs record significant choices that affect boundaries, persistent data, public contracts, workflow semantics, security, deployment, or costly vendor commitments.

## Status

The initial architecture was approved for implementation by the owner on 2026-08-04. Valid statuses are `Proposed`, `Accepted`, `Rejected`, `Deprecated`, and `Superseded by ADR-NNNN`.

## Index

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-modular-monorepo-and-monolith.md) | Modular monorepo and modular monolith | Accepted |
| [0002](0002-python-api-workers-and-typescript-web.md) | Python API/workers and TypeScript web | Accepted |
| [0003](0003-temporal-durable-workflows.md) | Temporal for durable workflows | Accepted |
| [0004](0004-postgresql-and-s3-artifact-storage.md) | PostgreSQL plus S3-compatible artifacts | Accepted |
| [0005](0005-stable-segment-ids-and-immutable-artifacts.md) | Stable segment IDs and immutable versions | Accepted |
| [0006](0006-provider-ports-and-versioned-ai-contracts.md) | Provider ports and versioned AI contracts | Accepted |
| [0007](0007-proxy-editor-with-html-overlays.md) | Proxy editor with HTML overlays | Accepted |
| [0008](0008-single-host-tailscale-deployment.md) | Single-host deployment through Tailscale | Accepted |
| [0009](0009-paid-translation-only.md) | Paid translation LLM as the only paid runtime provider | Accepted |
| [0010](0010-local-vietnamese-tts.md) | VieNeu-TTS for local Vietnamese synthesis | Accepted |
| [0011](0011-versioned-translation-tone-presets.md) | Versioned project-wide translation tone presets | Accepted |
| [0012](0012-structured-subtitle-styles.md) | Structured subtitle styles with pinned fonts | Accepted |
| [0013](0013-same-origin-tailnet-identity-gateway.md) | Same-origin web gateway for tailnet identity | Accepted |
| [0014](0014-github-actions-and-ghcr-delivery.md) | GitHub Actions CI and GHCR continuous delivery | Accepted |

## Template

```markdown
# ADR-NNNN: Decision title

- Status: Proposed
- Date: YYYY-MM-DD
- Owners: project maintainers

## Context

## Decision

## Consequences

## Alternatives considered

## Reversibility and review triggers
```

Create a new ADR rather than rewriting the rationale of an accepted decision. Small clarifications may be appended with date and reason. Link superseding records in both directions.
