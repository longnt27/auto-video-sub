from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in (
            "request_id",
            "user_id",
            "project_id",
            "workflow_id",
            "stage_execution_id",
            "artifact_id",
            "attempt",
            "worker_id",
            "task_queue",
            "service",
            "dependency",
            "code",
            "exception_type",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = f"{span_context.trace_id:032x}"
            payload["span_id"] = f"{span_context.span_id:016x}"
        if record.exc_info:
            exception_type = record.exc_info[0]
            if exception_type is not None:
                payload["exception_type"] = exception_type.__name__
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
