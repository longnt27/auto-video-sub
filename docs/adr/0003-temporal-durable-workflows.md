# ADR-0003: Use Temporal for durable workflows

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

Processing lasts minutes to hours, waits for human review, fans out by chunk/batch/segment, must resume after restarts, and needs bounded retry, timeouts, cancellation, and partial replay. Building these semantics on a basic queue would create substantial custom state machinery.

## Decision

Use self-hosted Temporal workflows for orchestration and Python activities for side effects. Persist Temporal state and SQL visibility in separate databases/credentials on the local PostgreSQL server. Keep domain decisions and product-facing stage history in application/PostgreSQL modules. Use separate task queues for orchestration, media, render, local AI, translation, and provider limits. Workflows remain deterministic and activities idempotent.

## Consequences

Durable timers, signals, cancellation, retry policy, and restart recovery are provided by a mature engine without a SaaS fee. The owner must operate more containers and learn replay determinism, workflow versioning, history limits, namespace operations, backup, and upgrades. Temporal competes for memory on the single host and is not the source of user authorization or artifact metadata.

## Alternatives considered

- Celery or Dramatiq with PostgreSQL/Redis: less conceptual/vendor overhead initially, but human waits, partial recovery, durable state, and exactly-once illusions become application responsibilities.
- Temporal Cloud or AWS Step Functions: reduce local operations but violate the paid-translation-only runtime constraint and add vendor dependence.
- PostgreSQL job table only: suitable for simpler jobs, not the full orchestration requirements without building a workflow engine.

## Reversibility and review triggers

Difficult because workflow semantics permeate operations. Before acceptance, build a synthetic single-host proof of concept covering review signals, worker/server restart, cancellation, idempotency, replay, PostgreSQL backup/restore, and measured idle/load resource use. Reconsider if host or operational overhead is disproportionate.
