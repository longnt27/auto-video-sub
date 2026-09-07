SHELL := /bin/sh
UV_CACHE_DIR ?= .cache/uv
COMPOSE_FILE := deploy/compose.yaml
OBSERVABILITY_COMPOSE_FILE := deploy/compose.observability.yaml

.PHONY: bootstrap lock format format-check lint typecheck test test-integration check build \
	stack-config stack-up stack-smoke stack-smoke-phase2 stack-down \
	stack-observability-config stack-observability-up stack-observability-smoke \
	stack-observability-down api worker web disk-check \
	migration-check migrate

bootstrap:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --all-packages --all-groups --frozen
	corepack pnpm install --frozen-lockfile

lock:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv lock
	corepack pnpm install --lockfile-only

format:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run ruff format .
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run ruff check --fix .
	corepack pnpm format

format-check:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run ruff format --check .
	corepack pnpm format:check

lint:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run ruff check .
	corepack pnpm lint

typecheck:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run mypy
	corepack pnpm typecheck

test:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest --cov --cov-report=term-missing
	corepack pnpm test

test-integration:
	./scripts/test-integration.sh

check: format-check lint typecheck test

build:
	corepack pnpm build

migration-check:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run alembic -c db/alembic.ini check

migrate:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run alembic -c db/alembic.ini upgrade head

stack-config:
	docker compose --env-file .env.example -f $(COMPOSE_FILE) config --quiet

disk-check:
	./scripts/check-disk-space.sh

stack-up: disk-check
	docker compose --env-file .env.example -f $(COMPOSE_FILE) up -d --build --wait

stack-smoke:
	./scripts/smoke-local-stack.sh

stack-smoke-phase2:
	./scripts/smoke-phase2.sh

stack-down:
	docker compose --env-file .env.example -f $(COMPOSE_FILE) down

stack-observability-config:
	docker compose --env-file .env.example -f $(COMPOSE_FILE) -f $(OBSERVABILITY_COMPOSE_FILE) config --quiet

stack-observability-up: disk-check
	docker compose --env-file .env.example -f $(COMPOSE_FILE) -f $(OBSERVABILITY_COMPOSE_FILE) up -d --build --wait

stack-observability-smoke:
	./scripts/smoke-observability.sh

stack-observability-down:
	docker compose --env-file .env.example -f $(COMPOSE_FILE) -f $(OBSERVABILITY_COMPOSE_FILE) down

api:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run auto-video-sub-api

worker:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run auto-video-sub-worker

web:
	corepack pnpm dev:web
