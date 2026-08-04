from __future__ import annotations

import asyncio
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from auto_video_sub_infrastructure import S3ObjectStorage


def _read_url(request: str | urllib.request.Request) -> tuple[int, bytes]:
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, response.read()


@pytest.mark.integration
async def test_garage_signed_upload_seal_download_and_delete(tmp_path: Path) -> None:
    endpoint = os.environ.get("TEST_OBJECT_STORE_ENDPOINT")
    bucket = os.environ.get("TEST_OBJECT_STORE_BUCKET")
    if endpoint is None or bucket is None:
        pytest.skip("TEST_OBJECT_STORE_ENDPOINT and TEST_OBJECT_STORE_BUCKET are required")
    storage = S3ObjectStorage(
        endpoint=endpoint,
        public_endpoint=endpoint,
        bucket=bucket,
        region="garage",
        access_key="GK00000000000000000000000000000000",
        secret_key="0000000000000000000000000000000000000000000000000000000000000000",
    )
    payload = b"phase-2-storage-contract"
    prefix = uuid4().hex
    staging_key = f"staging/{prefix}"
    sealed_key = f"artifacts/{prefix}/original"
    signed = storage.sign_upload(
        object_key=staging_key,
        content_type="video/mp4",
        byte_size=len(payload),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    upload = urllib.request.Request(
        signed.url,
        data=payload,
        headers=signed.headers,
        method=signed.method,
    )
    upload_status, _ = await asyncio.to_thread(_read_url, upload)
    assert upload_status // 100 == 2

    oversized_key = f"staging/{prefix}-oversized"
    oversized = storage.sign_upload(
        object_key=oversized_key,
        content_type="video/mp4",
        byte_size=len(payload),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    oversized_request = urllib.request.Request(
        oversized.url,
        data=payload + b"x",
        headers=oversized.headers,
        method=oversized.method,
    )
    with pytest.raises(urllib.error.HTTPError) as rejected:
        await asyncio.to_thread(_read_url, oversized_request)
    assert rejected.value.code == 403

    metadata = await storage.seal_upload(
        staging_key=staging_key,
        sealed_key=sealed_key,
        expected_size=len(payload),
        expected_content_type="video/mp4",
    )
    assert metadata.byte_size == len(payload)
    destination = tmp_path / "downloaded"
    await storage.download_file(sealed_key, destination)
    assert destination.read_bytes() == payload

    download_url = storage.sign_download(
        object_key=sealed_key,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    _, downloaded = await asyncio.to_thread(_read_url, download_url)
    assert downloaded == payload
    await storage.delete_object(sealed_key)
