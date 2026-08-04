from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import timedelta
from typing import Any
from uuid import uuid4

from auto_video_sub_application import (
    DependencyProbe,
    IdentityService,
    ProjectService,
    UploadService,
    check_readiness,
)
from auto_video_sub_application.ports import ObjectStorage, ProductRepository, WorkflowStarter
from auto_video_sub_domain import DomainError, MediaLimits
from auto_video_sub_infrastructure import (
    S3ObjectStorage,
    SessionProvider,
    Settings,
    SqlAlchemyProductRepository,
    TemporalWorkflowStarter,
    build_dependency_probes,
    create_engine,
    get_settings,
)
from auto_video_sub_infrastructure.logging import configure_logging
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auto_video_sub_api.routes import router

LOGGER = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _request_id(request: Request) -> str:
    candidate = request.headers.get("x-request-id", "")
    return candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else str(uuid4())


def create_app(
    *,
    settings: Settings | None = None,
    probes: Sequence[DependencyProbe] | None = None,
    repository: ProductRepository | None = None,
    storage: ObjectStorage | None = None,
    workflows: WorkflowStarter | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not hasattr(app.state, "probes"):
            app.state.probes = build_dependency_probes(resolved_settings)
        engine = None
        resolved_repository = repository
        if resolved_repository is None:
            engine = create_engine(resolved_settings.database_url)
            resolved_repository = SqlAlchemyProductRepository(
                SessionProvider(engine),
                default_max_projects=resolved_settings.default_max_projects,
                default_max_concurrent_uploads=resolved_settings.default_max_concurrent_uploads,
                default_max_storage_bytes=resolved_settings.default_max_storage_bytes,
            )
        resolved_storage = storage or S3ObjectStorage(
            endpoint=resolved_settings.object_store_endpoint,
            public_endpoint=resolved_settings.public_object_store_base_url,
            bucket=resolved_settings.object_store_bucket,
            region=resolved_settings.object_store_region,
            access_key=resolved_settings.object_store_access_key,
            secret_key=resolved_settings.object_store_secret_key,
        )
        resolved_workflows = workflows or TemporalWorkflowStarter(
            address=resolved_settings.temporal_address,
            namespace=resolved_settings.temporal_namespace,
            task_queue=resolved_settings.temporal_media_task_queue,
        )
        app.state.repository = resolved_repository
        app.state.identity_service = IdentityService(resolved_repository)
        app.state.project_service = ProjectService(resolved_repository)
        app.state.upload_service = UploadService(
            repository=resolved_repository,
            storage=resolved_storage,
            workflows=resolved_workflows,
            limits=MediaLimits(
                max_upload_bytes=resolved_settings.max_upload_bytes,
                max_duration_us=resolved_settings.max_media_duration_seconds * 1_000_000,
                max_width=resolved_settings.max_media_width,
                max_height=resolved_settings.max_media_height,
                max_frame_rate=resolved_settings.max_media_frame_rate,
                max_streams=resolved_settings.max_media_streams,
                allowed_content_types=resolved_settings.allowed_upload_content_types,
            ),
            upload_url_ttl=timedelta(seconds=resolved_settings.upload_url_ttl_seconds),
            download_url_ttl=timedelta(seconds=resolved_settings.download_url_ttl_seconds),
        )
        try:
            yield
        finally:
            if engine is not None:
                await engine.dispose()

    application = FastAPI(
        title="Auto Video Sub API",
        version=resolved_settings.service_version,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    if probes is not None:
        application.state.probes = probes
    application.state.settings = resolved_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["content-type", "idempotency-key", "x-request-id"],
    )

    @application.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Response:
        request_id = _request_id(request)
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["x-request-id"] = request_id
        LOGGER.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "service": resolved_settings.service_name,
                "user_id": getattr(request.state, "user_id", None),
            },
        )
        return response

    @application.exception_handler(DomainError)
    async def domain_error_handler(request: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "request_id": getattr(request.state, "request_id", str(uuid4())),
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        LOGGER.info(
            "request_validation_failed",
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "REQUEST_VALIDATION_FAILED",
                    "message": "Request data is invalid",
                    "request_id": getattr(request.state, "request_id", str(uuid4())),
                }
            },
        )

    @application.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, error: Exception) -> JSONResponse:
        LOGGER.error(
            "unhandled_request_error",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "code": "INTERNAL_ERROR",
                "exception_type": type(error).__name__,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "request_id": getattr(request.state, "request_id", str(uuid4())),
                }
            },
        )

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

    application.include_router(router)

    return application
