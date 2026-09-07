from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"anchor not found in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace(
    "packages/infrastructure/pyproject.toml",
    '  "pydantic-settings>=2.12,<3",\n',
    '  "opentelemetry-exporter-otlp-proto-http>=1.44,<1.45",\n'
    '  "opentelemetry-sdk>=1.44,<1.45",\n'
    '  "pydantic-settings>=2.12,<3",\n',
)

replace(
    "packages/infrastructure/src/auto_video_sub_infrastructure/settings.py",
    '    log_level: str = "INFO"\n    host: str = "0.0.0.0"\n',
    '    log_level: str = "INFO"\n'
    '    otel_enabled: bool = False\n'
    '    otel_exporter_otlp_endpoint: str = "http://127.0.0.1:4318"\n'
    '    otel_trace_sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)\n'
    '    otel_metric_export_interval_seconds: int = Field(default=10, ge=5, le=300)\n'
    '    host: str = "0.0.0.0"\n',
)

replace(
    "packages/infrastructure/src/auto_video_sub_infrastructure/logging.py",
    "from typing import Any\n",
    "from typing import Any\n\nfrom opentelemetry import trace\n",
)
replace(
    "packages/infrastructure/src/auto_video_sub_infrastructure/logging.py",
    '        if record.exc_info:\n',
    '        span_context = trace.get_current_span().get_span_context()\n'
    '        if span_context.is_valid:\n'
    '            payload["trace_id"] = f"{span_context.trace_id:032x}"\n'
    '            payload["span_id"] = f"{span_context.span_id:016x}"\n'
    '        if record.exc_info:\n',
)

replace(
    "apps/api/src/auto_video_sub_api/app.py",
    "from datetime import timedelta\n",
    "from datetime import timedelta\nfrom time import perf_counter\n",
)
replace(
    "apps/api/src/auto_video_sub_api/app.py",
    "from auto_video_sub_infrastructure.logging import configure_logging\n",
    "from auto_video_sub_infrastructure.logging import configure_logging\n"
    "from auto_video_sub_infrastructure.telemetry import configure_telemetry\n",
)
replace(
    "apps/api/src/auto_video_sub_api/app.py",
    "    configure_logging(resolved_settings.log_level)\n\n    @asynccontextmanager\n",
    "    configure_logging(resolved_settings.log_level)\n"
    "    telemetry = configure_telemetry(\n"
    "        enabled=resolved_settings.otel_enabled,\n"
    "        endpoint=resolved_settings.otel_exporter_otlp_endpoint,\n"
    "        service_name=resolved_settings.service_name,\n"
    "        service_version=resolved_settings.service_version,\n"
    "        environment=resolved_settings.app_env,\n"
    "        sample_ratio=resolved_settings.otel_trace_sample_ratio,\n"
    "        export_interval_seconds=resolved_settings.otel_metric_export_interval_seconds,\n"
    "    )\n\n"
    "    @asynccontextmanager\n",
)
replace(
    "apps/api/src/auto_video_sub_api/app.py",
    "            if engine is not None:\n                await engine.dispose()\n",
    "            if engine is not None:\n                await engine.dispose()\n"
    "            telemetry.shutdown()\n",
)
old_middleware = '''    @application.middleware("http")
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
'''
new_middleware = '''    @application.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Response:
        request_id = _request_id(request)
        request.state.request_id = request_id
        started = perf_counter()
        span_attributes = {
            "http.request.method": request.method,
            "request.id": request_id,
        }
        with telemetry.tracer.start_as_current_span(
            "http.request",
            attributes=span_attributes,
        ) as span:
            response: Response = await call_next(request)
            response.headers["x-request-id"] = request_id
            duration_ms = (perf_counter() - started) * 1000
            metric_attributes = {
                "http.request.method": request.method,
                "http.response.status_code": str(response.status_code),
            }
            telemetry.http_requests.add(1, metric_attributes)
            telemetry.http_duration_ms.record(duration_ms, metric_attributes)
            span.set_attribute("http.response.status_code", response.status_code)
            LOGGER.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "service": resolved_settings.service_name,
                    "user_id": getattr(request.state, "user_id", None),
                },
            )
            return response
'''
replace("apps/api/src/auto_video_sub_api/app.py", old_middleware, new_middleware)

replace(
    ".env.example",
    "WORKER_PROFILE=core\nOTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318\nLOG_LEVEL=INFO\n",
    "WORKER_PROFILE=core\n"
    "# Phase 7 telemetry is opt-in for the normal stack; stack-observability-up enables it.\n"
    "OTEL_ENABLED=0\n"
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318\n"
    "OTEL_TRACE_SAMPLE_RATIO=1.0\n"
    "OTEL_METRIC_EXPORT_INTERVAL_SECONDS=10\n"
    "PROMETHEUS_RETENTION=24h\n"
    "GRAFANA_HOST_PORT=3200\n"
    "PROMETHEUS_HOST_PORT=9090\n"
    "JAEGER_HOST_PORT=16686\n"
    "LOG_LEVEL=INFO\n",
)

replace(
    "Makefile",
    "COMPOSE_FILE := deploy/compose.yaml\n",
    "COMPOSE_FILE := deploy/compose.yaml\n"
    "OBSERVABILITY_COMPOSE_FILE := deploy/compose.observability.yaml\n",
)
replace(
    "Makefile",
    "\tstack-config stack-up stack-smoke stack-smoke-phase2 stack-down api worker web disk-check \\\n",
    "\tstack-config stack-up stack-smoke stack-smoke-phase2 stack-down \\\n"
    "\tstack-observability-config stack-observability-up stack-observability-smoke \\\n"
    "\tstack-observability-down api worker web disk-check \\\n",
)
replace(
    "Makefile",
    "stack-down:\n\tdocker compose --env-file .env.example -f $(COMPOSE_FILE) down\n\napi:\n",
    "stack-down:\n\tdocker compose --env-file .env.example -f $(COMPOSE_FILE) down\n\n"
    "stack-observability-config:\n"
    "\tdocker compose --env-file .env.example -f $(COMPOSE_FILE) -f $(OBSERVABILITY_COMPOSE_FILE) config --quiet\n\n"
    "stack-observability-up: disk-check\n"
    "\tdocker compose --env-file .env.example -f $(COMPOSE_FILE) -f $(OBSERVABILITY_COMPOSE_FILE) up -d --build --wait\n\n"
    "stack-observability-smoke:\n"
    "\t./scripts/smoke-observability.sh\n\n"
    "stack-observability-down:\n"
    "\tdocker compose --env-file .env.example -f $(COMPOSE_FILE) -f $(OBSERVABILITY_COMPOSE_FILE) down\n\n"
    "api:\n",
)

replace(
    ".github/workflows/ci.yml",
    "      - name: Verify paid provider smoke tests remain disabled\n",
    "      - name: Validate observability topology\n"
    "        run: docker compose --env-file .env.example -f deploy/compose.yaml -f deploy/compose.observability.yaml config --quiet\n"
    "      - name: Verify paid provider smoke tests remain disabled\n",
)
