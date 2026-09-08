# Auto Video Sub

> Self-hosted Chinese-to-Vietnamese video localization with OCR, context-aware translation, Vietnamese TTS, subtitle styling, and final video rendering.

[![CI/CD](https://github.com/longnt27/auto_video_sub/actions/workflows/ci.yml/badge.svg)](https://github.com/longnt27/auto_video_sub/actions/workflows/ci.yml)

Auto Video Sub is a local-first web application for turning Chinese videos with ordinary bottom-region subtitles into reviewable Vietnamese-localized videos.

The workflow is intentionally human-in-the-loop: the app automates the expensive and repetitive work, while still letting you correct OCR, translation, timing, speech, and subtitle appearance before producing the final file.

## What it can do

- Upload and validate supported video files.
- Generate a lightweight browser playback proxy.
- Extract Chinese subtitles from a configurable lower-frame region.
- Run local OCR with RapidOCR and consolidate detections into timestamped segments.
- Review and correct the Chinese source transcript without re-uploading the video.
- Build story-wide context, names, entities, relationships, and glossary hints.
- Translate Chinese subtitles to Vietnamese with a cloud LLM.
- Use project-wide translation tones: `natural`, `funny`, `formal`, or `dramatic`.
- Review and edit Vietnamese translations before approval.
- Preview structured subtitle styles in the browser.
- Generate Vietnamese speech locally with VieNeu-TTS v3 Turbo.
- Fit speech into subtitle timing using silence trimming, bounded speed-up, and optional local rewriting.
- Render subtitles and Vietnamese speech into the final video with FFmpeg/libass.
- Retain, reduce, or remove the original audio during rendering.
- Validate the rendered output before making it downloadable.
- Preserve immutable revisions and artifact lineage so selective edits do not require rerunning the entire pipeline.

## Current status

Implementation through the final render/export workflow is complete. The application currently includes:

| Stage | Status |
| --- | --- |
| Project creation, upload, validation, proxy | Complete |
| Chinese subtitle OCR and transcript review | Complete |
| Context-aware Chinese → Vietnamese translation | Complete |
| Vietnamese translation review and subtitle styling | Complete |
| Local Vietnamese TTS and duration fitting | Complete |
| Final render, validation, and download | Complete |
| Production hardening and operational polish | In progress |

The project is currently optimized for a **single-user, self-hosted deployment**, especially on Apple Silicon.

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
| Translation | OpenAI Responses API |
| Vietnamese TTS | VieNeu-TTS v3 Turbo / ONNX |
| Optional local rewrite | llama.cpp-compatible HTTP endpoint |
| Observability | OpenTelemetry, Prometheus, Jaeger, Grafana |
| Local deployment | Docker Compose |

## Requirements

### Recommended: Docker deployment

For normal personal use you only need:

- Git
- Docker with Docker Compose
- at least **6 GiB of free disk space** for the base stack, plus space for uploaded videos and generated artifacts
- an OpenAI API key for translation
- a local VieNeu-TTS v3 Turbo model snapshot
- `NotoSans-Regular.ttf` for deterministic final subtitle rendering

Apple Silicon is the primary local deployment target, but the application images are built for both `linux/amd64` and `linux/arm64`.

### Optional: host development tools

If you want to run services or checks outside Docker, use the pinned development toolchain:

- Node.js `22.22.x`
- pnpm `11.15.x`
- Python `3.12.13`
- uv `0.11.3`
- FFmpeg / ffprobe

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/longnt27/auto_video_sub.git
cd auto_video_sub
```

### 2. Create your local configuration

```bash
cp .env.example .env
```

The committed `.env.example` contains safe development defaults. Put real credentials and local model paths only in `.env`.

### 3. Configure translation

Edit `.env` and provide at least:

```dotenv
TRANSLATION_PROVIDER_NAME=openai
TRANSLATION_PROVIDER_BASE_URL=https://api.openai.com/v1/responses
TRANSLATION_PROVIDER_API_KEY=<your-api-key>
TRANSLATION_PROVIDER_MODEL=<your-model>

TRANSLATION_INPUT_COST_MICROS_PER_MILLION_TOKENS=<model-input-rate>
TRANSLATION_OUTPUT_COST_MICROS_PER_MILLION_TOKENS=<model-output-rate>
DEFAULT_TRANSLATION_BUDGET_MICROS=<maximum-project-budget>
```

Translation is the only intentionally paid runtime dependency. The app requires explicit confirmation before starting paid translation work.

Keep the model pricing values aligned with the model you actually use. They are used for cost estimation and budget enforcement; the repository intentionally does not hard-code provider pricing.

### 4. Install the local VieNeu TTS model

By default the Compose stack expects the model at:

```text
.local/models/vieneu/
```

Point `TTS_MODEL_HOST_PATH` somewhere else if you already keep the model in another directory.

The configured model snapshot must contain the VieNeu ONNX assets expected by the runtime, including the appropriate ONNX directory and codec assets. Then set:

```dotenv
TTS_MODEL_HOST_PATH=./.local/models/vieneu
TTS_MODEL_REVISION=<exact-model-revision>
TTS_VOICE_ID=<preset-voice-id>
TTS_PRECISION=fp32
```

`TTS_PRECISION` supports `fp32` and `int8`.

The runtime deliberately does **not** download a floating model at startup. A missing model, revision, or voice fails closed instead of silently changing TTS behavior.

### 5. Install the render font

Place a licensed Noto Sans Regular font file at:

```text
.local/fonts/NotoSans-Regular.ttf
```

Then calculate its SHA-256 checksum on macOS:

```bash
shasum -a 256 .local/fonts/NotoSans-Regular.ttf
```

Copy the checksum into `.env`:

```dotenv
RENDER_FONT_HOST_PATH=./.local/fonts/NotoSans-Regular.ttf
RENDER_FONT_FILENAME=NotoSans-Regular.ttf
RENDER_FONT_CHECKSUM_SHA256=<sha256>
```

The checksum is pinned into render metadata so a final output can be reproduced from the same inputs.

### 6. Optional: configure local Vietnamese rewriting

When synthesized speech is still too long after trimming and bounded speed-up, the application can ask a local llama.cpp-compatible service for a shorter meaning-preserving Vietnamese rewrite.

```dotenv
REWRITE_PROVIDER_ENDPOINT=<local-http-endpoint>
REWRITE_PROVIDER_MODEL=<model-name>
REWRITE_PROVIDER_MODEL_REVISION=<model-revision>
```

This is optional. If it is not configured, segments that cannot fit safely are surfaced for manual review instead.

## Running the application

For the complete localization workflow, including the paid translation worker, run:

```bash
docker compose \
  --env-file .env \
  -f deploy/compose.yaml \
  --profile translation \
  up -d --build --wait
```

Then open:

- Web app: `http://127.0.0.1:3100`
- API: `http://127.0.0.1:8000`

The local development stack binds the browser-facing services to loopback, so it is not exposed publicly by default.

Check running services with:

```bash
docker compose \
  --env-file .env \
  -f deploy/compose.yaml \
  --profile translation \
  ps
```

Follow logs with:

```bash
docker compose \
  --env-file .env \
  -f deploy/compose.yaml \
  --profile translation \
  logs -f
```

Stop the stack without deleting stored data:

```bash
docker compose \
  --env-file .env \
  -f deploy/compose.yaml \
  --profile translation \
  down
```

> **Warning:** `docker compose down -v` deletes the persistent PostgreSQL and object-storage volumes. Do not use it unless you intentionally want to wipe local application data.

## Using the app

### 1. Create a project

Open `http://127.0.0.1:3100`, create a project, and select the video you want to localize.

### 2. Upload the source video

The browser uploads the original video to the local S3-compatible object store. The backend then validates the media and generates a browser-friendly proxy.

Default local admission limits are:

| Limit | Default |
| --- | ---: |
| Maximum file size | 2 GiB |
| Maximum duration | 3 hours |
| Maximum resolution | 3840 × 2160 |
| Maximum frame rate | 60 fps |
| Maximum streams | 16 |
| Supported declarations | MP4, QuickTime, Matroska, WebM |

### 3. Extract Chinese subtitles

Start source transcript processing after the proxy is ready.

The default OCR region covers the lower part of the frame, where ordinary hard-coded Chinese subtitles are expected. Adjust the subtitle region or sampling interval when the source video uses a different layout.

The application samples the configured region, runs RapidOCR locally, and consolidates repeated observations into timestamped source segments.

### 4. Review the source transcript

Watch the proxy while reviewing the extracted Chinese subtitle segments.

Correct OCR text or timing where necessary, then approve the source transcript. Corrections create new immutable revisions; they do not require another upload or proxy generation.

### 5. Build translation context

The app extracts story-wide context such as names, places, organizations, relationships, recurring terminology, and ambiguous entities.

Review important context or glossary entries before translation when consistency matters.

### 6. Translate to Vietnamese

Choose one translation tone:

- `natural` — default, neutral Vietnamese localization
- `funny` — preserves meaning while allowing humor already supported by the source
- `formal` — more formal wording and register
- `dramatic` — stronger expression without inventing facts or plot

The UI shows the estimated paid scope before translation. Confirm it explicitly to start the translation worker.

### 7. Review translation and subtitle style

Review Chinese and Vietnamese segments side by side and correct any translation you do not like.

You can also configure the project-wide subtitle appearance, including:

- font size
- text color
- background color and opacity
- outline
- shadow
- alignment within the supported MVP policy

Style preview happens in the browser and does not trigger translation or video encoding.

### 8. Generate Vietnamese speech

Start speech generation after approving the Vietnamese translation.

For each segment the app can:

1. synthesize Vietnamese speech with VieNeu,
2. trim edge silence,
3. measure the actual duration,
4. apply bounded speed-up when needed,
5. optionally request a shorter local rewrite,
6. surface unresolved segments for manual review.

Review any segment marked as needing attention before final rendering.

### 9. Render the localized video

Once all required speech segments are ready, choose how to treat the original audio:

- retain it at full volume,
- reduce it under the Vietnamese speech,
- remove it.

Start the render. FFmpeg burns the approved Vietnamese subtitles, mixes the audio tracks, and creates the final H.264/AAC output.

The backend validates the rendered media before exposing the download link.

### 10. Download the result

After validation succeeds, download the final localized MP4 from the render review screen.

## Observability

A local OpenTelemetry stack is available for runtime inspection.

Start the application with Prometheus, Jaeger, and Grafana:

```bash
docker compose \
  --env-file .env \
  -f deploy/compose.yaml \
  -f deploy/compose.observability.yaml \
  --profile translation \
  up -d --build --wait
```

Default local endpoints:

- Grafana: `http://127.0.0.1:3200`
- Prometheus: `http://127.0.0.1:9090`
- Jaeger: `http://127.0.0.1:16686`

## Development

Install the pinned host dependencies, then bootstrap the workspace:

```bash
make bootstrap
```

Run all normal static checks and tests:

```bash
make check
```

Run PostgreSQL, Garage, and migration integration tests:

```bash
make test-integration
```

Build the web application:

```bash
make build
```

Run individual processes after their dependencies are available:

```bash
make api
make worker
make web
```

Useful repository targets:

| Command | Purpose |
| --- | --- |
| `make format` | Format Python and TypeScript |
| `make lint` | Run linters |
| `make typecheck` | Run Python and TypeScript type checks |
| `make test` | Run unit/component tests |
| `make test-integration` | Run database, object-store, and migration integration tests |
| `make stack-config` | Validate the base Compose topology |
| `make stack-up` | Start the safe base stack using committed development defaults |
| `make stack-smoke` | Smoke-test the base local stack |
| `make stack-smoke-phase2` | Exercise upload → validation → proxy generation → playback |
| `make stack-down` | Stop the base stack while preserving volumes |

> The `make stack-*` convenience targets intentionally use the committed `.env.example` development defaults. For the real translation/TTS/render configuration in your personal `.env`, use the explicit Docker Compose commands shown above.

## Testing and CI

GitHub Actions currently verifies:

- Python formatting with Ruff
- Python linting
- mypy type checking
- pytest with coverage
- PostgreSQL / Garage / Alembic integration tests
- TypeScript formatting and linting
- TypeScript type checking
- web tests
- production Next.js build
- Docker Compose configuration
- multi-architecture API, web, and worker image builds on `main`

Normal CI never makes a paid translation-provider call.

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
                PostgreSQL, storage, workflow, and telemetry adapters
  providers/    OCR, translation, TTS, FFmpeg, and rewrite adapters

db/             Alembic migrations
deploy/         Docker Compose and observability configuration
docs/           Architecture, ADRs, workflows, policies, and roadmap
scripts/        Smoke tests, integration checks, and local benchmarks
```

The backend follows a modular-monolith design. OCR, translation, TTS, rendering, storage, and workflow engines remain behind explicit ports so provider-specific code does not leak into the core domain.

## Documentation

For deeper implementation details:

- [`docs/product-overview.md`](docs/product-overview.md) — product scope and complete workflow
- [`docs/architecture.md`](docs/architecture.md) — system architecture
- [`docs/workflow-state-machine.md`](docs/workflow-state-machine.md) — durable workflow design
- [`docs/translation-context.md`](docs/translation-context.md) — context and translation strategy
- [`docs/duration-fitting.md`](docs/duration-fitting.md) — speech duration fitting policy
- [`docs/subtitle-styling.md`](docs/subtitle-styling.md) — subtitle style contract
- [`docs/deployment-strategy.md`](docs/deployment-strategy.md) — deployment model
- [`docs/observability.md`](docs/observability.md) — telemetry stack
- [`docs/testing-strategy.md`](docs/testing-strategy.md) — test strategy
- [`docs/roadmap.md`](docs/roadmap.md) — implementation roadmap and current phase
- [`docs/final-mvp-acceptance.md`](docs/final-mvp-acceptance.md) — final end-to-end acceptance checklist

## Scope

This MVP is deliberately narrow. It is designed for videos with ordinary Chinese subtitles in a predictable lower-frame region.

It does **not** currently target:

- arbitrary scene-text replacement
- image/video inpainting
- lip synchronization
- voice cloning
- speaker diarization guarantees
- DRM-protected ingestion
- live streaming
- public sharing
- multi-user collaboration
- high-availability or multi-region deployment

That narrow scope is intentional: the goal is to make the normal Chinese-subtitle → Vietnamese-localized-video workflow reliable before turning the project into a small media empire nobody asked for.

## License and media rights

Use only media, fonts, models, and provider services that you are authorized to use. The repository does not grant rights to third-party video content, model weights, fonts, or cloud-provider services.
