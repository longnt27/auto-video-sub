---
name: fix-bug
description: Diagnose and fix a reproducible defect in this repository with evidence and regression coverage. Use for incorrect behavior, failed workflows, data/artifact inconsistency, provider errors, authorization defects, media failures, or regressions; use diagnosis only when the user has not authorized a code change.
---

# Bug Fixing

## Non-negotiable rules

Never perform feature work directly on the default branch, use destructive Git commands, overwrite unrelated changes, or make unrelated refactors. Never silently skip tests or fabricate command results. Never introduce a dependency without justification and alternatives. Never implement product behavior before requirements and acceptance criteria are understood.

## Establish evidence

1. Read `AGENTS.md`, relevant product/architecture/domain/workflow/security documents, accepted ADRs, and the bug report.
2. Inspect repository status, current branch/worktrees, unrelated changes, affected code history when available, tests, logs/errors, artifacts, and actual task commands.
3. Reproduce with synthetic/sanitized inputs or establish the narrowest failing invariant. Separate symptom, trigger, root cause, and impact. Do not change code merely because a suspicious pattern exists.
4. Never invent commands, logs, reproduction, or test results.

## Plan the correction

Define expected behavior and a regression test that fails for the right reason. Assess affected tenants/data, stage scopes, artifact lineage, open workflow histories, provider versions, migrations, security exposure, and need for repair/backfill. If requirements are ambiguous or the fix changes product behavior, stop for human review.

## Work safely

Do not perform bug-fix implementation on the default branch; use a scoped branch/worktree after preserving existing changes. Never use destructive Git commands, overwrite unrelated work, or use cleanup commands on unverified paths. Avoid unrelated refactors. A new dependency requires explicit justification, alternatives, and security/license/maintenance review.

## Fix and verify

Apply the smallest root-cause fix through existing boundaries. Preserve stable IDs, idempotency, immutable history, authorization, bounded retries, and cancellation. Do not rewrite historical artifacts or production data casually; design an auditable repair if needed.

Add the regression test at the lowest useful layer, plus integration/workflow/security coverage when the failure crosses a boundary. Run repository-discovered targeted checks, then the required broader suite. Never silently skip tests or paid-provider restrictions; state every skip/failure.

Self-review the full diff and run an adjacent-case analysis: duplicate delivery, retry after partial publication, cancellation, stale revisions, cross-user access, malformed input, timeout, and rollback. Confirm the test would fail without the fix.

## Human review cases

Require review for suspected security incidents, customer-data repair/deletion, destructive migrations, changed acceptance criteria, provider/model/prompt behavior, non-backward-compatible APIs/workflows, or a fix whose blast radius cannot be bounded.

## Completion report

Report: symptom and impact; evidence/reproduction; root cause; correction; regression and exact test results; skipped checks; data repair/rollout/rollback; security implications; remaining risks and human actions.
