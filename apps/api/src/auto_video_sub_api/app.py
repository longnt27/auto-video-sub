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
    SpeechService,
    SubtitleStyleRepository,
    SubtitleStyleService,
    TranscriptService,
    TranslationService,
    UploadService,
    check_readiness,
)
from auto_video_sub_application.ports import (
    ObjectStorage,
    ProductRepository,
    TranscriptRepository,
    TranscriptWorkflowControl,
    WorkflowStarter,
)
from auto_video_sub_application.speech_ports import SpeechRepository, SpeechWorkflowControl
from auto_video_sub_application.translation_ports import (
    TranslationRepository,
    TranslationWorkflowControl,
)
from auto_video_sub_domain import DomainError, DurationFitPolicy, MediaLimits
from auto_video_sub_infrastructure import (
    S3ObjectStorage,
    SessionProvider,
    Settings,
    SqlAlchemyProductRepository,
    SqlAlchemySpeechRepository,
    SqlAlchemySubtitleStyleRepository,
    SqlAlchemyTranscriptRepository,
    SqlAlchemyTranslationRepository,
    TemporalSpeechWorkflowControl,
    TemporalTranslationWorkflowControl,
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
from auto_video_sub_api.speech_routes import router as speech_router
from auto_video_sub_api.subtitle_style_routes import router as subtitle_style_router
from auto_video_sub_api.translation_routes import router as translation_router

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
    transcript_repository: TranscriptRepository | None = None,
    transcript_workflows: TranscriptWorkflowControl | None = None,
    translation_repository: TranslationRepository | None = None,
    translation_workflows: TranslationWorkflowControl | None = None,
    speech_repository: SpeechRepository | None = None,
    speech_workflows: SpeechWorkflowControl | None = None,
    subtitle_style_repository: SubtitleStyleRepository | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not hasattr(app.state, "probes"):
            app.state.probes = build_dependency_probes(resolved_settings)
        engine = None
        sessions = None
        resolved_repository = repository
        if resolved_repository is None:
            engine = create_engine(resolved_settings.database_url)
            sessions = SessionProvider(engine)
            resolved_repository = SqlAlchemyProductRepository(
                sessions,
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
            transcript_task_queue=resolved_settings.temporal_local_ai_task_queue,
        )
        resolved_transcript_repository = transcript_repository
        if resolved_transcript_repository is None and sessions is not None:
            if not isinstance(resolved_repository, SqlAlchemyProductRepository):
                raise RuntimeError("SQL transcript repository requires SQL product repository")
            resolved_transcript_repository = SqlAlchemyTranscriptRepository(
                sessions,
                resolved_repository,
            )
        resolved_transcript_workflows = transcript_workflows
        if resolved_transcript_workflows is None and isinstance(
            resolved_workflows, TemporalWorkflowStarter
        ):
            resolved_transcript_workflows = resolved_workflows

        resolved_translation_repository = translation_repository
        if resolved_translation_repository is None and sessions is not None:
            resolved_translation_repository = SqlAlchemyTranslationRepository(
                sessions,
                default_translation_budget_micros=(
                    resolved_settings.default_translation_budget_micros
                ),
                input_cost_micros_per_million_tokens=(
                    resolved_settings.translation_input_cost_micros_per_million_tokens
                ),
                output_cost_micros_per_million_tokens=(
                    resolved_settings.translation_output_cost_micros_per_million_tokens
                ),
            )
        resolved_translation_workflows = translation_workflows or TemporalTranslationWorkflowControl(
            address=resolved_settings.temporal_address,
            namespace=resolved_settings.temporal_namespace,
            task_queue=resolved_settings.temporal_translation_task_queue,
        )
        resolved_speech_repository = speech_repository
        if resolved_speech_repository is None and sessions is not None:
            resolved_speech_repository = SqlAlchemySpeechRepository(sessions)
        resolved_speech_workflows = speech_workflows or TemporalSpeechWorkflowControl(
            address=resolved_settings.temporal_address,
            namespace=resolved_settings.temporal_namespace,
            task_queue=resolved_settings.temporal_local_ai_task_queue,
        )
        resolved_subtitle_style_repository = subtitle_style_repository
        if resolved_subtitle_style_repository is None and sessions is not None:
            resolved_subtitle_style_repository = SqlAlchemySubtitleStyleRepository(sessions)

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
        app.state.transcript_service = (
            TranscriptService(
                repository=resolved_transcript_repository,
                workflows=resolved_transcript_workflows,
            )
            if resolved_transcript_repository is not None
            and resolved_transcript_workflows is not None
            else None
        )
        app.state.translation_service = (
            TranslationService(
                repository=resolved_translation_repository,
                workflows=resolved_translation_workflows,
                provider=resolved_settings.translation_provider_name,
                model=resolved_settings.translation_provider_model,
                input_cost_micros_per_million_tokens=(
                    resolved_settings.translation_input_cost_micros_per_million_tokens
                ),
                output_cost_micros_per_million_tokens=(
                    resolved_settings.translation_output_cost_micros_per_million_tokens
                ),
            )
            if resolved_translation_repository is not None
            else None
        )
        app.state.speech_service = (
            SpeechService(
                repository=resolved_speech_repository,
                workflows=resolved_speech_workflows,
                storage=resolved_storage,
                provider=resolved_settings.tts_provider_name,
                model=resolved_settings.tts_model_name,
                model_revision=resolved_settings.tts_model_revision,
                voice_id=resolved_settings.tts_voice_id,
                policy=DurationFitPolicy(
                    tolerance_us=resolved_settings.duration_tolerance_us,
                    max_speed_factor_ppm=resolved_settings.duration_max_speed_factor_ppm,
                    max_rewrite_attempts=resolved_settings.duration_max_rewrite_attempts,
                ),
                download_url_ttl=timedelta(seconds=resolved_settings.download_url_ttl_seconds),
            )
            if resolved_speech_repository is not None
            else None
        )
        app.state.subtitle_style_service = (
            SubtitleStyleService(resolved_subtitle_style_repository)
            if resolved_subtitle_style_repository is not None
            else None
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
    application.include_router(translation_router)
    application.include_router(speech_router)
    application.include_router(subtitle_style_router)
    return application
