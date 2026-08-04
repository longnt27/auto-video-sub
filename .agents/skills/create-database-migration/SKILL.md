---
name: create-database-migration
description: Design, implement, and verify a safe PostgreSQL/Alembic schema or data migration for this repository. Use for tables, columns, constraints, indexes, backfills, retention changes, or persistence-contract changes after the data model and rollout are approved; do not create migrations during the architecture-only approval gate.
---

# Database Migration

## Non-negotiable rules

Never perform feature work directly on the default branch, use destructive Git commands, overwrite unrelated changes, or make unrelated refactors. Never silently skip tests or fabricate command results. Never introduce a dependency without justification and alternatives. Never implement product behavior before requirements and acceptance criteria are understood.

## Inspect and understand

Read `AGENTS.md`, `docs/domain-model.md`, `docs/workflow-state-machine.md`, `docs/security.md`, `docs/deployment-strategy.md`, `docs/development-workflow.md`, relevant ADRs, and the feature requirements. Inspect actual ORM models, repositories, current migration heads/history, deployed-version assumptions, database version, CI/task commands, branch/worktrees, and uncommitted changes.

Confirm the desired invariant, data volume/distribution, null/duplicate cases, concurrent writers, long-running workflows, retention/deletion behavior, and rollback/recovery expectation. Discover every command from repository files; never invent commands or fabricate output.

## Plan

Use expand/migrate/contract by default:

1. add backward-compatible schema;
2. deploy dual-read/write or compatible code if needed;
3. backfill in resumable, idempotent, bounded batches with progress;
4. validate counts/invariants and observe;
5. switch reads;
6. remove old schema only after old code and rollback window are gone.

Assess locks, table rewrites, index build mode, transaction boundaries, statement/lock timeouts, replica/storage impact, tenant authorization, and failure resumption. Never make destructive down-migration the incident rollback strategy.

## Work safely

Never perform migration work on the default branch. Use a scoped branch/worktree after preserving existing changes. Never use destructive Git/database commands, overwrite unrelated work, or edit an already-applied migration. Avoid unrelated refactors. New dependencies require documented need, alternatives, and security/license/maintenance review.

Do not implement until requirements, acceptance criteria, rollout, and compatibility are understood. Require human approval for destructive changes, large backfills, irreversible transformations, prolonged locks, production data inspection/repair, or changed retention/privacy semantics.

## Implement and test

Generate migrations only with the repository-approved tool, then inspect generated SQL/operations manually. Make names explicit and deterministic. Separate operational backfills from schema DDL when safer. Add application compatibility before constraints become strict.

Run repository-defined migration lint/checks, upgrade from supported prior schema, repository integration tests, invariant queries, downgrade only when the documented migration is genuinely reversible, and upgrade again. Test interruption/resume and old/new application compatibility where relevant. Never silently skip tests; report exact results, skips, and environment limits.

Self-review the full diff for accidental drops, default volatility, null handling, lock risk, missing indexes/constraints, artifact/workflow references, tenant leakage, and stale docs/ER diagrams.

## Completion report

Report: invariant/change; expand-migrate-contract sequence; migration files; data volume/lock estimates; commands and exact results; validation queries; rollout/rollback/recovery; observability; skipped checks; risks and required human actions.
