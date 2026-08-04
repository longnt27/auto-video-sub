# syntax=docker/dockerfile:1.12
FROM ghcr.io/astral-sh/uv:0.11.3 AS uv
FROM python:3.12.13-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY packages/domain/pyproject.toml packages/domain/pyproject.toml
COPY packages/application/pyproject.toml packages/application/pyproject.toml
COPY packages/infrastructure/pyproject.toml packages/infrastructure/pyproject.toml
COPY packages/providers/pyproject.toml packages/providers/pyproject.toml
RUN uv sync --frozen --no-dev --package auto-video-sub-api --no-install-workspace
COPY apps/api/src apps/api/src
COPY packages/domain/src packages/domain/src
COPY packages/application/src packages/application/src
COPY packages/infrastructure/src packages/infrastructure/src
RUN uv sync --frozen --no-dev --package auto-video-sub-api

FROM python:3.12.13-slim-bookworm AS runtime
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/apps/api/src apps/api/src
COPY --from=builder /app/packages/domain/src packages/domain/src
COPY --from=builder /app/packages/application/src packages/application/src
COPY --from=builder /app/packages/infrastructure/src packages/infrastructure/src
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["auto-video-sub-api"]
