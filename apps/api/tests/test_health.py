from __future__ import annotations

import httpx
import pytest
from auto_video_sub_api.app import create_app
from auto_video_sub_infrastructure import Settings


class Probe:
    def __init__(self, name: str, error: Exception | None = None) -> None:
        self._name = name
        self.error = error

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> None:
        if self.error:
            raise self.error


def settings_for_test() -> Settings:
    return Settings(
        _env_file=None,
        service_name="test-api",
        dependency_timeout_seconds=0.1,
    )


def test_phase4_translation_and_style_routes_are_mounted() -> None:
    app = create_app(settings=settings_for_test(), probes=[])
    paths = app.openapi()["paths"]

    assert "/v1/translation/tones" in paths
    assert "/v1/projects/{project_id}/media/{media_asset_id}/translation/estimate" in paths
    assert "/v1/projects/{project_id}/media/{media_asset_id}/translation/start" in paths
    assert "/v1/projects/{project_id}/media/{media_asset_id}/translation/approve" in paths
    assert "/v1/subtitle-styles/fonts" in paths
    assert "/v1/projects/{project_id}/media/{media_asset_id}/subtitle-style" in paths
    assert "/v1/projects/{project_id}/media/{media_asset_id}/subtitle-style/revisions" in paths


@pytest.mark.asyncio
async def test_liveness_does_not_require_dependencies() -> None:
    app = create_app(settings=settings_for_test(), probes=[Probe("db", RuntimeError("down"))])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/live", headers={"x-request-id": "test-request"})

    assert response.status_code == 200
    assert response.json() == {"status": "alive", "service": "test-api", "version": "0.1.0"}
    assert response.headers["x-request-id"] == "test-request"


@pytest.mark.asyncio
async def test_readiness_reports_normalized_dependency_failure() -> None:
    app = create_app(
        settings=settings_for_test(),
        probes=[Probe("postgresql"), Probe("temporal", RuntimeError("private details"))],
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependencies": [
            {"name": "postgresql", "healthy": True, "code": "ok"},
            {"name": "temporal", "healthy": False, "code": "dependency_unavailable"},
        ],
    }


@pytest.mark.asyncio
async def test_untrusted_request_id_is_replaced() -> None:
    app = create_app(settings=settings_for_test(), probes=[])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/live", headers={"x-request-id": "bad value\n"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "bad value\n"
