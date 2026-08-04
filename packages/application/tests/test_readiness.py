from __future__ import annotations

import asyncio

import pytest
from auto_video_sub_application import check_readiness


class Probe:
    def __init__(self, name: str, *, error: Exception | None = None, delay: float = 0) -> None:
        self._name = name
        self.error = error
        self.delay = delay

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error


@pytest.mark.asyncio
async def test_readiness_is_sorted_and_healthy_when_all_probes_pass() -> None:
    report = await check_readiness([Probe("temporal"), Probe("postgresql")], timeout_seconds=0.1)

    assert report.ready is True
    assert [status.name for status in report.dependencies] == ["postgresql", "temporal"]
    assert {status.code for status in report.dependencies} == {"ok"}


@pytest.mark.asyncio
async def test_readiness_normalizes_failures_without_exposing_exception_details() -> None:
    report = await check_readiness(
        [Probe("object_storage", error=RuntimeError("secret endpoint details"))],
        timeout_seconds=0.1,
    )

    assert report.ready is False
    assert report.dependencies[0].code == "dependency_unavailable"
    assert "secret endpoint details" not in repr(report)


@pytest.mark.asyncio
async def test_readiness_bounds_each_probe_by_timeout() -> None:
    report = await check_readiness([Probe("slow", delay=0.05)], timeout_seconds=0.001)

    assert report.ready is False
    assert report.dependencies[0].code == "dependency_timeout"
