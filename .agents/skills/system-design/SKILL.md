---
name: system-design
description: Design or revise architecture, domain boundaries, workflows, data ownership, APIs, security, deployment, or cross-cutting technical plans for this video-localization repository. Use for new subsystems, significant design changes, ADRs, technology selection, scaling/reliability plans, or work spanning multiple modules; do not use it to implement unapproved product code.
---

# System Design

## Non-negotiable rules

Never perform feature work directly on the default branch, use destructive Git commands, overwrite unrelated changes, or make unrelated refactors. Never silently skip tests or fabricate command results. Never introduce a dependency without justification and alternatives. Never implement product behavior before requirements and acceptance criteria are understood.

## Establish context

1. Read `AGENTS.md`, `README.md`, `docs/product-overview.md`, `docs/architecture.md`, `docs/repository-structure.md`, `docs/domain-model.md`, and `docs/open-decisions.md` completely.
2. Read the relevant workflow, translation, duration, security, observability, testing, deployment, and accepted ADR documents for the topic.
3. Inspect the actual repository tree, manifests, contracts, recent decisions, current branch/worktrees, and uncommitted changes. Treat the proposed tree as non-existent until files confirm it.
4. Derive all commands from checked-in task runners, manifests, README, and CI. Never invent commands or fabricate results.

## Plan and design

State the problem, actors, scope, exclusions, constraints, quality attributes, acceptance criteria, assumptions, and unresolved decisions. Trace at least one normal flow and relevant failure/recovery flows. Define logical ownership and dependency direction before choosing technologies.

For durable processing, specify stage scopes, authoritative state, artifacts, idempotency keys, retries, timeouts, cancellation, partial invalidation, backpressure, quotas, and human review. For data, specify identity, versioning, invariants, authorization, retention, migration, and rollback. For providers, specify ports, versioned contracts, validation, usage/cost, and failure normalization.

Compare realistic alternatives and classify reversibility. Prefer the simplest design meeting present requirements. Create or update an ADR when the decision changes persistent data, public contracts, process boundaries, workflow semantics, security, deployment, or a costly vendor commitment.

## Work safely

Do not perform feature work on the default branch; use a task branch or isolated worktree after inspecting repository state. Never use destructive Git commands, overwrite unrelated changes, or refactor unrelated areas. Do not introduce a dependency without a concrete justification, alternatives, compatibility/security/license review, and approval where required.

Do not implement product behavior until requirements and acceptance criteria are understood and the current approval gate permits it. Ask for human review when ambiguity affects user behavior, data compatibility, security/privacy, cost, provider commitment, or rollout risk.

## Validate and self-review

Check the proposal against every affected document and ADR. Verify module dependency direction, state recovery, smallest-scope retry, tenant isolation, immutable lineage, operational ownership, testability, migration safety, and rollback. Use diagrams only where they clarify boundaries or state. If executable validation applies, run only discovered commands and report failures/skips honestly; never silently skip tests.

Review the complete diff for contradictions, speculative abstractions, unapproved implementation, unrelated changes, and stale links. Update affected documentation together.

## Completion report

Report: outcome; scope/non-goals; decision and alternatives; modules/data/workflows affected; security/operations/cost; validation performed with exact results; files changed; risks; reversible experiments; unresolved items requiring human approval.
