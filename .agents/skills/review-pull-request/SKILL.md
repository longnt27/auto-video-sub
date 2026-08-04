---
name: review-pull-request
description: Review a pull request, branch, patch, or diff in this repository for correctness, regressions, security, reliability, architecture fit, and test adequacy. Use when asked for code review or merge readiness; report findings rather than modifying the change unless the user separately authorizes fixes.
---

# Pull Request Review

## Non-negotiable rules

Never perform feature work directly on the default branch, use destructive Git commands, overwrite unrelated changes, or make unrelated refactors. Never silently skip tests or fabricate command results. Never introduce a dependency without justification and alternatives. Never implement product behavior before requirements and acceptance criteria are understood.

## Gather scope

1. Read `AGENTS.md`, the PR description/acceptance criteria, relevant product/architecture/domain/workflow/security/testing documents, and accepted ADRs.
2. Inspect repository/branch/worktree state, the complete diff against the intended base, changed contracts/migrations/generated files, and nearby code/tests. Preserve all changes; never use destructive Git commands.
3. Discover review/test commands from repository files. Never invent or fabricate command results.

## Review by risk

Trace changed behavior end to end. Prioritize:

- authorization and cross-tenant object/project access;
- data invariants, migration compatibility, immutable revisions, and artifact lineage;
- workflow determinism, idempotency, retries, timeouts, duplicate delivery, cancellation, and cleanup;
- stable subtitle IDs and backend-owned timestamps;
- provider schema/error validation, prompt/model versioning, privacy, and cost;
- unsafe media/FFmpeg or temporary-file behavior;
- concurrency, backpressure, quotas, observability, and rollback;
- API/UI contract compatibility and user-visible failure/review states;
- test quality, including whether assertions would detect the defect.

Differentiate defects from preferences. Cite file and line, concrete failure scenario, impact/severity, and a minimal correction direction. Do not request unrelated refactors or a dependency without concrete justification and alternatives.

## Validation and self-review

Run safe, repository-defined checks proportional to the review if authorized and practical. Never silently skip tests; disclose what was not run. Do not call paid providers by default. Check that implementation was not done on the default branch when branch metadata is available.

Review your own findings for false positives, duplicated comments, scope creep, and missing evidence. If no findings remain, state that explicitly while noting residual test/inspection limits.

## Human review cases

Escalate uncertain product behavior, security/privacy incidents, destructive or irreversible migrations, architecture/ADR conflicts, provider/legal commitments, linguistic quality judgments, and release risk outside available evidence. Do not approve by guessing.

## Completion report

Lead with findings ordered by severity. For each: location, issue, failure scenario/impact, and suggested direction. Then list questions/assumptions, checks and exact results, skipped checks, and a brief change summary. Do not bury defects in general commentary.
