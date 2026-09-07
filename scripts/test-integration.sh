#!/bin/sh
set -eu

project_name=auto-video-sub-integration
database_url=postgresql+asyncpg://app:app@127.0.0.1:55432/auto_video_sub
compose_files="-f deploy/compose.integration.yaml"

cleanup() {
  docker compose -p "$project_name" --env-file .env.example $compose_files down --volumes
}
trap cleanup EXIT INT TERM

check_database() {
  TEST_DATABASE_URL="$database_url" UV_CACHE_DIR=.cache/uv uv run python - <<'PY'
import asyncio
import os

import asyncpg


async def main() -> None:
    url = os.environ["TEST_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    try:
        connection = await asyncpg.connect(url, timeout=2)
        try:
            await connection.execute("SELECT 1")
        finally:
            await connection.close()
    except Exception:
        raise SystemExit(1) from None


asyncio.run(main())
PY
}

wait_for_stable_database() {
  stable_checks=0
  attempts=0
  while [ "$stable_checks" -lt 3 ]; do
    attempts=$((attempts + 1))
    if check_database; then
      stable_checks=$((stable_checks + 1))
    else
      stable_checks=0
    fi
    if [ "$attempts" -ge 30 ]; then
      echo "application database did not become stably ready" >&2
      return 1
    fi
    if [ "$stable_checks" -lt 3 ]; then
      sleep 1
    fi
  done
}

docker compose -p "$project_name" --env-file .env.example $compose_files up -d --wait
# The official Postgres entrypoint briefly exposes a temporary init server before
# restarting the final postmaster. Compose health can therefore turn green during
# that restart window. Require consecutive successful app-level connections before
# Alembic is allowed to touch the database.
wait_for_stable_database
DATABASE_URL="$database_url" UV_CACHE_DIR=.cache/uv uv run alembic -c db/alembic.ini upgrade head
DATABASE_URL="$database_url" UV_CACHE_DIR=.cache/uv uv run alembic -c db/alembic.ini downgrade base
DATABASE_URL="$database_url" UV_CACHE_DIR=.cache/uv uv run alembic -c db/alembic.ini upgrade head
DATABASE_URL="$database_url" UV_CACHE_DIR=.cache/uv uv run alembic -c db/alembic.ini check
TEST_DATABASE_URL="$database_url" \
  TEST_OBJECT_STORE_ENDPOINT=http://127.0.0.1:55900 \
  TEST_OBJECT_STORE_BUCKET=auto-video-sub-integration \
  UV_CACHE_DIR=.cache/uv \
  uv run pytest -m integration
