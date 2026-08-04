from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from collections.abc import Sequence

from auto_video_sub_application import DependencyProbe, check_readiness
from auto_video_sub_infrastructure import build_dependency_probes, get_settings
from auto_video_sub_infrastructure.logging import configure_logging

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

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for event in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(event, stop.set)

    LOGGER.info("worker_host_ready_no_task_pollers", extra={"service": "worker"})
    await stop.wait()
    LOGGER.info("worker_host_stopped", extra={"service": "worker"})
    return 0


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
