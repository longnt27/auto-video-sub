# ADR-0004: Use PostgreSQL and S3-compatible artifact storage

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

Projects, revisions, authorization, workflow history, quotas, and lineage require transactions and relational queries. Videos, frames, audio, model envelopes, and renders are large immutable blobs unsuitable for the application database or container disks.

## Decision

Use one local PostgreSQL server for transactional metadata, with separate application and Temporal databases/credentials, and Garage as the S3-compatible private object store for durable artifacts. Use SQLAlchemy repositories and Alembic after bootstrap. Store PostgreSQL and Garage data on persistent host volumes and back them up to a physically independent target. Register verified objects transactionally and sweep abandoned staging data.

## Consequences

The split supports signed direct uploads, checksums, lifecycle rules, and later migration to another S3 provider. Cross-system publication requires idempotent reconciliation. Garage's S3 subset must be contract-tested, and a single node provides no redundancy; availability and durability depend on off-host backups and restoration drills.

## Alternatives considered

- Store blobs in PostgreSQL: simpler consistency but poor fit for large streaming media, signed access, and storage lifecycle.
- Container volumes/filesystem: fails durability, scaling, and lineage requirements.
- MinIO: familiar, but its community repository is archived and current community distribution is source-only under AGPLv3, increasing maintenance/license review burden.
- AWS S3 or another managed object store: higher durability with less operation but adds recurring cost and cloud dependence.
- Multiple databases/search engines: no present query or scale need justifies their operations.

## Reversibility and review triggers

PostgreSQL is difficult to replace; Garage is medium because semantics stay within a tested S3 subset. Revisit for insufficient single-host durability, failed compatibility tests, commercial license concerns, or measured scale. A provider change creates a migration plan and preserves artifact checksums/IDs.
