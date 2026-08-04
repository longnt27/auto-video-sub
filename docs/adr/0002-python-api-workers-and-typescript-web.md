# ADR-0002: Use Python for API/workers and TypeScript for the web

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

The backend is dominated by OCR, LLM/TTS integrations, media tooling, durable orchestration, and data validation. The editor benefits from the React/TypeScript ecosystem and typed browser APIs.

## Decision

Use FastAPI/Pydantic on Python, with 3.12 as the proposed compatibility baseline for the first bootstrap, for the HTTP API and domain/application/workers. Use Next.js, React, and TypeScript for the browser. Generate a TypeScript API client from reviewed OpenAPI rather than sharing runtime code across languages. Confirm the final Python minor against every native OCR/media/Temporal dependency on macOS arm64 and Linux arm64/amd64 before pinning it.

## Consequences

Python provider/media libraries stay direct and the editor uses a mature ecosystem. Two language toolchains and contract generation add CI/local complexity. Domain types cannot be naively shared, so wire schemas and compatibility tests are important.

## Alternatives considered

- TypeScript/NestJS everywhere: one language but Python OCR/media/local-model processes would still exist or become network sidecars.
- Python-rendered web UI: simplifies tooling but is a weaker fit for a timeline editor.
- Django: productive built-ins, but stronger persistence/framework coupling than desired application ports.

## Reversibility and review triggers

Medium. Frameworks can change behind contracts, but language rewrites are costly. Reconsider after a thin vertical-slice benchmark exposes library, performance, or staffing constraints.
