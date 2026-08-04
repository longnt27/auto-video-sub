# Proposed repository structure

The architecture was approved on 2026-08-04. Phase 2 now contains the first vertical product slice through the existing package boundaries.

```text
.
├── apps/
│   ├── web/                       # Next.js editor and authenticated UI
│   ├── api/                       # FastAPI composition root and HTTP transport
│   └── worker/                    # Temporal media workflow and activity host
├── packages/
│   ├── domain/                    # Pure Python aggregates, policies, value objects
│   ├── application/               # Use cases, ports, commands, queries
│   ├── infrastructure/            # PostgreSQL, object store, Temporal, telemetry
│   ├── providers/                 # OCR, LLM, TTS, local rewrite, FFmpeg adapters
│   └── contracts/                 # Deferred until generated cross-language contracts add value
├── db/
│   ├── alembic.ini
│   └── migrations/                # Reviewed Alembic revisions; never app-startup DDL
├── tests/
│   ├── fixtures/media/            # Tiny deterministic, licensed/generated media
│   ├── fixtures/fonts/            # Reviewed subset/provenance for render parity tests
│   ├── contract/
│   ├── integration/
│   ├── workflow/
│   ├── e2e/
│   ├── security/
│   └── load/
├── deploy/                        # Local Compose topology and later deployment definitions
├── assets/
│   └── fonts/                     # Added with the approved font catalog in Phase 6
├── scripts/                       # Integration and synthetic full-stack smoke scripts
├── docs/
│   └── adr/
├── .agents/skills/                # Repository-scoped Codex workflows
└── .github/                       # Review templates, dependency updates, and cost-free CI
```

## Deployable applications

`web`, `api`, and `worker` are deployable processes, not separate products or repositories. Phase 2 runs the `media` Temporal queue in the worker composition root. Later approved phases may run these profiles independently from the same codebase:

- `workflow`: Temporal workflows and lightweight orchestration activities;
- `media`: probe, proxy, extraction, and bounded audio transformations;
- `render`: final FFmpeg composition and output validation;
- `local-ai`: OCR, VieNeu-TTS synthesis, and narrowly scoped llama.cpp rewrite activities without provider credentials or internet egress;
- `translation`: global context extraction, semantic translation batches, and LLM-assisted consistency activities with the sole paid provider credential.

Queue profiles may later split further only when measured resource contention justifies it. Domain and application packages never import app entry points.

## Dependency direction

```mermaid
flowchart LR
  Web[apps/web] --> HTTP[Reviewed JSON API]
  API[apps/api] --> App[packages/application]
  Worker[apps/worker] --> App
  API --> Infra[packages/infrastructure]
  Worker --> Infra
  Worker --> Providers[packages/providers]
  App --> Domain[packages/domain]
  Infra -. implements ports .-> App
  Providers -. implements ports .-> App
```

Domain code imports only the standard library and explicitly approved domain utilities. Application code depends on domain types and defines ports. Infrastructure and providers implement those ports. Composition roots select implementations.

Current Phase 2 placement is concrete: project/media rules and UUIDv7 IDs live in `domain`; project/upload use cases and ports in `application`; SQLAlchemy models/repositories, Garage, settings, and Temporal client in `infrastructure`; FFmpeg/ffprobe in `providers`; FastAPI auth/routes in `apps/api`; the deterministic workflow and activities in `apps/worker`; and the same-origin gateway/UI in `apps/web`.

## Package boundary rules

- Prefer a few cohesive packages over one package per entity or stage.
- Keep SQL models and repository implementations in `infrastructure`; do not leak them into domain APIs.
- Keep provider SDK payloads inside provider adapters.
- Keep tone prompt templates server-owned and versioned; expose preset identifiers through contracts, never raw system prompts.
- Keep the font catalog small and license-reviewed. Browser and renderer variants must derive from the same pinned font release.
- Generate the TypeScript client from the reviewed OpenAPI contract; do not maintain duplicate hand-written wire types.
- Keep test fixtures small, deterministic, legally usable, and described by provenance.
- Place scripts only when their command, inputs, safety behavior, and owner are documented.
