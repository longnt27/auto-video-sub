#!/bin/sh
set -eu

project_name=auto-video-sub-integration
database_url=postgresql+asyncpg://app:app@127.0.0.1:55432/auto_video_sub
compose_files="-f deploy/compose.integration.yaml"

cleanup() {
  docker compose -p "$project_name" --env-file .env.example $compose_files down --volumes
}
trap cleanup EXIT INT TERM

docker compose -p "$project_name" --env-file .env.example $compose_files up -d --wait
DATABASE_URL="$database_url" UV_CACHE_DIR=.cache/uv uv run alembic -c db/alembic.ini upgrade head
DATABASE_URL="$database_url" UV_CACHE_DIR=.cache/uv uv run alembic -c db/alembic.ini downgrade base
DATABASE_URL="$database_url" UV_CACHE_DIR=.cache/uv uv run alembic -c db/alembic.ini upgrade head
DATABASE_URL="$database_url" UV_CACHE_DIR=.cache/uv uv run alembic -c db/alembic.ini check
TEST_DATABASE_URL="$database_url" \
  TEST_OBJECT_STORE_ENDPOINT=http://127.0.0.1:55900 \
  TEST_OBJECT_STORE_BUCKET=auto-video-sub-integration \
  UV_CACHE_DIR=.cache/uv \
  uv run pytest -m integration
