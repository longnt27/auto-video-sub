from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from collections.abc import Sequence

from auto_video_sub_application import DependencyProbe, check_readiness
from auto_video_sub_domain import MediaLimits
from auto_video_sub_infrastructure import (
    S3ObjectStorage,
    SessionProvider,
    SqlAlchemyProductRepository,
    SqlAlchemyTranscriptRepository,
    SqlAlchemyTranslationRepository,
    build_dependency_probes,
    create_engine,
    get_settings,
)
from auto_video_sub_infrastructure.logging import configure_logging
from auto_video_sub_providers import (
    FFmpegMediaProcessor,
    OpenAIResponsesTranslationProvider,
    RapidOcrProvider,
)
from temporalio.client import Client
from temporalio.worker import Worker

from auto_video_sub_worker.media_ingest_workflow import MediaIngestWorkflow
from auto_video_sub_worker.media_workflow import MediaActivities
from auto_video_sub_worker.source_transcript_activities import SourceTranscriptActivities
from auto_video_sub_worker.source_transcript_workflow import SourceTranscriptWorkflow
from auto_video_sub_worker.translation_activities import TranslationActivities
from auto_video_sub_worker.translation_workflow import TranslationWorkflow

LOGGER = logging.getLogger(__name__)


async def check_once(probes: Sequence[DependencyProbe], timeout_seconds: float) -> bool:
    report = await check_readiness(probes, timeout_seconds=timeout_seconds)
    for dependency in report.dependencies:
        LOGGER.info(
            "dependency_checked",
            extra={"dependency": dependency.name, "code": dependency.code, "service": "worker"},
        )
    return report.ready


async def _run_workers(workers: tuple[Worker, ...], *, profile: str) -> int:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for event in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(event, stop.set)

    LOGGER.info(
        "worker_host_ready",
        extra={"service": "worker", "profile": profile, "worker_count": len(workers)},
    )
    worker_tasks = tuple(asyncio.create_task(worker.run()) for worker in workers)
    stop_task = asyncio.create_task(stop.wait())
    done, _ = await asyncio.wait(
        {*worker_tasks, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    result = 0
    for worker_task in worker_tasks:
        if worker_task in done and worker_task.exception() is not None:
            LOGGER.error(
                "worker_host_failed",
                extra={
                    "service": "worker",
                    "profile": profile,
                    "exception_type": type(worker_task.exception()).__name__,
                },
            )
            result = 1
            stop.set()
    await asyncio.gather(*(worker.shutdown() for worker in workers))
    for worker_task in worker_tasks:
        if not worker_task.done():
            await worker_task
    stop_task.cancel()
    await asyncio.gather(stop_task, return_exceptions=True)
    LOGGER.info("worker_host_stopped", extra={"service": "worker", "profile": profile})
    return result


async def serve() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    probes = build_dependency_probes(settings)
    if not await check_once(probes, settings.dependency_timeout_seconds):
        LOGGER.error("worker_host_startup_failed", extra={"service": "worker"})
        return 1

    engine = create_engine(settings.database_url)
    sessions = SessionProvider(engine)
    temporal_client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )

    if settings.worker_profile == "translation":
        translation_repository = SqlAlchemyTranslationRepository(
            sessions,
            default_translation_budget_micros=settings.default_translation_budget_micros,
            input_cost_micros_per_million_tokens=(
                settings.translation_input_cost_micros_per_million_tokens
            ),
            output_cost_micros_per_million_tokens=(
                settings.translation_output_cost_micros_per_million_tokens
            ),
        )
        translation_activities = TranslationActivities(
            repository=translation_repository,
            provider=OpenAIResponsesTranslationProvider(
                api_key=settings.translation_provider_api_key,
                model=settings.translation_provider_model,
                base_url=settings.translation_provider_base_url,
                timeout_seconds=settings.translation_request_timeout_seconds,
            ),
        )
        worker = Worker(
            temporal_client,
            task_queue=settings.temporal_translation_task_queue,
            workflows=[TranslationWorkflow],
            activities=[
                translation_activities.extract_context,
                translation_activities.plan_batches,
                translation_activities.translate_batch,
                translation_activities.finalize,
                translation_activities.mark_failed,
            ],
        )
        try:
            return await _run_workers((worker,), profile="translation")
        finally:
            await engine.dispose()

    repository = SqlAlchemyProductRepository(
        sessions,
        default_max_projects=settings.default_max_projects,
        default_max_concurrent_uploads=settings.default_max_concurrent_uploads,
        default_max_storage_bytes=settings.default_max_storage_bytes,
    )
    transcript_repository = SqlAlchemyTranscriptRepository(sessions, repository)
    storage = S3ObjectStorage(
        endpoint=settings.object_store_endpoint,
        public_endpoint=settings.public_object_store_base_url,
        bucket=settings.object_store_bucket,
        region=settings.object_store_region,
        access_key=settings.object_store_access_key,
        secret_key=settings.object_store_secret_key,
    )
    processor = FFmpegMediaProcessor(
        ffmpeg_path=settings.ffmpeg_path,
        ffprobe_path=settings.ffprobe_path,
        probe_timeout_seconds=settings.media_probe_timeout_seconds,
        proxy_timeout_seconds=settings.proxy_timeout_seconds,
    )
    media_activities = MediaActivities(
        repository=repository,
        storage=storage,
        processor=processor,
        limits=MediaLimits(
            max_upload_bytes=settings.max_upload_bytes,
            max_duration_us=settings.max_media_duration_seconds * 1_000_000,
            max_width=settings.max_media_width,
            max_height=settings.max_media_height,
            max_frame_rate=settings.max_media_frame_rate,
            max_streams=settings.max_media_streams,
            allowed_content_types=settings.allowed_upload_content_types,
        ),
    )
    transcript_activities = SourceTranscriptActivities(
        repository=transcript_repository,
        storage=storage,
        processor=processor,
        ocr=RapidOcrProvider(),
    )
    media_worker = Worker(
        temporal_client,
        task_queue=settings.temporal_media_task_queue,
        workflows=[MediaIngestWorkflow],
        activities=[
            media_activities.validate_original,
            media_activities.generate_proxy,
            media_activities.mark_failed,
        ],
    )
    transcript_worker = Worker(
        temporal_client,
        task_queue=settings.temporal_local_ai_task_queue,
        workflows=[SourceTranscriptWorkflow],
        activities=[
            transcript_activities.extract_and_ocr,
            transcript_activities.consolidate,
            transcript_activities.mark_failed,
        ],
    )
    try:
        return await _run_workers((media_worker, transcript_worker), profile="core")
    finally:
        await engine.dispose()


async def healthcheck() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    probes = build_dependency_probes(settings)
    return 0 if await check_once(probes, settings.dependency_timeout_seconds) else 1


def run() -> None:
    parser = argparse.ArgumentParser(description="Auto Video Sub worker host")
    parser.add_argument("--check", action="store_true", help="check dependencies and exit")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(healthcheck() if args.check else serve()))


if __name__ == "__main__":
    run()
