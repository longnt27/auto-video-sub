#!/usr/bin/env bash
set -euo pipefail

MODEL_HOST_PATH="${VIENEU_MODEL_HOST_PATH:?set VIENEU_MODEL_HOST_PATH to the pinned VieNeu snapshot directory}"
MODEL_REVISION="${VIENEU_MODEL_REVISION:?set VIENEU_MODEL_REVISION to the exact reviewed model revision}"
VOICE_ID="${VIENEU_VOICE_ID:?set VIENEU_VOICE_ID to the preset voice under review}"
PRECISION="${VIENEU_PRECISION:-int8}"
THREADS="${VIENEU_THREADS:-0}"
OUTPUT_DIR="${1:-reports/phase5-promotion}"
IMAGE="${PHASE5_BENCHMARK_IMAGE:-auto-video-sub-worker:phase5-promotion}"

mkdir -p "$OUTPUT_DIR"
MODEL_ABS="$(cd "$MODEL_HOST_PATH" && pwd)"
OUTPUT_ABS="$(cd "$OUTPUT_DIR" && pwd)"

echo "Building linux/arm64 worker image..."
docker build \
  --platform linux/arm64 \
  --file apps/worker/Dockerfile \
  --tag "$IMAGE" \
  .

echo "Running VieNeu promotion fixtures with container networking disabled..."
docker run --rm \
  --platform linux/arm64 \
  --network none \
  --entrypoint python \
  --volume "$MODEL_ABS:/models/vieneu:ro" \
  --volume "$OUTPUT_ABS:/reports" \
  "$IMAGE" \
  -m auto_video_sub_worker.phase5_promotion \
  --model-root /models/vieneu \
  --model-revision "$MODEL_REVISION" \
  --voice "$VOICE_ID" \
  --precision "$PRECISION" \
  --threads "$THREADS" \
  --output /reports \
  --require-arm64

echo
echo "Benchmark evidence: $OUTPUT_ABS/benchmark.json"
echo "Listening checklist: $OUTPUT_ABS/LISTENING_REVIEW.md"
