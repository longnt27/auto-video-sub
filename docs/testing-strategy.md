# Testing strategy

## Principles

Tests follow dependency boundaries, run deterministically by default, and make expensive provider calls opt-in. Every production defect receives the smallest useful regression test. Test data must be licensed, generated, or explicitly approved and must not contain customer media.

## Layers

| Layer | Scope and examples | Default execution |
|---|---|---|
| Domain unit | state transitions, input fingerprints, tone/style versioning and invalidation, quotas, translation validation, duration decisions, error classification | Every change; no network/filesystem unless intrinsic |
| Property tests | segment timing/order, ID set validation, retry bounds, artifact lineage invariants | Pull requests for affected packages |
| Adapter contract | OCR/LLM/TTS/object store/local rewrite request mapping, schemas, error normalization, idempotency | Mock/fake provider by default |
| Persistence integration | PostgreSQL repositories, constraints, transactions, optimistic locking, migrations | Ephemeral real PostgreSQL |
| Storage integration | signed intent rules, checksums, multipart abort, tenant key isolation, retention tags | Ephemeral S3-compatible service |
| Workflow integration | Temporal retry/resume/timeout/signal/cancellation/idempotency and replay compatibility | Temporal test server/environment |
| Media processing | probe, region extraction, proxy, silence trim, ASS/font subtitle rendering, mux/render, validation | Version-pinned FFmpeg/libass and tiny fixtures |
| API contract | OpenAPI conformance, auth/ownership, idempotent mutations, errors, generated-client compatibility | API with ephemeral dependencies |
| Browser E2E | create/upload handshake, tone selection/cost confirmation, reviews, HTML overlay and style controls, status recovery, render/download authorization | Playwright with fake providers |
| Security | cross-tenant object/project attempts, MIME/magic mismatch, malformed media, URL expiry, quotas, injection/path handling | Pull request subset plus scheduled suite |
| Load/resilience | status polling, workflow admission, queue backpressure/fairness, worker loss, provider throttling | Pre-release/scheduled, never against production by default |

## Deterministic provider testing

Each provider port has a shared behavioral contract. Fakes return recorded, synthetic responses and configurable failures: timeouts, 429s, truncation, unknown IDs, malformed audio, and duplicate callbacks. Adapter tests prove translation into domain errors without asserting SDK internals.

The paid translation-provider smoke test requires an explicit variable such as `RUN_TRANSLATION_LLM_SMOKE=1`, separately scoped credentials, a hard token/cost/time cap, and manual execution. CI pull requests must not call it. OCR, VieNeu-TTS, llama.cpp, Garage, PostgreSQL, Temporal, and FFmpeg tests are local, but large-model/media suites can remain separately tagged for resource reasons.

## Workflow scenarios

At minimum, exercise:

- worker termination and replay after an activity heartbeat;
- transient failure followed by success and retry exhaustion;
- duplicated activity delivery and duplicate API commands;
- cancellation before work, during chunk work, and around artifact publication;
- human-review signal before and after workflow wait begins;
- timeout and late provider response;
- one failed OCR chunk, translation batch, TTS segment, and render retry;
- edit-driven invalidation with compatible artifact reuse;
- workflow code compatibility for histories that remain open across deployments.

Use Temporal time skipping for timers where supported. Replay representative saved histories before deploying workflow changes.

Deployment security tests also verify that direct LAN/tailnet access to container ports fails, only Tailscale Serve can supply trusted identity, spoofed identity headers are removed/rejected, Funnel/public ingress is disabled, signed object URLs expire, and non-translation workers cannot reach arbitrary internet endpoints.

Tone tests snapshot each server-owned prompt template and assert that the selected policy version enters the provider envelope and idempotency fingerprint. Deterministic fixtures cover all presets, stable IDs, glossary constraints, meaning preservation, bounded humor/drama, and invalid provider output. A tone change test proves context/OCR reuse, explicit paid-cost confirmation, cancellation or rejection of late old-policy results, and invalidation of translation/TTS/render only. CI uses fakes; linguistic tone promotion requires comparative review by a qualified Vietnamese speaker.

Subtitle-style tests follow [the styling contract](subtitle-styling.md). They prove canonical values and font checksums reach both HTML preview and render manifests, style edits schedule no translation/TTS/encode work, and only final rendering is invalidated. Security fixtures include CSS/ASS/filter injection, paths/URLs, malformed colors, unsupported fonts/faces, extreme dimensions, and cross-project style references.

## Media fixtures and assertions

Keep short deterministic fixtures with documented generation commands and expected probe metadata: no subtitle, one/two lines, changing subtitle, Vietnamese diacritics, variable frame rate where supported, rotated input, common aspect ratios, multiple audio tracks, corrupted/truncated media, extreme metadata, and audio with known silence/duration. Keep reviewed font fixtures with exact license/provenance and checksums. Assert structural properties and declared preview/render tolerances rather than bit-for-bit encoded video unless the codec/profile is deterministic.

## Quality evaluation

Automated translation validation does not establish linguistic quality or tone quality. Maintain a versioned Chinese/Vietnamese evaluation set reviewed by a qualified speaker, with cases for aliases, kinship, organizations, slang, pronouns, humor, formal hierarchy, emotional dialogue, and duration-constrained speech. Compare every tone prompt/model candidate offline and require human review for regressions before promotion.

OCR evaluation records character/line accuracy plus segment boundary quality on representative subtitle styles. TTS evaluation combines duration-fit metrics with listening review by a Vietnamese speaker. The VieNeu-TTS promotion corpus covers all three regional preset groups, names and Sino-Vietnamese terms, numbers, punctuation, English code-switching, emotional dialogue, short utterances, long sentences, and duration-constrained lines. Record pronunciation/content errors, repetition or omission, naturalness, clipping/silence, real-time factor, peak memory, and failure rate on the actual Apple Silicon host and inside the planned arm64 Colima container. Pin an exact model revision and one preset voice only after it meets agreed thresholds and the owner accepts its listening quality; Piper does not need to be retained or re-evaluated. Upgrades repeat the same evaluation.

## CI quality gates

Fast formatting, lint, type, unit, and contract tests run first. Integration/media tests run in parallel using pinned services. Browser E2E runs on the assembled candidate. Security/dependency/container scans and migration checks gate release. Fail closed on missing required tests; quarantine requires an owner, reason, issue, and expiry.

The implemented Phase 2 CI runs Python quality plus real PostgreSQL/Garage migration contracts, web quality/build, and Compose validation. Only a protected-main push that passes all three job groups may publish application images. Pull requests never receive `packages: write`, never publish images, and never run on the production host.

Coverage is a diagnostic, not the goal. Critical domain policy branches and authorization rules require direct assertions regardless of aggregate coverage.

## Test command discovery

Future contributors must read the checked-in `Makefile`, manifests, lockfiles, and CI rather than guessing commands. The exact supported setup and verification commands are maintained in [the development workflow](development-workflow.md). Paid-provider smoke tests are never part of `make check` or pull-request CI.

## Phase 2 executable coverage

Phase 2 currently provides:

- pure domain tests for UUIDv7 and media-limit rules;
- FastAPI use-case tests for project/upload flow, fail-closed identity, request size limits, and cross-owner denial;
- a deterministic generated MP4 test for magic detection, FFprobe, and proxy output;
- real PostgreSQL tests for identity/idempotency concurrency, ownership, quota-backed upload, original/proxy publication, and lineage foreign keys;
- real Garage tests for signed PUT, sealing, download, and deletion;
- Alembic upgrade/downgrade/upgrade and autogenerate-drift checks;
- a full local-stack synthetic smoke from same-origin web gateway through signed upload, Temporal activities, FFmpeg, artifact registration, and signed preview download.

Run `make check`, `make test-integration`, `make build`, `make stack-config`, and—after `make stack-up`—`make stack-smoke-phase2`. Phase 3 must add Temporal time-skipping/replay/cancellation tests; Phase 2's live smoke proves the happy durable path but does not claim those later scenarios.
