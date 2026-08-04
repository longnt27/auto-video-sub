#!/bin/sh
set -eu

web_url=${APP_BASE_URL:-http://127.0.0.1:3100}
temporary_directory=$(mktemp -d "${TMPDIR:-/tmp}/auto-video-sub-smoke.XXXXXX")
trap 'rm -rf "$temporary_directory"' EXIT HUP INT TERM

fixture_path="${temporary_directory}/phase2-smoke.mp4"
ffmpeg \
  -nostdin \
  -hide_banner \
  -loglevel error \
  -f lavfi \
  -i "testsrc2=size=640x360:rate=24:duration=1" \
  -f lavfi \
  -i "sine=frequency=440:sample_rate=48000:duration=1" \
  -c:v libx264 \
  -pix_fmt yuv420p \
  -c:a aac \
  -shortest \
  -movflags +faststart \
  -y \
  "$fixture_path"

uv run python scripts/smoke_phase2.py "$web_url" "$fixture_path"
