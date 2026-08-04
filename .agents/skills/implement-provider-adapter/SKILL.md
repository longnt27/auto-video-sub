---
name: implement-provider-adapter
description: Implement or change a replaceable adapter for OCR, cloud LLM, local rewrite LLM, TTS, object storage, FFmpeg/media, authentication, or another external provider. Use for SDK/API mapping, provider configuration, error normalization, usage/cost capture, or contract tests after the capability contract and provider choice are approved.
---

# Provider Adapter Implementation

## Non-negotiable rules

Never perform feature work directly on the default branch, use destructive Git commands, overwrite unrelated changes, or make unrelated refactors. Never silently skip tests or fabricate command results. Never introduce a dependency without justification and alternatives. Never implement product behavior before requirements and acceptance criteria are understood.

## Prepare

Read `AGENTS.md`, `docs/architecture.md`, `docs/domain-model.md`, `docs/testing-strategy.md`, `docs/security.md`, `docs/observability.md`, ADR-0006, and the relevant translation/duration/deployment documents. Inspect the actual application port, existing adapters/fakes, provider SDK/API docs and pinned version, configuration, secret handling, contracts, tests, branch/worktrees, and uncommitted changes.

Confirm capability requirements, acceptance criteria, data sent/received, provider retention/region, model/voice/version pinning, rate/concurrency limits, timeout, idempotency support, pricing units, and failure semantics. Commands come only from repository files. Never fabricate docs, behavior, calls, or results.

## Plan the boundary

Keep provider SDK types and exceptions inside the adapter. Map to versioned application request/results and a structured error taxonomy. Define validation for malformed, missing, duplicate, unknown, truncated, empty, unsafe, or inconsistent output as applicable. Capture provider request ID, resolved model/version, prompt/policy version, usage, latency, finish reason, and estimated cost without logging secrets/content.

Use one real adapter and deterministic fake first; do not build speculative provider switching. A dependency requires concrete justification, alternatives (including direct HTTP where appropriate), maintenance/security/license/size/platform review, and approval for material impact.

## Work safely and implement

Never implement on the default branch. Use a scoped branch/worktree and preserve unrelated changes. Never use destructive Git commands, overwrite changes, or refactor unrelated code. Do not implement product behavior until requirements and acceptance criteria are understood.

Use bounded connect/response timeouts, provider-specific retry hints, application concurrency/rate limits, and idempotency/reconciliation. Validate provider output before domain persistence. Keep backend IDs/timestamps authoritative. Store secrets only through approved runtime configuration; redact tokens, signed URLs, and content from logs.

Require human review for new data processors/regions, unbounded spend, unclear provider terms, behavior-affecting model/prompt changes, weak output validation, unsupported arm64/amd64, or a public-contract change.

## Test and self-review

Implement shared contract tests against the fake and adapter mapping tests for success, throttling, timeout, auth failure, malformed/truncated output, duplicate/unknown IDs where relevant, invalid audio/media, and usage/error normalization. Real-provider smoke tests are optional, explicitly enabled, budget-capped, and never default CI.

Run discovered checks and report exact results/skips. Self-review the full diff for SDK leakage, retry multiplication with Temporal, secret/content logging, missing version/cost metadata, platform packaging, unsafe shell/file use, unrelated changes, and docs/config drift.

## Completion report

Report: capability/provider and rationale; port/adapter mapping; data/privacy/secret handling; retries/timeouts/rate/cost; files/dependency justification; exact test results and opt-in smoke status; rollout/fallback; risks and human review.
