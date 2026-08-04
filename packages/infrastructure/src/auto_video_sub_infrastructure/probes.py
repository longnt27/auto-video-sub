from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import boto3
from auto_video_sub_application import DependencyProbe
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from temporalio.client import Client

from auto_video_sub_infrastructure.settings import Settings


class PostgreSqlProbe:
    name = "postgresql"

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def check(self) -> None:
        async with self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))


class TemporalProbe:
    name = "temporal"

    def __init__(self, address: str, namespace: str) -> None:
        self._address = address
        self._namespace = namespace

    async def check(self) -> None:
        client = await Client.connect(self._address, namespace=self._namespace)
        healthy = await client.service_client.check_health()
        if not healthy:
            raise RuntimeError("Temporal health check returned unhealthy")


class ObjectStorageProbe:
    name = "object_storage"

    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    async def check(self) -> None:
        await asyncio.to_thread(self._client.head_bucket, Bucket=self._bucket)


def build_dependency_probes(settings: Settings) -> Sequence[DependencyProbe]:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.object_store_endpoint,
        region_name=settings.object_store_region,
        aws_access_key_id=settings.object_store_access_key,
        aws_secret_access_key=settings.object_store_secret_key,
    )
    return (
        PostgreSqlProbe(engine),
        TemporalProbe(settings.temporal_address, settings.temporal_namespace),
        ObjectStorageProbe(s3_client, settings.object_store_bucket),
    )
