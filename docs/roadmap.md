# Roadmap

Each phase ends with a review gate. Scope may be reduced after evaluation; later phases do not authorize themselves.

## Phase 0 — architecture approval (completed 2026-08-04)

The owner approved the documented architecture and directed implementation. All initial ADRs are accepted; unresolved numerical/provider/catalog choices remain explicit gates for their affected phases.

## Phase 1 — reproducible skeleton (implementation complete 2026-08-04)

Initialize Git if approved; add pinned tool versions, workspace/package manifests, lockfiles, task runner, minimal web/API/worker composition roots, local Compose dependencies, lint/type/test harnesses, non-root Dockerfiles, cost-free CI/local checks, and development documentation. Include no product workflow beyond health/readiness and local dependency connectivity.

**Current review gate.** The arm64 quality suite, production web build, non-root image builds, Compose validation, clean-volume startup, and live health/readiness smoke checks passed. The owner must accept this evidence before Phase 2 starts.

Exit: a clean checkout can run documented checks on arm64; the local stack can start without paid services; CI validates both language stacks; no paid translation call occurs.

## Phase 2 — project, identity, upload, and artifacts

Implement Tailscale Serve identity validation, tenant-safe projects, quota-aware tailnet-only signed upload intents, media safety validation/probing, immutable artifacts/lineage, proxy generation, and browser proxy playback.

Exit: authorized user can safely upload a fixture and preview a proxy; cross-tenant/security tests pass.

## Phase 3 — durable workflow and transcript

Implement Temporal orchestration, stage history/progress/cancellation, region extraction, OCR adapter, consolidation, stable subtitle IDs, transcript revisions, and review UI.

Exit: worker restart/retry/cancel tests pass and a transcript can be corrected without global reprocessing.

## Phase 4 — context and translation

Implement context/entity versions, the versioned natural/funny/formal/dramatic tone catalog, tone selection with paid-rerun confirmation, semantic batching, cloud LLM adapter, strict validation, cost ledger, rolling summaries, consistency pass, translation editor, and structured subtitle-style controls with HTML preview.

Exit: every tone prompt meets agreed validation/quality thresholds; tone changes reuse context but never old translation text; inconsistent terms surface for review; style edits persist and update HTML overlays without encoding or provider calls.

## Phase 5 — TTS and duration fitting

Implement the approved VieNeu-TTS adapter with a pinned preset voice, actual-duration measurement, silence trimming, bounded speed-up, llama.cpp rewrite adapter, immutable attempts, segment-level repair/review, and audio preview. Do not enable voice cloning.

Exit: deterministic policy/workflow tests and listening evaluation pass; attempts never loop indefinitely.

## Phase 6 — rendering and download

Implement frozen render manifests, the approved font catalog, generated ASS/libass subtitle rendering from immutable style versions, isolated FFmpeg render, configurable original-audio policy, output validation, retention, signed downloads, and partial rerender behavior.

Exit: end-to-end fixtures produce validated outputs with reproducible style/font lineage and preview/render parity inside declared tolerances; a style-only change rerenders without upstream processing.

## Phase 7 — production hardening and pilot

Complete load/resilience/security testing, local dashboards/alerts/runbooks, off-host backup/restore and rollback drills, Tailscale exposure tests, SBOM/scanning, translation spend controls, single-host deployment automation, data deletion, and a limited tailnet-only pilot.

Exit: production-readiness review has no unresolved critical findings and explicit launch approval is recorded.
