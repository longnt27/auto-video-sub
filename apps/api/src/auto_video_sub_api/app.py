from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from auto_video_sub_application import DependencyProbe, check_readiness
from auto_video_sub_infrastructure import Settings, build_dependency_probes, get_settings
from auto_video_sub_infrastructure.logging import configure_logging
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

LOGGER = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _request_id(request: Request) -> str:
    candidate = request.headers.get("x-request-id", "")
    return candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else str(uuid4())


def create_app(
    *,
    settings: Settings | None = None,
    probes: Sequence[DependencyProbe] | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not hasattr(app.state, "probes"):
            app.state.probes = build_dependency_probes(resolved_settings)
        yield

    application = FastAPI(
        title="Auto Video Sub API",
        version=resolved_settings.service_version,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    if probes is not None:
        application.state.probes = probes

    @application.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Response:
        request_id = _request_id(request)
        response: Response = await call_next(request)
        response.headers["x-request-id"] = request_id
        LOGGER.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "service": resolved_settings.service_name,
            },
        )
        return response

    @application.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {
            "status": "alive",
            "service": resolved_settings.service_name,
            "version": resolved_settings.service_version,
        }

    @application.get("/health/ready", tags=["health"])
    async def readiness(request: Request) -> JSONResponse:
        report = await check_readiness(
            request.app.state.probes,
            timeout_seconds=resolved_settings.dependency_timeout_seconds,
        )
        response_status = (
            status.HTTP_200_OK if report.ready else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return JSONResponse(
            status_code=response_status,
            content={
                "status": "ready" if report.ready else "not_ready",
                "dependencies": [asdict(item) for item in report.dependencies],
            },
        )

    return application
