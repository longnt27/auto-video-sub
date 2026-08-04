from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest
from auto_video_sub_domain import MediaProbe, MediaStatus, NotFoundError, UploadState
from auto_video_sub_infrastructure import (
    SessionProvider,
    SqlAlchemyProductRepository,
    create_engine,
)


@pytest.mark.integration
async def test_postgres_repository_enforces_owner_scope_and_idempotency() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    engine = create_engine(database_url)
    repository = SqlAlchemyProductRepository(
        SessionProvider(engine),
        default_max_projects=3,
        default_max_concurrent_uploads=1,
        default_max_storage_bytes=10_000_000,
    )
    try:
        concurrent_owners = await asyncio.gather(
            repository.get_or_create_user("owner-integration@example.com"),
            repository.get_or_create_user("owner-integration@example.com"),
        )
        owner = concurrent_owners[0]
        assert concurrent_owners[1].id == owner.id
        other = await repository.get_or_create_user("other-integration@example.com")
        project = await repository.create_project(
            owner_id=owner.id,
            title="Integration project",
            idempotency_key="integration-project-0001",
        )
        duplicate = await repository.create_project(
            owner_id=owner.id,
            title="Integration project",
            idempotency_key="integration-project-0001",
        )
        assert duplicate.id == project.id
        with pytest.raises(NotFoundError):
            await repository.get_project(owner_id=other.id, project_id=project.id)

        intent = await repository.create_upload_intent(
            owner_id=owner.id,
            project_id=project.id,
            display_name="fixture.mp4",
            content_type="video/mp4",
            byte_size=1_000,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            idempotency_key="integration-upload-0001",
        )
        await repository.mark_upload_received(owner_id=owner.id, upload_intent_id=intent.id)
        validation_stage_ids = await asyncio.gather(
            *(
                repository.begin_stage(
                    project_id=project.id,
                    media_asset_id=intent.media_asset_id,
                    workflow_id=f"integration/{intent.media_asset_id}",
                    stage_name="media_validation",
                    attempt=1,
                    input_fingerprint="a" * 64,
                    worker_id="integration-test",
                )
                for _ in range(2)
            )
        )
        assert validation_stage_ids[0] == validation_stage_ids[1]
        validation_stage_id = validation_stage_ids[0]
        original = await repository.register_original(
            media_asset_id=intent.media_asset_id,
            media_type="video/mp4",
            byte_size=1_000,
            checksum_sha256="b" * 64,
            probe=MediaProbe(
                format_name="mov,mp4",
                duration_us=1_000_000,
                width=640,
                height=360,
                frame_rate=24,
                video_codec="h264",
                audio_codec="aac",
                stream_count=2,
            ),
            stage_execution_id=validation_stage_id,
        )
        assert original.id == intent.original_artifact_id
        proxy_id = await repository.ensure_proxy_artifact_id(intent.media_asset_id)
        proxy_stage_id = await repository.begin_stage(
            project_id=project.id,
            media_asset_id=intent.media_asset_id,
            workflow_id=f"integration/{intent.media_asset_id}",
            stage_name="proxy_generation",
            attempt=1,
            input_fingerprint="c" * 64,
            worker_id="integration-test",
        )
        proxy = await repository.register_proxy(
            media_asset_id=intent.media_asset_id,
            artifact_id=proxy_id,
            object_key=f"artifacts/{project.id}/{proxy_id}/proxy.mp4",
            byte_size=500,
            checksum_sha256="d" * 64,
            stage_execution_id=proxy_stage_id,
        )
        assert proxy.id == proxy_id
        assert await repository.get_artifact_internal(proxy_id) == proxy

        second_project, duplicate_second_project = await asyncio.gather(
            repository.create_project(
                owner_id=owner.id,
                title="Concurrent project",
                idempotency_key="integration-project-concurrent",
            ),
            repository.create_project(
                owner_id=owner.id,
                title="Concurrent project",
                idempotency_key="integration-project-concurrent",
            ),
        )
        assert second_project.id == duplicate_second_project.id

        stale = await repository.create_upload_intent(
            owner_id=owner.id,
            project_id=second_project.id,
            display_name="expired.mp4",
            content_type="video/mp4",
            byte_size=100,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
            idempotency_key="integration-upload-expired",
        )
        await repository.create_upload_intent(
            owner_id=owner.id,
            project_id=second_project.id,
            display_name="fresh.mp4",
            content_type="video/mp4",
            byte_size=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            idempotency_key="integration-upload-fresh",
        )
        expired = await repository.get_upload_intent(
            owner_id=owner.id,
            project_id=second_project.id,
            upload_intent_id=stale.id,
        )
        assert expired.state is UploadState.EXPIRED
        await repository.mark_media_failed(
            stale.media_asset_id,
            error_code="MEDIA_INGEST_EXHAUSTED",
        )
        expired_media = await repository.get_media_asset(
            owner_id=owner.id,
            project_id=second_project.id,
            media_asset_id=stale.media_asset_id,
        )
        assert expired_media.status is MediaStatus.REJECTED
        assert expired_media.error_code == "UPLOAD_INTENT_EXPIRED"
    finally:
        await engine.dispose()
