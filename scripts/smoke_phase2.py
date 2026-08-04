from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4


def request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    body = json.dumps(payload).encode() if payload is not None else None
    request_headers = {"content-type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            value = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"{method} {url} returned {error.code}: {detail}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"{method} {url} returned a non-object response")
    return value


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: smoke_phase2.py WEB_BASE_URL FIXTURE_PATH")
    base_url = sys.argv[1].rstrip("/")
    fixture = Path(sys.argv[2])
    fixture_bytes = fixture.read_bytes()
    project = request_json(
        "POST",
        f"{base_url}/api/backend/v1/projects",
        payload={"title": "Phase 2 smoke test"},
        headers={"idempotency-key": f"smoke-project-{uuid4().hex}"},
    )
    project_id = str(project["id"])
    intent = request_json(
        "POST",
        f"{base_url}/api/backend/v1/projects/{project_id}/uploads",
        payload={
            "file_name": fixture.name,
            "content_type": "video/mp4",
            "byte_size": len(fixture_bytes),
        },
        headers={"idempotency-key": f"smoke-upload-{uuid4().hex}"},
    )
    upload = intent["upload"]
    if not isinstance(upload, dict):
        raise RuntimeError("Upload grant is missing")
    put_request = urllib.request.Request(
        str(upload["url"]),
        data=fixture_bytes,
        headers={str(key): str(value) for key, value in dict(upload["headers"]).items()},
        method="PUT",
    )
    with urllib.request.urlopen(put_request, timeout=30) as response:
        if response.status // 100 != 2:
            raise RuntimeError(f"Object upload returned {response.status}")

    media = request_json(
        "POST",
        (f"{base_url}/api/backend/v1/projects/{project_id}/uploads/{intent['id']}/complete"),
    )
    media_id = str(media["id"])
    terminal_failures = {"failed", "rejected"}
    deadline = time.monotonic() + 180
    last_status = ""
    while time.monotonic() < deadline:
        media = request_json(
            "GET",
            f"{base_url}/api/backend/v1/projects/{project_id}/media/{media_id}",
        )
        status = str(media["status"])
        if status != last_status:
            print(f"media status: {status}", flush=True)
            last_status = status
        if status == "ready":
            proxy_url = media.get("proxy_url")
            if not isinstance(proxy_url, str) or not proxy_url:
                raise RuntimeError("Ready media has no signed proxy URL")
            with urllib.request.urlopen(proxy_url, timeout=30) as response:
                prefix = response.read(32)
                if response.status // 100 != 2 or b"ftyp" not in prefix:
                    raise RuntimeError("Signed proxy download was not a valid MP4 response")
            print(f"phase 2 smoke passed for project {project_id}")
            return 0
        if status in terminal_failures:
            raise RuntimeError(f"Media processing failed: {media.get('error_code')}")
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for media; last status was {last_status}")


if __name__ == "__main__":
    raise SystemExit(main())
