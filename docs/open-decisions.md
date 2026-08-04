# Assumptions, choices, and open decisions

## Documented assumptions

- One developer builds the MVP; operational load must remain manageable by a small team.
- Initial projects have one owner; collaboration and complex roles are deferred.
- Inputs have ordinary Chinese subtitles in a configurable, narrow lower-frame band.
- Human review is an intended workflow component, not an exceptional failure.
- English-language code/docs and Vietnamese/Chinese content fields are acceptable.
- The cloud translation LLM is the only paid runtime provider; CI uses a fake unless an explicit budget-capped smoke test is enabled.
- OCR, TTS, local rewriting, workflow orchestration, storage, database, and telemetry run locally using free/open-source software.
- The first deployment is an owner-operated, always-on Apple Silicon machine accessed only through the existing Tailscale tailnet.
- Polling plus optional server-sent updates is sufficient; collaborative real-time editing is not required.
- PostgreSQL and object storage are enough for durable product data; no search engine or message broker is presently required beyond Temporal.
- Final render throughput is moderate during MVP and can be controlled by admission and low concurrency.
- Translation tone and subtitle styling are project-wide in the MVP; arbitrary prompts, per-segment tone/style, and font uploads are deferred.

## Proposed architectural choices

| Choice | Reason | Reversibility |
|---|---|---|
| Modular monorepo/monolith with process profiles | One team, shared transactions and models, independent resource scaling without network sprawl | Difficult after boundaries erode; enforce now |
| Python backend/workers and TypeScript web | Best fit for media/AI libraries plus mature editor ecosystem | Medium |
| Temporal orchestration | Durable human waits, retry/replay/cancellation, long workflows | Difficult; requires approval and proof-of-concept |
| PostgreSQL plus S3-compatible artifacts | Clear transactional/blob split, local operation, backup, and lineage | Difficult for primary data; object vendor is medium |
| Stable UUIDv7 IDs and immutable revisions/artifacts | Enables retries, audit, selective invalidation, reproducible renders | Difficult and foundational |
| HTML overlays over proxy video | Fast editable MVP without encoding loop | Easy to replace behind editor/render contracts |
| Provider ports with first adapters | Controls vendor coupling while avoiding speculative multi-provider runtime | Easy/medium; prompts/models still behaviorally sticky |
| Single-host Compose plus Tailscale Serve | No recurring hosting/authentication fee, no public ingress, and fits personal MVP volume | Medium; sacrifices high availability |
| Paid translation only | Concentrates variable spend in the capability where cloud quality matters most | Easy/medium behind provider ports |
| Versioned tone presets | Gives users predictable creative control without exposing arbitrary system prompts | Easy to add presets; prompt behavior is medium |
| Structured subtitle styles with pinned fonts | Enables responsive HTML preview and reproducible FFmpeg/libass output | Easy/medium; renderer parity requires tests |

## Decisions requiring human approval

### Gates for the affected roadmap phase

1. **Host envelope:** the Phase 1 check ran natively on an Apple M4 Mac mini with 16 GiB RAM and Docker Desktop arm64. Only about 7.4 GiB host disk remained after images were pulled. Before media/model phases, confirm an always-awake setup, reclaim or add durable storage, set disk admission thresholds, and decide whether production uses Colima or another Linux container host.
2. **Workflow platform:** approve self-hosted Temporal with PostgreSQL after the synthetic human-review/restart proof of concept; choose a simpler queue only if the host overhead is unacceptable.
3. **Tailnet use:** confirm this is personal/non-commercial use compatible with Tailscale's free plan. Commercial use requires a plan/license review or a self-hosted network/auth alternative.
4. **Provider evaluation set:** approve RapidOCR/ONNX Runtime, VieNeu-TTS v3 Turbo through local ONNX, llama.cpp, and the paid translation provider/model. Set a hard translation budget and per-project token ceiling. PaddleOCR remains an accuracy comparison with explicit Apple Silicon packaging cost.
5. **Supported input envelope:** maximum upload bytes, duration, resolution, frame rate, codecs/containers, and subtitle-band configuration.
6. **Data governance and backup:** retention periods, deletion SLA, translation-provider region/retention, backup frequency, and an independent external disk/NAS destination. A volume on the same physical host is not a backup.
7. **Product audio policy:** default original-audio retain/reduce/remove behavior and whether source dialogue isolation is explicitly out of scope.
8. **Local TTS promotion:** approve the exact VieNeu-TTS v3 Turbo code/model revision and one built-in preset voice only after license/provenance review, Vietnamese listening tests, content-integrity tests, and arm64-container benchmarks pass. Piper is rejected based on the owner's listening test; voice cloning remains out of scope.

### Required before production, not bootstrap

9. Availability targets, RPO/RTO, expected concurrent users/videos, target throughput, and acceptable queue delay.
10. Budget ceilings and per-user quotas; billing/subscription behavior remains out of MVP unless requested.
11. Local telemetry retention and disk budget.
12. Legal terms for uploaded media, translation-provider data processing, content deletion, and acceptable-use enforcement.
13. Objective OCR/translation/TTS quality thresholds and who performs Vietnamese/Chinese review.

### Required before the affected implementation phase

14. **Tone catalog:** approve the initial `natural`, `funny`, `formal`, and `dramatic` prompt behavior, Vietnamese evaluation fixtures, default preset, and confirmation copy for paid retranslation. Project-wide tone is the MVP default; per-segment tone and arbitrary prompts remain out of scope.
15. **Subtitle style policy:** approve the initial font catalog and licenses, default style, numeric control ranges, allowed colors/background/shadow controls, preview/render parity tolerance, and whether left/right alignment is useful enough for MVP. Arbitrary font uploads and raw CSS/ASS remain out of scope.

## Reversible experiments

- Evaluate RapidOCR/ONNX Runtime versus PaddleOCR/cloud OCR on a representative, approved subtitle fixture set, including native Apple Silicon and Linux arm64 packaging.
- Evaluate VieNeu-TTS v3 Turbo preset voices for pronunciation, naturalness, content fidelity, pacing, model/voice provenance, CPU/RAM use, and duration-fit quality on the actual Mac and inside Colima. Use VieNeu v2 CPU as the stability fallback if v3 early access fails. Cloud TTS is not a default candidate under the cost constraint.
- Compare small Vietnamese-capable GGUF models through llama.cpp on Apple Silicon using meaning-preservation and fit metrics.
- Validate Temporal operational/developer experience with one synthetic human-in-loop workflow before product stages.
- Benchmark FFmpeg proxy/render profiles on arm64 and amd64 before fixing worker sizes and upload limits.
- Run a power-loss/restart and backup/restore drill for PostgreSQL, Temporal state, Garage objects, and artifact-lineage reconciliation.
- Verify that Garage accepts S3 presigned upload/download requests through the selected Tailscale Serve HTTPS listener without Host/path signature mismatch; retain direct browser upload only if the contract test passes.
- Evaluate each tone prompt on the same Chinese/Vietnamese corpus for fidelity, glossary consistency, naturalness, timing pressure, token use, and subjective tone strength; do not promote humor or drama that invents content.
- Compare HTML/webfont preview frames with generated ASS/libass renders across approved fonts, aspect ratios, diacritics, two-line wrapping, borders, shadows, and safe-area settings before fixing parity tolerances.

## Decision process

Record accepted outcomes in ADRs. Mark proposed ADRs `Accepted`, `Rejected`, or `Superseded`; do not silently edit historical rationale after acceptance. Numerical policies should be configuration with versioned defaults and evaluation evidence.
