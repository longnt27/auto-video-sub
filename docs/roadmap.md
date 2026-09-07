# Roadmap

This document is the execution source of truth for the remaining MVP work. Architecture details live in the ADRs and design documents; this roadmap decides **what is implemented next, what proves it works, and when a phase is allowed to close**.

## Execution rules

1. Work proceeds in phase order. A later phase may be researched, but product implementation does not begin until the previous phase exit criteria pass.
2. Every phase must end in a runnable vertical slice, not only new abstractions or documents.
3. Tests are part of the phase deliverable. A phase is not complete when the happy path works manually.
4. Long-running or retry-sensitive media/AI work must remain behind Temporal activities/workflows; do not replace durable orchestration with in-process background jobs.
5. Artifacts and editorial outputs remain immutable/versioned. Reprocessing should invalidate only descendants whose input fingerprint changed.
6. Paid translation calls stay opt-in, budgeted, and disabled in normal CI. OCR, TTS, rewriting, rendering, storage, database, workflow orchestration, and telemetry remain local by default.
7. Open decisions block only the first phase that consumes them. Resolve them before that implementation starts; do not stop unrelated work.
8. If scope must be cut, cut optional controls or automation before cutting correctness, recoverability, security, or lineage.

## Current status

| Phase | Status | User-visible result |
|---|---|---|
| 0 — Architecture | Completed | Approved technical direction and ADR baseline |
| 1 — Reproducible skeleton | Completed | Clean checkout, local stack, CI, runnable web/API/worker processes |
| 2 — Project, upload, and proxy | Completed | Authorized user can create a project, upload a video, validate it, generate a proxy, and play it in the browser |
| 3 — Source transcript | **Next** | Extract Chinese subtitle text into an editable, versioned transcript |
| 4 — Translation | Planned | Produce and review Vietnamese subtitles with controlled paid translation |
| 5 — Vietnamese speech | Planned | Produce fitted Vietnamese speech per translated segment |
| 6 — Render and export | Planned | Render a reproducible final localized video and download it |
| 7 — Production hardening | Planned | Safely operate a limited tailnet-only pilot |

Phase 2 is accepted as the current product baseline. Its provisional media limits remain configuration, not a reason to block Phase 3.

---

## Phase 0 — architecture approval — completed

**Outcome:** establish the modular monorepo/monolith, process boundaries, storage/database split, durable workflow strategy, local-first provider policy, Tailscale access model, and immutable artifact/versioning model.

**Exit evidence:** accepted ADR baseline and implementation direction.

---

## Phase 1 — reproducible skeleton — completed

**Outcome:** a clean checkout can install pinned dependencies, run web/API/worker processes, start local PostgreSQL/Temporal/Garage dependencies, and execute deterministic quality checks.

**Exit evidence:** arm64 local stack, CI for Python and TypeScript, non-root container images, lockfiles, migrations, health/readiness checks, and no paid provider call in ordinary CI.

---

## Phase 2 — project, identity, upload, and proxy — completed

**Outcome:** an authorized tailnet user can create an isolated project, upload a supported video through a signed intent, validate the media, persist immutable artifact lineage, generate a proxy through Temporal, and preview it in the web UI.

**Implemented baseline:**

- Tailscale identity gateway with trusted-proxy and internal-secret validation.
- Tenant-safe project ownership and quota-aware upload admission.
- Signed object upload/download boundaries backed by Garage.
- Media probing, safety limits, immutable original/proxy artifacts, and lineage.
- Durable `media-ingest-v1` workflow with bounded retries and failure recording.
- PostgreSQL/Garage/migration integration coverage and signed-upload-to-proxy smoke path.
- GitHub CI plus immutable multi-architecture API/web/worker image publishing from `main`.

**Exit:** upload-to-proxy vertical slice and cross-tenant/security tests pass.

---

# Remaining MVP execution plan

## Phase 3 — source transcript

**Goal:** turn the uploaded Chinese-subtitled video into a reliable, editable, versioned source transcript. At the end of this phase a user must be able to correct OCR output without re-uploading or regenerating the proxy.

### 3.1 Workflow control and stage model

Implement the control plane before adding OCR work:

- Extend project status/stage projection for transcript processing.
- Add start, cancel, retry/restart, and progress-query commands with idempotent semantics.
- Define artifact/input fingerprints for extraction, OCR, consolidation, and transcript revisions.
- Add Temporal stage/activity boundaries and task queues without changing the Phase 2 ingestion contract.
- Persist enough execution metadata to recover after API or worker restart.

**Proof:** deterministic workflow tests cover duplicate start, activity retry, cancellation, worker restart/reconnect, terminal failure, and safe restart from existing artifacts.

### 3.2 Subtitle-region extraction

Produce normalized image/frame inputs for OCR:

- Add configurable subtitle-band geometry with safe defaults and bounded values.
- Sample/crop frames without decoding the entire video into durable images unnecessarily.
- Handle resolution/aspect-ratio differences and record the extraction configuration/version.
- Deduplicate identical or near-identical subtitle frames enough to avoid obvious repeated OCR work.
- Store retained extraction artifacts only when needed for review/debugging; keep lineage to the original video.

**Proof:** fixture tests cover 16:9/vertical inputs, one-line/two-line subtitles, subtitle changes near cuts, fade transitions, and videos with no detected subtitle content.

### 3.3 OCR provider and normalization

Add OCR behind the provider port:

- Implement the first approved local OCR adapter (RapidOCR/ONNX Runtime unless evaluation changes the decision).
- Return a strict internal schema containing text, confidence, frame/time provenance, provider/model version, and region metadata.
- Normalize Chinese punctuation/whitespace without silently rewriting semantic content.
- Classify malformed/provider failures into retryable and non-retryable errors.
- Keep the provider replaceable; workflow/domain code must not depend on RapidOCR-specific response objects.

**Proof:** provider contract tests plus a representative Chinese subtitle fixture set. No cloud OCR dependency is required for CI.

### 3.4 Temporal consolidation and stable segments

Convert frame-level OCR observations into subtitle segments:

- Merge repeated observations into stable time ranges.
- Preserve meaningful text changes and avoid merging adjacent different subtitles.
- Assign stable segment IDs independent of future translation/TTS attempts.
- Store raw OCR observations separately from the canonical source transcript revision.
- Create immutable transcript revisions with optimistic concurrency for edits.
- Define invalidation so editing one segment affects only downstream work that consumes the changed revision.

**Proof:** tests cover repeated frames, intermittent OCR misses, confidence changes, rapid subtitle changes, overlapping/two-line text, manual corrections, and revision conflicts.

### 3.5 Transcript review UI and end-to-end slice

Make the phase usable:

- Show proxy video and synchronized transcript segments.
- Allow source-text correction and timestamp adjustment within guarded bounds.
- Expose processing/progress/failure state and retry/cancel actions.
- Preserve unsaved-change safety and optimistic-concurrency conflicts.
- Add one deterministic fixture E2E covering upload -> proxy -> extraction -> OCR -> consolidated transcript -> manual correction -> persisted new revision.

**Phase 3 exit criteria:**

- A representative Chinese-subtitled fixture produces an editable transcript with stable segment IDs.
- A manual source correction creates a new revision without repeating upload/proxy generation.
- Restart/retry/cancel tests pass for the new durable stages.
- OCR/provider failures surface as actionable state instead of leaving a project permanently "processing".
- The complete Phase 3 path runs locally on the supported Apple Silicon host with no paid provider.

**Do not pull into Phase 3:** translation, tone controls, TTS, final rendering, arbitrary subtitle styling, or production observability expansion.

---

## Phase 4 — context, Vietnamese translation, and subtitle review

**Goal:** create high-quality, reviewable Vietnamese subtitle revisions from an approved source transcript while making paid-provider spend explicit and bounded.

### 4.1 Translation contract and cost guard

- Implement the provider-neutral structured translation port and first cloud LLM adapter.
- Pin provider/model/prompt-policy identifiers on every attempt.
- Add project token/cost estimation, hard budget ceiling, reservation, actual usage ledger, and failure reconciliation.
- Require explicit confirmation before any action that intentionally causes paid retranslation.
- Keep all paid-provider credentials isolated to the translation worker profile.

### 4.2 Context and glossary versions

- Extract reusable entities, names, relationships, terminology, and translation hints from the source transcript.
- Store immutable context/glossary versions separately from translated text.
- Support human correction of important names/terms before or after translation.
- Reuse unchanged context across tone changes; never feed old translated sentences back as source truth.

### 4.3 Semantic batching and translation

- Batch segments with enough neighboring context for coherent translation while retaining one-to-one segment identity.
- Carry rolling summary/context for longer videos without unbounded prompts.
- Validate strict structured output, segment coverage, ID integrity, and prohibited omissions/additions.
- Retry only bounded provider/validation failures; never create an uncontrolled paid retry loop.

### 4.4 Tone presets and consistency pass

- Implement the versioned `natural`, `funny`, `formal`, and `dramatic` catalog after its fixtures/default are approved.
- Treat tone as a server-owned policy, not arbitrary user prompt text.
- Detect terminology/name inconsistencies and surface them for review.
- Reject tone behavior that invents facts or materially changes meaning.

### 4.5 Translation editor and subtitle appearance preview

- Show source and Vietnamese text side by side with synchronized video playback.
- Edit translated segments into immutable translation revisions.
- Add the approved structured subtitle-style controls and HTML overlay preview.
- Style changes create style versions and must not call the translation provider or encode video.

**Phase 4 exit criteria:**

- The representative fixture can be translated, reviewed, corrected, and previewed in Vietnamese.
- Every paid attempt has model/prompt/input-version/usage/cost lineage.
- Budget ceilings and explicit paid-rerun confirmation are enforced.
- Tone changes reuse source/context but produce fresh translation attempts.
- Glossary/context corrections and translation revisions invalidate only appropriate descendants.
- Quality evaluation fixtures pass the agreed fidelity, consistency, tone, and structured-output thresholds.

**Do not pull into Phase 4:** TTS duration fitting or final video render.

---

## Phase 5 — Vietnamese speech and duration fitting

**Goal:** generate local Vietnamese speech for each approved translated segment and fit it to the available timing without uncontrolled loops or semantic damage.

### 5.1 TTS adapter and immutable attempts

- Finalize license/provenance/listening approval for the pinned VieNeu-TTS model and one preset voice.
- Implement TTS behind the speech provider port.
- Store immutable attempt metadata: input translation revision, model/voice version, generated audio artifact, measured duration, and status.
- Do not enable voice cloning.

### 5.2 Measurement and deterministic fitting

Apply bounded transformations in order:

1. generate speech,
2. trim allowed silence,
3. measure actual duration,
4. apply bounded speed-up where acceptable,
5. if still too long, request a local semantic rewrite through the pinned llama.cpp adapter,
6. regenerate and remeasure up to a hard attempt limit,
7. require human review if the segment still cannot fit safely.

Persist every attempt rather than overwriting failed/long versions.

### 5.3 Review and repair UI

- Preview generated speech per segment and in sequence.
- Show duration target, actual duration, transformation history, and fit status.
- Allow segment-level retry, translation correction, or manual approval where policy permits.
- Changing one translation segment must not regenerate unrelated speech.

**Phase 5 exit criteria:**

- Representative Vietnamese speech passes listening/content-integrity checks.
- All attempts terminate within deterministic retry/rewrite limits.
- Duration-fit policy tests cover short, normal, excessively long, provider failure, and manual-review cases.
- Segment edits trigger only necessary TTS descendants.
- Audio artifacts and attempt lineage survive worker/API restart.

---

## Phase 6 — rendering, validation, and download

**Goal:** render a reproducible localized video from frozen approved inputs and make the validated output downloadable.

### 6.1 Freeze render inputs

- Create immutable render manifests containing exact original/proxy reference, transcript revision, translation revision, speech attempts, style version, font artifacts, renderer version, and audio policy.
- Refuse rendering when required inputs are missing/unapproved/stale.

### 6.2 Subtitle and audio render

- Generate ASS/libass input only from validated structured style state and the approved font catalog.
- Render with isolated FFmpeg invocation and bounded resource/temp-disk policy.
- Implement the approved original-audio retain/reduce/remove behavior.
- Combine fitted Vietnamese speech according to segment timing without mutating source artifacts.

### 6.3 Output validation and selective rerender

- Probe output media and validate duration, streams, dimensions, codec expectations, non-empty audio/video, and render completion.
- Record validation reports and immutable output lineage.
- A style-only change rerenders without OCR/translation/TTS.
- A translation edit reruns only its dependent TTS plus render work.

### 6.4 Download and retention

- Publish validated output through tailnet-only signed download.
- Apply retention state to temporary/render artifacts without deleting lineage metadata prematurely.
- Expose render progress, failure, retry, and final download state in the UI.

**Phase 6 exit criteria — MVP feature complete:**

- At least one representative Chinese-subtitled fixture completes the full path: upload -> proxy -> OCR -> source review -> Vietnamese translation -> translation review -> TTS -> duration fit -> render -> validation -> download.
- The final output is reproducible from its frozen render manifest.
- Preview/render subtitle styling stays within the approved parity tolerance.
- Selective invalidation/rerender behavior is proven by automated tests.
- No final output is published before validation passes.

---

## Phase 7 — production hardening and limited pilot

**Goal:** make the feature-complete MVP safe and recoverable enough for a small owner-operated tailnet pilot. Do not use this phase to add major product features.

### 7.1 Operational visibility

- Add OpenTelemetry instrumentation for API/workflow/activity/provider/render boundaries.
- Provide local metrics/dashboard/alerts for queue depth, stage latency/failure, disk pressure, worker health, translation spend, and stuck workflows.
- Define short, explicit telemetry retention suitable for the single host.

### 7.2 Resilience and recovery

- Run worker/process/host restart tests during active workflows.
- Complete PostgreSQL, Temporal, Garage, and configuration backup/restore drills to an independent off-host destination.
- Document and test rollback/recovery procedures and artifact-lineage reconciliation.
- Establish disk admission/cleanup thresholds before large media work starts.

### 7.3 Security and supply chain

- Verify Tailscale exposure and confirm no database/Temporal/Garage-admin/internal API port is unintentionally reachable.
- Complete dependency/container scanning, SBOM review, secret handling, least-privilege runtime users, and upload/content abuse checks.
- Confirm Tailscale/provider/license usage matches the intended pilot context.

### 7.4 Performance and spend controls

- Benchmark supported video envelopes and establish realistic concurrency/admission limits for the actual host.
- Test load around API commands, signed uploads/downloads, worker queues, OCR, TTS, and rendering.
- Enforce project/user translation budgets and surface spend/usage clearly.

### 7.5 Deployment and pilot

- Automate single-host deployment/restart with durable volumes and pinned immutable images.
- Add deletion/retention operations and verify they remove requested user media while preserving only legally/operationally justified metadata.
- Run a small tailnet-only pilot using representative real videos and collect OCR/translation/TTS/render failure cases.

**Phase 7 exit criteria — production-ready for limited pilot:**

- No unresolved critical security, data-loss, recovery, or uncontrolled-spend finding remains.
- Backup restore and rollback drills succeed from written runbooks.
- Declared host limits and queue/admission controls are backed by measured results.
- The complete product workflow can recover from process/worker restart without corrupting project state.
- Explicit launch approval for the limited pilot is recorded.

---

## Definition of MVP done

The MVP is done when a permitted tailnet user can upload a Chinese-subtitled video, correct the extracted source transcript, obtain and edit a Vietnamese translation, generate and review fitted Vietnamese speech, choose an approved subtitle style, render the final localized video, and download a validated output — with durable restart/retry behavior, versioned lineage, bounded paid-provider cost, selective reprocessing, and recoverable local storage.

Anything beyond that outcome — collaboration, arbitrary prompts/fonts, voice cloning, public internet access, Kubernetes, distributed scaling, billing/subscriptions, or broad multi-user product features — is explicitly post-MVP unless a new roadmap revision approves it.