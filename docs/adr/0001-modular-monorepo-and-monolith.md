# ADR-0001: Use a modular monorepo and modular monolith

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

One developer must build a web editor, API, durable workflows, media pipelines, and AI-provider integrations. These concerns need clear ownership but share domain transactions and are likely to change together during MVP discovery. Independent resource profiles are needed for API, AI, and render workloads.

## Decision

Use one repository and one backend codebase organized into domain, application, infrastructure, and provider packages. Deploy web, API, and independently scalable worker entry points from that monorepo. Treat logical modules as code boundaries, not network services.

## Consequences

Changes and contracts remain easy to coordinate, local development stays tractable, and workers can scale by task queue. Boundaries require import rules and review because the database and process can otherwise encourage coupling. A single release may include multiple process images even when only one module changed.

## Alternatives considered

- Microservices/repositories: stronger runtime isolation but premature network, deployment, schema, and observability overhead.
- One undifferentiated application process: operationally simple but media workloads can starve API traffic and cannot scale independently.

## Reversibility and review triggers

Difficult after code accumulates. Reconsider extracting a service only with measured scaling/isolation needs, distinct ownership, or an external contract that cannot be met within queue/process isolation.
