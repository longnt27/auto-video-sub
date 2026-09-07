# Phase 3 source transcript contract

Phase 3 turns a validated media asset into an editable, versioned Chinese source transcript. It does not perform translation, TTS, styling, or final rendering.

## Preconditions

- Caller owns the project and media asset.
- Media is in `ready` state with validated probe metadata and an immutable original artifact.
- Transcript processing uses the configured bottom subtitle region. Default region is x `0.05..0.95`, y `0.68..0.98`, sampled every `400 ms`.

## API

All routes are under `/v1/projects/{project_id}/media/{media_asset_id}` and use normal project ownership checks.

| Method | Route | Behavior |
|---|---|---|
| POST | `/transcript/start` | Start or idempotently rejoin `source-transcript-v1` using a validated region configuration. |
| GET | `/transcript` | Return processing/review status and current source revisions for stable subtitle segment IDs. |
| POST | `/transcript/segments/{segment_id}/revisions` | Append a user correction with optimistic `expected_version`; never mutates prior revisions. |
| POST | `/transcript/approve` | Approve the exact loaded transcript version and signal the waiting Temporal workflow. Repeating approval safely re-sends the signal. |
| POST | `/transcript/cancel` | Cancel active processing and mark the transcript cancelled. Repeating cancellation is safe. |
| POST | `/transcript/restart` | Restart only failed or cancelled processing using the stored region configuration and reusable durable inputs. |

Transcript status values are `processing`, `waiting_for_review`, `approved`, `failed`, and `cancelled` after creation. A transcript is editable only while `waiting_for_review`.

The browser always renders the transcript review surface, but per-segment correction controls appear only after OCR has published segments. The initial empty state therefore documents edit/revision behavior without rendering a fake segment editor.

## Durable workflow

Workflow ID is `source-transcript-v1/{media_asset_id}`. It runs on the local-AI queue and performs:

1. `extract-and-ocr-source-subtitles-v1`: download the immutable original into an activity temp directory, sample/crop the configured region with FFmpeg, run local RapidOCR, and persist normalized raw OCR observations.
2. `consolidate-source-transcript-v1`: merge repeated observations into timestamped segments, assign backend-owned stable IDs, publish initial immutable OCR source revisions, and move the transcript to `waiting_for_review`.
3. Wait for `transcript-approved-v1`; human corrections occur through the API while the workflow is waiting.

OCR and consolidation have bounded retries and persisted stage executions with canonical input fingerprints. Activity heartbeats make worker loss/cancellation observable. A retry after transcript publication reads the already committed result instead of regenerating segment identities.

## OCR boundary

The first adapter is RapidOCR 3.9.x with ONNX Runtime CPU. Provider-specific objects stay inside `packages/providers`. The application receives only text, confidence, provider identifier, and pinned model-policy identifier. OCR runs locally; no cloud OCR call or paid provider is introduced.

Sampled image files are ephemeral activity inputs and are deleted with the activity temp directory. Durable evidence is the normalized OCR observation set in PostgreSQL. No project upload can select an OCR executable or model path.

The checked-in `uv.lock` is regenerated with the repository-pinned uv 0.11.3 and verified with `uv sync --all-packages --all-groups --frozen`, so the local OCR runtime is reproducible in CI and deployment.

## Persistence and editing

Phase 3 adds:

- `transcript_states`: workflow/review projection, region config, version, error state;
- `ocr_observations`: frame-time text/confidence/provider/model evidence;
- `subtitle_segments`: stable backend-owned ID, ordinal, authoritative microsecond timing, optimistic version;
- `source_revisions`: immutable Chinese text revisions with origin, confidence/editor, and parent lineage.

Editing a segment creates a new `source_revisions` row and advances only that segment/current transcript version. It does not regenerate the proxy, rerun OCR, or alter timestamps implicitly.

## Error and recovery rules

Provider/media/domain failures map to stable `OCR_*`, `MEDIA_*`, `TRANSCRIPT_*`, or existing structured error codes. Exhausted processing moves the transcript to `failed`; the user may restart. Cancelled work may restart. Approved transcripts cannot be cancelled or restarted by Phase 3 commands.

No ordinary Phase 3 test invokes the paid translation provider.

## Exit verification

The final Phase 3 branch head must pass normal repository CI: frozen dependency installs, Python format/lint/type/tests plus PostgreSQL/Garage/migration integration, web format/lint/type/tests/build, and Compose validation.
