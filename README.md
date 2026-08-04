# Chinese-to-Vietnamese Video Localization

Planning repository for a web application that turns Chinese-language videos with ordinary bottom-region subtitles into Vietnamese-language videos. The MVP extracts subtitle segments, builds story-wide translation context, supports selectable translation tones and human correction, previews configurable subtitle styling, generates duration-fitted Vietnamese speech, and renders a downloadable result.

The initial architecture was approved on 2026-08-04. Implementation now follows the gated phases in [the roadmap](docs/roadmap.md); each phase must meet its exit criteria before later product work proceeds.

## Approved foundation

- Next.js and TypeScript for the browser editor.
- FastAPI and Python for the API, domain modules, media workers, and provider adapters.
- Temporal for durable, resumable workflows and stage-level activity retries.
- PostgreSQL for transactional metadata and S3-compatible storage for immutable artifacts.
- FFmpeg/ffprobe for deterministic media work; replaceable adapters for OCR and LLMs; VieNeu-TTS v3 Turbo is the proposed local Vietnamese TTS candidate, subject to its quality gate.
- OpenTelemetry-based logs, metrics, and traces.
- A single-host, containerized deployment exposed only inside a Tailscale tailnet. The cloud translation LLM is the sole paid runtime dependency.

The approved design is a modular monorepo and modular monolith with independently runnable worker processes—not a fleet of microservices.

## Start here

1. Read [the product scope](docs/product-overview.md).
2. Review [open decisions](docs/open-decisions.md) and the [ADRs](docs/adr/README.md).
3. Review [architecture](docs/architecture.md), [domain model](docs/domain-model.md), [workflow design](docs/workflow-state-machine.md), and [subtitle styling](docs/subtitle-styling.md).
4. Follow the current implementation phase and review gates in [the roadmap](docs/roadmap.md).

## Current status

Phase 2 implementation is complete on its review branch. It adds tenant-scoped projects, quota-reserved direct uploads, PostgreSQL metadata and Alembic migration, immutable original/proxy artifacts with lineage, a durable Temporal media-ingest workflow, FFprobe safety validation, FFmpeg proxy generation, signed preview URLs, and the browser project/upload/playback flow. Phase 3 remains blocked until the owner accepts the Phase 2 evidence.

See [the Phase 2 API contract](docs/api-phase2.md), [AGENTS.md](AGENTS.md), and [the development workflow](docs/development-workflow.md).

## Local quick start

Required host tools are Node.js `22.22.x`, pnpm `11.15.x` through Corepack, Python `3.12.13`, uv `0.11.3`, Docker with Compose, and at least 6 GiB of free disk space for the local stack.

```sh
cp .env.example .env
make bootstrap
make check
make stack-config
make stack-up
make stack-smoke
make stack-smoke-phase2
```

The web and API are available only on loopback at `http://127.0.0.1:3100` and `http://127.0.0.1:8000`. `make stack-smoke-phase2` generates a one-second synthetic video and exercises project creation, direct object upload, validation, proxy generation, and signed playback. `make stack-down` stops containers without deleting persistent volumes. No command above calls the paid translation provider.

Run one process without containers with `make web`, `make api`, or `make worker` after starting the local dependencies. Discover the authoritative commands in the root `Makefile`, workspace manifests, and CI workflow.

Use `make test-integration` for clean PostgreSQL/Garage contract tests and a migration upgrade/downgrade/upgrade cycle. The provisional local admission policy is 2 GiB, three hours, 3840×2160, 60 fps, and 16 streams; these are configurable safety ceilings, not a production capacity promise.
