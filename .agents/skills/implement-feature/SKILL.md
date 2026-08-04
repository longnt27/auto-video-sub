---
name: implement-feature
description: Implement an approved, scoped product feature in this repository after requirements and acceptance criteria are known. Use for user-visible behavior or coherent backend capabilities spanning web, API, domain, workflow, workers, or adapters; do not use during the architecture-only approval gate or for ambiguous requests that need product decisions first.
---

# Feature Implementation

## Non-negotiable rules

Never perform feature work directly on the default branch, use destructive Git commands, overwrite unrelated changes, or make unrelated refactors. Never silently skip tests or fabricate command results. Never introduce a dependency without justification and alternatives. Never implement product behavior before requirements and acceptance criteria are understood.

## Prepare

1. Read `AGENTS.md`, `README.md`, `docs/product-overview.md`, `docs/architecture.md`, `docs/repository-structure.md`, and documents/ADRs governing the feature.
2. Inspect repository status, branch/worktrees, existing changes, module boundaries, nearby implementations, public contracts, migrations, tests, and CI/task-runner files.
3. Confirm the architecture gate permits implementation. Confirm observable requirements, acceptance criteria, exclusions, authorization, error behavior, idempotency, cancellation, telemetry, and rollout needs.
4. Discover commands from actual checked-in files. Never invent a setup/test command or fabricate its output.

## Plan

Write a concise implementation plan covering domain/application changes, transport and persistence adapters, workflow impact, immutable artifacts/versions, UI states, tests, migration/compatibility, and rollback. Identify human-review points before coding. If a significant decision lacks an accepted ADR, stop and obtain review.

## Work safely

Never perform feature work on the default branch. Create or use a scoped branch/worktree only after preserving existing work. Never use destructive Git commands, overwrite unrelated changes, or perform unrelated refactors. Do not add dependencies unless the need, alternatives, maintenance/security/license cost, and architecture fit are documented; obtain approval when the choice is material.

## Implement

Follow dependency direction: domain rules first, application use case/ports next, adapters/transports next, composition last. Keep provider SDK and framework types out of domain code. Preserve stable segment IDs, backend-owned timing, immutable artifacts/revisions, tenant scoping, bounded retries, and structured errors.

Implement the smallest coherent vertical behavior. Add authorization and validation at the boundary and enforce invariants inside the application/domain. Add telemetry without leaking content/secrets. Update contracts and docs in the same change.

## Test and self-review

Add focused domain tests and the relevant persistence, storage, workflow, provider-contract, media, API, browser, or security tests from `docs/testing-strategy.md`. Run the smallest checks while iterating and every repository-defined required check before completion. Never silently skip tests; report unavailable, skipped, flaky, or failed checks and why. Paid real-provider tests require explicit opt-in and budget authorization.

Review requirements one by one, then inspect the complete diff for tenant leaks, retry duplication, stale derived data, missing cancellation/cleanup, unsafe file handling, compatibility, secrets, unrelated changes, and undocumented behavior. Confirm rollback is possible.

## Completion report

Report: implemented outcome; acceptance criteria; files/modules changed; exact test commands/results; skipped checks; data/workflow/provider implications; security/observability; rollout/rollback; risks/follow-ups; human review still required.
