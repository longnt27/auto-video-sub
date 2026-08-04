---
name: review-production-readiness
description: Audit a release, environment, workflow, or system increment for production readiness across correctness, reliability, security, privacy, observability, capacity, cost, deployment, rollback, recovery, and operations. Use before pilot/launch, after major architecture changes, or when asked for a go/no-go assessment; report evidence and blockers rather than implementing fixes unless separately authorized.
---

# Production Readiness Review

## Non-negotiable rules

Never perform feature work directly on the default branch, use destructive Git commands, overwrite unrelated changes, or make unrelated refactors. Never silently skip tests or fabricate command results. Never introduce a dependency without justification and alternatives. Never implement product behavior before requirements and acceptance criteria are understood.

## Establish the release baseline

Read `AGENTS.md`, all current product/architecture/domain/workflow/testing/security/observability/deployment/open-decision documents, accepted ADRs, release acceptance criteria, and operational runbooks/SLOs. Inspect repository status, intended commit/images, complete release diff, manifests/locks, migrations, workflow replay evidence, infrastructure/config, CI results, dashboards/alerts, and known issues.

Confirm target environment, traffic/volume, data classification, providers/regions, budget, RPO/RTO, rollout, rollback, and owners. Derive commands from checked-in files only. Never fabricate tests, scans, dashboards, capacity evidence, approvals, or command results.

## Review gates

Assess with evidence:

- product acceptance and linguistic/manual evaluation;
- tenant authorization, upload/media isolation, secrets, rate/quota controls, deletion, dependency/container/SBOM findings;
- workflow idempotency, bounded retries, timeouts, cancellation, partial recovery, replay compatibility, cleanup, and review backlog;
- database expand/migrate/contract, backups, restore drill, artifact lineage/retention, and rollback compatibility;
- queue fairness/backpressure, resource/temp-disk limits, load tests, provider throttling, and spend caps;
- structured errors/logs, metrics/traces, worker health, dashboards, actionable alerts, and runbook/on-call ownership;
- immutable release artifacts, non-root/multi-arch status, environment isolation, canary, rollback, and synthetic verification.

Classify findings: `blocker`, `high`, `medium`, `low`, or `accepted risk`. Give owner, evidence, remediation/mitigation, and due gate. Missing evidence is not a pass.

## Work safety and validation

This skill is review-first. Do not modify production, deploy, migrate, rotate secrets, delete data, or fix code without explicit authorization. Never work features on the default branch, use destructive Git commands, overwrite unrelated changes, add unjustified dependencies, or request unrelated refactors.

Run only safe, approved, repository-defined checks. Never silently skip tests; identify unavailable and stale evidence. Paid/provider or destructive resilience tests require explicit approval and isolated targets. Self-review findings for duplication, false confidence, unowned mitigations, rollback gaps, and contradictions with open decisions.

## Human decision

Require human go/no-go for unresolved blocker/high findings, accepted security/privacy/data-loss risk, unmet RPO/RTO, destructive migration, legal/provider data terms, budget/quotas, language-quality thresholds, or rollback/restore not demonstrated. Do not infer launch approval.

## Completion report

Lead with recommendation: `go`, `conditional go`, or `no-go`, and state that humans own the decision. List findings by severity with evidence/owner/action; checks and exact results; skipped/missing evidence; release/rollback/recovery posture; capacity/cost/security status; accepted risks; and explicit approvals required.
