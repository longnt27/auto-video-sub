---
name: implement-workflow-stage
description: Design or implement a durable Temporal workflow stage or scoped activity for media, OCR, context, translation, TTS, duration repair, rendering, validation, or cleanup. Use when adding/changing asynchronous processing, retry/resume behavior, human-review gates, progress, or partial invalidation after requirements are approved.
---

# Workflow Stage Implementation

## Non-negotiable rules

Never perform feature work directly on the default branch, use destructive Git commands, overwrite unrelated changes, or make unrelated refactors. Never silently skip tests or fabricate command results. Never introduce a dependency without justification and alternatives. Never implement product behavior before requirements and acceptance criteria are understood.

## Required context

Read `AGENTS.md`, `docs/architecture.md`, `docs/domain-model.md`, `docs/workflow-state-machine.md`, `docs/testing-strategy.md`, `docs/security.md`, `docs/observability.md`, ADR-0003, ADR-0005, and provider/duration/translation docs relevant to the stage. Inspect actual workflow/activity conventions, ports, queues, persistence, artifacts, histories/versioning, tests, task commands, current branch/worktrees, and unrelated changes.

Confirm stage inputs/outputs, scope unit, acceptance criteria, upstream/downstream dependencies, review behavior, cost, and authoritative state before implementation. Never invent commands or results.

## Define the stage contract

Document:

- stable stage/scope identifier and canonical input fingerprint;
- immutable input/output artifact and revision IDs;
- idempotency key, duplicate-claim protection, and uncertain-side-effect reconciliation;
- transient/permanent/review error mapping and bounded retry/backoff;
- schedule/start/heartbeat timeouts and cancellation checkpoints;
- queue/resource/concurrency/provider limits and fan-out window;
- progress units, stage history, cost usage, structured logs/metrics/traces;
- invalidation and smallest partial-restart behavior;
- cleanup of temp, staging, multipart, and abandoned work.

Keep deterministic orchestration separate from side-effecting activities and domain policy. Do not call providers, clocks, random generators, filesystem, or network nondeterministically from workflow code.

## Work safely and implement

Do not implement on the default branch. Use a scoped branch/worktree and preserve unrelated changes. Never use destructive Git commands or unrelated refactors. Do not add dependencies without justified need, alternatives, and compatibility/security/license review. Stop for human review if behavior, retry/cost limits, artifact retention, migration, security, or workflow compatibility is unclear.

Implement the smallest stage through application ports. Assume at-least-once activity execution. Publish to unique staging artifacts, verify, then commit immutable metadata. Heartbeat only resumable state. Respect cancellation at safe boundaries. Version workflow changes so open histories replay.

## Test and self-review

Unit-test domain decisions and error classification. Workflow-test success, each retry class, exhaustion, timeout, worker restart/replay, duplicate delivery, cancellation at critical boundaries, late signals, partial restart, invalidation, and cleanup. Contract/integration-test adapters and durable stores. Replay representative histories before deployment.

Run discovered commands and report exact results; never silently skip tests or call paid providers implicitly. Review the full diff for nondeterminism, infinite retries, broad restart, duplicate side effects, missing lineage/progress/cost, tenant leaks, and unsafe cancellation.

## Completion report

Report: stage contract and scope; state/artifact changes; retry/timeout/idempotency/cancellation; queue/backpressure/cost; files; exact tests/results and skips; replay/rollout/rollback; risks and human-review items.
