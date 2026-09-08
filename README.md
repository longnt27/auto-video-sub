# Auto Video Sub

> Self-hosted Chinese-to-Vietnamese video localization with OCR, context-aware translation, Vietnamese TTS, subtitle styling, and final video rendering.

[![CI/CD](https://github.com/longnt27/auto_video_sub/actions/workflows/ci.yml/badge.svg)](https://github.com/longnt27/auto_video_sub/actions/workflows/ci.yml)

Auto Video Sub is a local-first web application for turning Chinese videos with ordinary bottom-region subtitles into reviewable Vietnamese-localized videos.

The workflow is intentionally human-in-the-loop: the app automates OCR, translation, speech fitting, and rendering while keeping source text, translation, timing, speech, and subtitle appearance reviewable before export.

## What it can do

- Upload and validate supported video files.
- Generate a lightweight browser playback proxy.
- Extract Chinese subtitles from a configurable lower-frame region with local RapidOCR.
- Review and correct the Chinese source transcript without re-uploading the video.
- Build story-wide context, names, entities, relationships, and glossary hints.
- Translate Chinese subtitles to Vietnamese with a user-selected cloud AI provider.
- Configure **OpenAI, DeepSeek, or OpenRouter directly in the app**.
- Choose a project-wide translation tone: `natural`, `funny`, `formal`, or `dramatic`.
- Review and edit Vietnamese translations before approval.
- Preview structured subtitle styles in the browser.
- Generate Vietnamese speech locally with VieNeu-TTS v3 Turbo.
- Fit speech into subtitle timing with trimming, bounded speed-up, and optional local rewriting.
- Render subtitles and Vietnamese speech into a final H.264/AAC MP4 with FFmpeg/libass.
- Retain, reduce, or remove original audio during rendering.
- Validate the rendered output before making it downloadable.
- Preserve immutable revisions and artifact lineage so small edits do not require rerunning the whole pipeline.

## Current status

| Stage | Status |
| --- | --- |
| Project creation, upload, validation, proxy | Complete |
| Chinese subtitle OCR and transcript review | Complete |
| Context-aware Chinese → Vietnamese translation | Complete |
| In-app AI provider configuration | Complete |
| Vietnamese translation review and subtitle styling | Complete |
| Local Vietnamese TTS and duration fitting | Complete |
| Final render, validation, and download | Complete |
| Production hardening and operational polish | In progress |

The current deployment is optimized for **single-user self-hosting**, especially on Apple Silicon.

## Processing flow

```text
Video upload
    ↓
Validation + proxy generation
    ↓
Subtitle-region extraction
    ↓
Chinese OCR
    ↓
Source transcript review
    ↓
Context / glossary extraction
    ↓
Chinese → Vietnamese translation
    ↓
Translation + subtitle-style review
    ↓
Vietnamese TTS + duration fitting
    ↓
FFmpeg subtitle/audio render
    ↓
Output validation
    ↓
Download localized MP4
```

## Tech stack

| Area | Technology |
| --- | --- |
| Web UI | Next.js, React, TypeScript |
| API | FastAPI, Python |
| Durable workflows | Temporal |
| Database | PostgreSQL |
| Object storage | Garage / S3-compatible storage |
| Media processing | FFmpeg, ffprobe, libass |
| OCR | RapidOCR / ONNX Runtime |
| Translation | OpenAI-compatible Responses API: OpenAI, DeepSeek, OpenRouter |
| Vietnamese TTS | VieNeu-TTS v3 Turbo / ONNX |
| Optional local rewrite | llama.cpp-compatible HTTP endpoint |
| Observability | OpenTelemetry, Prometheus, Jaeger, Grafana |
| Local deployment | Docker Compose |

## Requirements

For normal personal use:

- Git
- Docker with Docker Compose
- at least **6 GiB of free disk space** for the base stack, plus source/output media
- an API key for at least one supported translation provider
- a local VieNeu-TTS v3 Turbo model snapshot
- `NotoSans-Regular.ttf` for deterministic final subtitle rendering

Apple Silicon is the primary local deployment target. Application images remain multi-architecture where practical.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/longnt27/auto_video_sub.git
cd auto_video_sub
```

### 2. Create local configuration

```bash
cp .env.example .env
```

`.env` now contains infrastructure/runtime configuration only. **Do not put translation provider API keys, models, or token pricing in it.** Those are selected from the application UI.

### 3. Install the local VieNeu TTS model

By default Compose expects the model at:

```text
.local/models/vieneu/
```

Set the reviewed model and voice in `.env`:

```dotenv
TTS_MODEL_HOST_PATH=./.local/models/vieneu
TTS_MODEL_REVISION=<exact-model-revision>
TTS_VOICE_ID=<preset-voice-id>
TTS_PRECISION=fp32
```

`TTS_PRECISION` supports `fp32` and `int8`.

The runtime deliberately does not download a floating TTS model at startup. Missing model, revision, or voice configuration fails closed.

### 4. Install the render font

Place Noto Sans Regular at:

```text
.local/fonts/NotoSans-Regular.ttf
```

Calculate its SHA-256 checksum on macOS:

```bash
shasum -a 256 .local/fonts/NotoSans-Regular.ttf
```

Then set:

```dotenv
RENDER_FONT_HOST_PATH=./.local/fonts/NotoSans-Regular.ttf
RENDER_FONT_FILENAME=NotoSans-Regular.ttf
RENDER_FONT_CHECKSUM_SHA256=<sha256>
```

### 5. Optional: configure local Vietnamese rewriting

If speech still cannot fit after silence trimming and bounded speed-up, the app can use a local llama.cpp-compatible endpoint for a shorter meaning-preserving Vietnamese rewrite.

```dotenv
REWRITE_PROVIDER_ENDPOINT=<local-http-endpoint>
REWRITE_PROVIDER_MODEL=<model-name>
REWRITE_PROVIDER_MODEL_REVISION=<model-revision>
```

Without it, unresolved duration failures are surfaced for manual review.

## Running the application

Start the full localization stack, including the translation worker:

```bash
docker compose \
  --env-file .env \
  -f deploy/compose.yaml \
  --profile translation \
  up -d --build --wait
```

Open:

- Web app: `http://127.0.0.1:3100`
- AI settings: `http://127.0.0.1:3100/settings`
- API: `http://127.0.0.1:8000`

The browser-facing services bind to loopback by default.

### Configure the translation provider in the app

Before starting translation, open **AI settings** and choose a provider:

| Provider | Configuration |
| --- | --- |
| OpenAI | API key + model ID |
| DeepSeek | API key + model ID |
| OpenRouter | API key + model ID |

The app provides model suggestions but accepts another valid model ID supported by the selected provider.

The API key is written to the private Docker `provider-config` volume shared only by the API and translation worker. The backend returns only a masked key hint to the browser; it never echoes the complete key back through the settings API.

Changing the active provider affects new translation runs. Each run pins its provider and model in the translation policy so lineage remains deterministic.

### Cost and usage reporting

The app no longer calculates monetary cost from prices stored in `.env`.

- Every provider response records its returned token usage.
- If the provider returns an exact monetary charge in its response, that amount is recorded as provider-reported cost.
- If the provider does **not** expose an exact per-response monetary cost, the app shows monetary cost as unavailable instead of inventing a number from a local pricing table.

OpenRouter currently exposes request cost through its usage payload when requested. OpenAI and DeepSeek provide token usage in the Responses API but do not provide an exact dollar charge for each response, so the app keeps their monetary cost unavailable.

## Useful runtime commands

Check services:

```bash
docker compose --env-file .env -f deploy/compose.yaml --profile translation ps
```

Follow logs:

```bash
docker compose --env-file .env -f deploy/compose.yaml --profile translation logs -f
```

Stop while preserving data and provider settings:

```bash
docker compose --env-file .env -f deploy/compose.yaml --profile translation down
```

> `docker compose down -v` deletes PostgreSQL, object-storage data, **and the saved AI provider configuration/API keys**. Use it only for an intentional local reset.

## Using the app

### 1. Create a project and upload a video

Create a project, upload the source video, and wait for validation and proxy generation.

Default local admission limits:

| Limit | Default |
| --- | ---: |
| Maximum file size | 2 GiB |
| Maximum duration | 3 hours |
| Maximum resolution | 3840 × 2160 |
| Maximum frame rate | 60 fps |
| Maximum streams | 16 |
| Supported declarations | MP4, QuickTime, Matroska, WebM |

### 2. Extract Chinese subtitles

Start source-transcript processing after the proxy is ready. The default OCR region targets ordinary hard-coded subtitles near the bottom of the frame.

### 3. Review the source transcript

Correct OCR text or timing where necessary, then approve the source transcript. Corrections create immutable revisions and do not require another upload.

### 4. Build translation context

The app extracts story context such as names, places, organizations, relationships, recurring terminology, and ambiguities. Review important context before translation batches continue.

### 5. Translate to Vietnamese

Select a tone:

- `natural` — neutral conversational Vietnamese
- `funny` — playful where the source supports it
- `formal` — polished and restrained
- `dramatic` — more emotionally vivid without inventing plot facts

The app shows the approximate token scope and requires explicit confirmation before paid translation begins. It does **not** fabricate a currency estimate when the provider has not reported an actual charge yet.

### 6. Review translation and subtitle style

Review Chinese and Vietnamese segments side by side, edit translations as needed, and configure the project-wide subtitle appearance.

Style preview is browser-side and does not trigger another translation or video render.

### 7. Generate Vietnamese speech

For each segment the app can:

1. synthesize Vietnamese speech with VieNeu,
2. trim edge silence,
3. measure actual duration,
4. apply bounded speed-up when needed,
5. optionally request a shorter local rewrite,
6. surface unresolved segments for manual review.

### 8. Render and download

Choose how to treat original audio: retain, reduce, or remove. FFmpeg burns the approved Vietnamese subtitles, mixes audio, validates the output, and exposes the final MP4 only after validation succeeds.

## Observability

Start the application with Prometheus, Jaeger, and Grafana:

```bash
docker compose \
  --env-file .env \
  -f deploy/compose.yaml \
  -f deploy/compose.observability.yaml \
  --profile translation \
  up -d --build --wait
```

Default endpoints:

- Grafana: `http://127.0.0.1:3200`
- Prometheus: `http://127.0.0.1:9090`
- Jaeger: `http://127.0.0.1:16686`

## Development

Pinned host toolchain:

- Node.js `22.22.x`
- pnpm `11.15.x`
- Python `3.12.13`
- uv `0.11.3`
- FFmpeg / ffprobe

Bootstrap and run normal checks:

```bash
make bootstrap
make check
```

Integration tests:

```bash
make test-integration
```

Build:

```bash
make build
```

Useful targets:

| Command | Purpose |
| --- | --- |
| `make format` | Format Python and TypeScript |
| `make lint` | Run linters |
| `make typecheck` | Run Python and TypeScript type checks |
| `make test` | Run unit/component tests |
| `make test-integration` | Run PostgreSQL, object-store, and migration integration tests |
| `make stack-config` | Validate base Compose topology |
| `make stack-up` | Start the safe base stack |
| `make stack-smoke` | Smoke-test the base local stack |
| `make stack-smoke-phase2` | Exercise upload → validation → proxy → playback |
| `make stack-down` | Stop the base stack while preserving volumes |

Normal CI never calls a paid translation provider.

## Project structure

```text
apps/
  api/          FastAPI HTTP application
  web/          Next.js browser UI
  worker/       Temporal workers and media/AI activities

packages/
  domain/       Pure domain rules and entities
  application/  Use cases and provider ports
  infrastructure/
                PostgreSQL, storage, workflow, runtime settings, telemetry
  providers/    OCR, translation, TTS, FFmpeg, rewrite adapters

db/             Alembic migrations
deploy/         Docker Compose and observability configuration
docs/           Architecture, ADRs, workflows, policies, roadmap
scripts/        Smoke tests, integration checks, local benchmarks
```

## Scope

The MVP targets videos with ordinary Chinese subtitles in a predictable lower-frame region. It does not currently target arbitrary scene-text replacement, inpainting, lip synchronization, voice cloning, DRM ingestion, live streaming, public sharing, multi-user collaboration, or high-availability deployment.

That narrow scope is intentional: make the normal Chinese-subtitle → Vietnamese-localized-video workflow reliable before building a small media empire nobody asked for.

## License and media rights

Use only media, fonts, models, and provider services that you are authorized to use. This repository does not grant rights to third-party video content, model weights, fonts, or cloud-provider services.
