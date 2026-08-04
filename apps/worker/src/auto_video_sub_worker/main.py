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
    build_dependency_probes,
    create_engine,
    get_settings,
)
from auto_video_sub_infrastructure.logging import configure_logging
from auto_video_sub_providers import FFmpegMediaProcessor
from temporalio.client import Client
from temporalio.worker import Worker

from auto_video_sub_worker.media_ingest_workflow import MediaIngestWorkflow
from auto_video_sub_worker.media_workflow import MediaActivities

LOGGER = logging.getLogger(__name__)


async def check_once(probes: Sequence[DependencyProbe], timeout_seconds: float) -> bool:
    report = await check_readiness(probes, timeout_seconds=timeout_seconds)
    for dependency in report.dependencies:
        LOGGER.info(
            "dependency_checked",
            extra={"dependency": dependency.name, "code": dependency.code, "service": "worker"},
        )
    return report.ready


async def serve() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    probes = build_dependency_probes(settings)
    if not await check_once(probes, settings.dependency_timeout_seconds):
        LOGGER.error("worker_host_startup_failed", extra={"service": "worker"})
        return 1

    engine = create_engine(settings.database_url)
    repository = SqlAlchemyProductRepository(
        SessionProvider(engine),
        default_max_projects=settings.default_max_projects,
        default_max_concurrent_uploads=settings.default_max_concurrent_uploads,
        default_max_storage_bytes=settings.default_max_storage_bytes,
    )
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
    activities = MediaActivities(
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
    temporal_client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    worker = Worker(
        temporal_client,
        task_queue=settings.temporal_media_task_queue,
        workflows=[MediaIngestWorkflow],
        activities=[
            activities.validate_original,
            activities.generate_proxy,
            activities.mark_failed,
        ],
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for event in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(event, stop.set)

    LOGGER.info(
        "worker_host_ready",
        extra={"service": "worker", "task_queue": settings.temporal_media_task_queue},
    )
    worker_task = asyncio.create_task(worker.run())
    stop_task = asyncio.create_task(stop.wait())
    done, _ = await asyncio.wait(
        {worker_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    result = 0
    if worker_task in done and worker_task.exception() is not None:
        LOGGER.error(
            "worker_host_failed",
            extra={
                "service": "worker",
                "exception_type": type(worker_task.exception()).__name__,
            },
        )
        result = 1
    await worker.shutdown()
    if not worker_task.done():
        await worker_task
    await engine.dispose()
    stop_task.cancel()
    await asyncio.gather(stop_task, return_exceptions=True)
    LOGGER.info("worker_host_stopped", extra={"service": "worker"})
    return result


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
