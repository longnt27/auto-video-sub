from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DependencyStatus:
    name: str
    healthy: bool
    code: str


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    ready: bool
    dependencies: tuple[DependencyStatus, ...]


class DependencyProbe(Protocol):
    @property
    def name(self) -> str: ...

    async def check(self) -> None: ...


async def _run_probe(probe: DependencyProbe, timeout_seconds: float) -> DependencyStatus:
    try:
        async with asyncio.timeout(timeout_seconds):
            await probe.check()
    except TimeoutError:
        return DependencyStatus(name=probe.name, healthy=False, code="dependency_timeout")
    except Exception:
        return DependencyStatus(name=probe.name, healthy=False, code="dependency_unavailable")
    return DependencyStatus(name=probe.name, healthy=True, code="ok")


async def check_readiness(
    probes: Sequence[DependencyProbe], *, timeout_seconds: float
) -> ReadinessReport:
    statuses = await asyncio.gather(*(_run_probe(probe, timeout_seconds) for probe in probes))
    ordered = tuple(sorted(statuses, key=lambda item: item.name))
    return ReadinessReport(
        ready=all(status.healthy for status in ordered),
        dependencies=ordered,
    )
