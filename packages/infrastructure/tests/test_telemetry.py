from auto_video_sub_infrastructure.telemetry import configure_telemetry


def test_disabled_telemetry_is_local_and_shutdown_safe() -> None:
    runtime = configure_telemetry(
        enabled=False,
        endpoint="http://127.0.0.1:4318",
        service_name="test-service",
        service_version="test-version",
        environment="test",
        sample_ratio=1.0,
        export_interval_seconds=10,
    )

    assert runtime.enabled is False
    runtime.http_requests.add(1, {"http.request.method": "GET"})
    runtime.http_duration_ms.record(1.5, {"http.request.method": "GET"})
    runtime.shutdown()
