from __future__ import annotations

import pytest
from auto_video_sub_worker.main import check_once


class Probe:
    name = "test"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def check(self) -> None:
        if self.fail:
            raise RuntimeError("unavailable")


@pytest.mark.asyncio
async def test_check_once_succeeds_when_dependencies_are_healthy() -> None:
    assert await check_once([Probe()], timeout_seconds=0.1) is True


@pytest.mark.asyncio
async def test_check_once_fails_when_a_dependency_is_unhealthy() -> None:
    assert await check_once([Probe(fail=True)], timeout_seconds=0.1) is False
