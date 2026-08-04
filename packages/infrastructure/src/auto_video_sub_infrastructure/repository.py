from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from auto_video_sub_domain import (
    Artifact,
    ArtifactKind,
    ArtifactState,
    ConflictError,
    MediaAsset,
    MediaProbe,
    MediaStatus,
    NotFoundError,
    Project,
    ProjectLifecycle,
    QuotaExceededError,
    RetentionClass,
    UploadIntent,
    UploadState,
    User,
    new_uuid7,
)
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from auto_video_sub_infrastructure.database import SessionProvider
from auto_video_sub_infrastructure.models import (
    ArtifactEdgeModel,
    ArtifactModel,
    MediaAssetModel,
    ProjectModel,
    QuotaAccountModel,
    StageExecutionModel,
    UploadIntentModel,
    UserModel,
)


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _project(row: ProjectModel) -> Project:
    return Project(
        id=row.id,
        owner_id=row.owner_id,
        title=row.title,
        lifecycle=ProjectLifecycle(row.lifecycle),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _upload(row: UploadIntentModel) -> UploadIntent:
    return UploadIntent(
        id=row.id,
        project_id=row.project_id,
        media_asset_id=row.media_asset_id,
        original_artifact_id=row.original_artifact_id,
        object_key=row.staging_object_key,
        sealed_object_key=row.sealed_object_key,
        display_name=row.display_name,
        declared_content_type=row.declared_content_type,
        declared_size_bytes=row.declared_size_bytes,
        state=UploadState(row.state),
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


def _probe(value: dict[str, Any] | None) -> MediaProbe | None:
    return MediaProbe(**value) if value is not None else None


def _media(row: MediaAssetModel) -> MediaAsset:
    return MediaAsset(
        id=row.id,
        project_id=row.project_id,
        display_name=row.display_name,
        status=MediaStatus(row.status),
        original_artifact_id=row.original_artifact_id,
        proxy_artifact_id=row.proxy_artifact_id,
        probe=_probe(row.probe),
        error_code=row.error_code,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _artifact(row: ArtifactModel) -> Artifact:
    return Artifact(
        id=row.id,
        project_id=row.project_id,
        media_asset_id=row.media_asset_id,
        kind=ArtifactKind(row.kind),
        media_type=row.media_type,
        byte_size=row.byte_size,
        checksum_sha256=row.checksum_sha256,
        object_key=row.object_key,
        retention_class=RetentionClass(row.retention_class),
        state=ArtifactState(row.state),
        created_at=row.created_at,
    )


class SqlAlchemyProductRepository:
    def __init__(
        self,
        sessions: SessionProvider,
        *,
        default_max_projects: int,
        default_max_concurrent_uploads: int,
        default_max_storage_bytes: int,
    ) -> None:
        self._sessions = sessions
        self._default_max_projects = default_max_projects
        self._default_max_concurrent_uploads = default_max_concurrent_uploads
        self._default_max_storage_bytes = default_max_storage_bytes

    async def get_or_create_user(self, external_login: str) -> User:
        async with self._sessions.session() as session, session.begin():
            now = datetime.now(UTC)
            proposed_id = new_uuid7()
            inserted_id = await session.scalar(
                postgres_insert(UserModel)
                .values(id=proposed_id, external_login=external_login, created_at=now)
                .on_conflict_do_nothing(index_elements=[UserModel.external_login])
                .returning(UserModel.id)
            )
            if inserted_id is not None:
                session.add(
                    QuotaAccountModel(
                        user_id=inserted_id,
                        max_projects=self._default_max_projects,
                        max_concurrent_uploads=self._default_max_concurrent_uploads,
                        max_storage_bytes=self._default_max_storage_bytes,
                        reserved_storage_bytes=0,
                        used_storage_bytes=0,
                        active_uploads=0,
                        updated_at=now,
                    )
                )
            await session.flush()
            row = await session.scalar(
                select(UserModel).where(UserModel.external_login == external_login)
            )
            if row is None:
                raise RuntimeError("User insert completed without a readable row")
            return User(id=row.id, external_login=row.external_login, created_at=row.created_at)

    async def create_project(self, *, owner_id: UUID, title: str, idempotency_key: str) -> Project:
        request_fingerprint = _fingerprint({"title": title})
        async with self._sessions.session() as session, session.begin():
            quota = await session.scalar(
                select(QuotaAccountModel)
                .where(QuotaAccountModel.user_id == owner_id)
                .with_for_update()
            )
            if quota is None:
                raise NotFoundError("Quota account not found")
            existing = await session.scalar(
                select(ProjectModel).where(
                    ProjectModel.owner_id == owner_id,
                    ProjectModel.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                if existing.request_fingerprint != request_fingerprint:
                    raise ConflictError("Idempotency key was reused with different project data")
                return _project(existing)
            count = await session.scalar(
                select(func.count())
                .select_from(ProjectModel)
                .where(ProjectModel.owner_id == owner_id)
            )
            if (count or 0) >= quota.max_projects:
                raise QuotaExceededError("Project quota exceeded")
            now = datetime.now(UTC)
            row = ProjectModel(
                id=new_uuid7(),
                owner_id=owner_id,
                title=title,
                lifecycle=ProjectLifecycle.DRAFT,
                version=1,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            return _project(row)

    async def list_projects(self, *, owner_id: UUID) -> list[Project]:
        async with self._sessions.session() as session:
            rows = (
                await session.scalars(
                    select(ProjectModel)
                    .where(ProjectModel.owner_id == owner_id)
                    .order_by(ProjectModel.created_at.desc())
                )
            ).all()
            return [_project(row) for row in rows]

    async def get_project(self, *, owner_id: UUID, project_id: UUID) -> Project:
        async with self._sessions.session() as session:
            row = await session.scalar(
                select(ProjectModel).where(
                    ProjectModel.id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
            )
            if row is None:
                raise NotFoundError("Project not found")
            return _project(row)

    async def create_upload_intent(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        display_name: str,
        content_type: str,
        byte_size: int,
        expires_at: datetime,
        idempotency_key: str,
    ) -> UploadIntent:
        request_fingerprint = _fingerprint(
            {"display_name": display_name, "content_type": content_type, "byte_size": byte_size}
        )
        async with self._sessions.session() as session, session.begin():
            project = await session.scalar(
                select(ProjectModel).where(
                    ProjectModel.id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
            )
            if project is None:
                raise NotFoundError("Project not found")
            quota = await session.scalar(
                select(QuotaAccountModel)
                .where(QuotaAccountModel.user_id == owner_id)
                .with_for_update()
            )
            if quota is None:
                raise NotFoundError("Quota account not found")
            now = datetime.now(UTC)
            expired = (
                await session.scalars(
                    select(UploadIntentModel)
                    .join(ProjectModel, ProjectModel.id == UploadIntentModel.project_id)
                    .where(
                        ProjectModel.owner_id == owner_id,
                        UploadIntentModel.state == UploadState.PENDING,
                        UploadIntentModel.expires_at <= now,
                    )
                    .with_for_update()
                )
            ).all()
            for stale in expired:
                quota.reserved_storage_bytes = max(
                    0, quota.reserved_storage_bytes - stale.declared_size_bytes
                )
                quota.active_uploads = max(0, quota.active_uploads - 1)
                stale.state = UploadState.EXPIRED
                stale.error_code = "UPLOAD_INTENT_EXPIRED"
                stale.updated_at = now
                stale_media = await session.get(
                    MediaAssetModel,
                    stale.media_asset_id,
                    with_for_update=True,
                )
                if stale_media is not None:
                    stale_media.status = MediaStatus.REJECTED
                    stale_media.error_code = "UPLOAD_INTENT_EXPIRED"
                    stale_media.updated_at = now
            existing = await session.scalar(
                select(UploadIntentModel).where(
                    UploadIntentModel.project_id == project_id,
                    UploadIntentModel.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                if existing.request_fingerprint != request_fingerprint:
                    raise ConflictError("Idempotency key was reused with different upload data")
                return _upload(existing)
            if quota.active_uploads >= quota.max_concurrent_uploads:
                raise QuotaExceededError("Concurrent upload quota exceeded")
            if (
                quota.used_storage_bytes + quota.reserved_storage_bytes + byte_size
                > quota.max_storage_bytes
            ):
                raise QuotaExceededError("Storage quota exceeded")
            intent_id = new_uuid7()
            media_id = new_uuid7()
            artifact_id = new_uuid7()
            media = MediaAssetModel(
                id=media_id,
                project_id=project_id,
                display_name=display_name,
                status=MediaStatus.UPLOAD_PENDING,
                original_artifact_id=artifact_id,
                proxy_artifact_id=None,
                probe=None,
                error_code=None,
                created_at=now,
                updated_at=now,
            )
            row = UploadIntentModel(
                id=intent_id,
                project_id=project_id,
                media_asset_id=media_id,
                original_artifact_id=artifact_id,
                staging_object_key=f"staging/{intent_id}",
                sealed_object_key=f"artifacts/{project_id}/{artifact_id}/original",
                display_name=display_name,
                declared_content_type=content_type,
                declared_size_bytes=byte_size,
                state=UploadState.PENDING,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                error_code=None,
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
            )
            quota.reserved_storage_bytes += byte_size
            quota.active_uploads += 1
            quota.updated_at = now
            session.add_all([media, row])
            await session.flush()
            return _upload(row)

    async def get_upload_intent(
        self, *, owner_id: UUID, project_id: UUID, upload_intent_id: UUID
    ) -> UploadIntent:
        async with self._sessions.session() as session:
            row = await session.scalar(
                select(UploadIntentModel)
                .join(ProjectModel, ProjectModel.id == UploadIntentModel.project_id)
                .where(
                    UploadIntentModel.id == upload_intent_id,
                    UploadIntentModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
            )
            if row is None:
                raise NotFoundError("Upload intent not found")
            return _upload(row)

    async def mark_upload_received(self, *, owner_id: UUID, upload_intent_id: UUID) -> MediaAsset:
        async with self._sessions.session() as session, session.begin():
            row = await session.scalar(
                select(UploadIntentModel)
                .join(ProjectModel, ProjectModel.id == UploadIntentModel.project_id)
                .where(
                    UploadIntentModel.id == upload_intent_id,
                    ProjectModel.owner_id == owner_id,
                )
                .with_for_update()
            )
            if row is None:
                raise NotFoundError("Upload intent not found")
            media = await session.get(MediaAssetModel, row.media_asset_id, with_for_update=True)
            if media is None:
                raise NotFoundError("Media asset not found")
            if row.state == UploadState.PENDING:
                now = datetime.now(UTC)
                row.state = UploadState.OBJECT_RECEIVED
                row.updated_at = now
                media.status = MediaStatus.OBJECT_RECEIVED
                media.updated_at = now
            return _media(media)

    async def reject_upload(self, *, upload_intent_id: UUID, error_code: str) -> None:
        async with self._sessions.session() as session, session.begin():
            row = await session.get(UploadIntentModel, upload_intent_id, with_for_update=True)
            if row is None or row.state in {UploadState.REJECTED, UploadState.ACCEPTED}:
                return
            project = await session.get(ProjectModel, row.project_id)
            if project is None:
                return
            quota = await session.scalar(
                select(QuotaAccountModel)
                .where(QuotaAccountModel.user_id == project.owner_id)
                .with_for_update()
            )
            if quota is not None:
                quota.reserved_storage_bytes = max(
                    0, quota.reserved_storage_bytes - row.declared_size_bytes
                )
                quota.active_uploads = max(0, quota.active_uploads - 1)
                quota.updated_at = datetime.now(UTC)
            row.state = UploadState.REJECTED
            row.error_code = error_code
            row.updated_at = datetime.now(UTC)
            media = await session.get(MediaAssetModel, row.media_asset_id, with_for_update=True)
            if media is not None:
                media.status = MediaStatus.REJECTED
                media.error_code = error_code
                media.updated_at = datetime.now(UTC)

    async def get_media_asset(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> MediaAsset:
        async with self._sessions.session() as session:
            row = await session.scalar(
                select(MediaAssetModel)
                .join(ProjectModel, ProjectModel.id == MediaAssetModel.project_id)
                .where(
                    MediaAssetModel.id == media_asset_id,
                    MediaAssetModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
            )
            if row is None:
                raise NotFoundError("Media asset not found")
            return _media(row)

    async def get_media_asset_internal(self, media_asset_id: UUID) -> MediaAsset:
        async with self._sessions.session() as session:
            row = await session.get(MediaAssetModel, media_asset_id)
            if row is None:
                raise NotFoundError("Media asset not found")
            return _media(row)

    async def get_upload_for_media_internal(self, media_asset_id: UUID) -> UploadIntent:
        async with self._sessions.session() as session:
            row = await session.scalar(
                select(UploadIntentModel).where(UploadIntentModel.media_asset_id == media_asset_id)
            )
            if row is None:
                raise NotFoundError("Upload intent not found")
            return _upload(row)

    async def get_artifact_for_owner(
        self, *, owner_id: UUID, project_id: UUID, artifact_id: UUID
    ) -> Artifact:
        async with self._sessions.session() as session:
            row = await session.scalar(
                select(ArtifactModel)
                .join(ProjectModel, ProjectModel.id == ArtifactModel.project_id)
                .where(
                    ArtifactModel.id == artifact_id,
                    ArtifactModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                    ArtifactModel.state == ArtifactState.AVAILABLE,
                )
            )
            if row is None:
                raise NotFoundError("Artifact not found")
            return _artifact(row)

    async def get_artifact_internal(self, artifact_id: UUID) -> Artifact | None:
        async with self._sessions.session() as session:
            row = await session.get(ArtifactModel, artifact_id)
            return _artifact(row) if row is not None else None

    async def set_media_status(
        self, media_asset_id: UUID, status: MediaStatus, *, error_code: str | None = None
    ) -> None:
        async with self._sessions.session() as session, session.begin():
            media = await session.get(MediaAssetModel, media_asset_id, with_for_update=True)
            if media is None:
                raise NotFoundError("Media asset not found")
            media.status = status
            media.error_code = error_code
            media.updated_at = datetime.now(UTC)

    async def mark_media_failed(self, media_asset_id: UUID, *, error_code: str) -> None:
        async with self._sessions.session() as session, session.begin():
            media = await session.get(MediaAssetModel, media_asset_id, with_for_update=True)
            if media is None:
                raise NotFoundError("Media asset not found")
            if media.status == MediaStatus.REJECTED:
                return
            media.status = MediaStatus.FAILED
            media.error_code = error_code
            media.updated_at = datetime.now(UTC)

    async def ensure_proxy_artifact_id(self, media_asset_id: UUID) -> UUID:
        async with self._sessions.session() as session, session.begin():
            media = await session.get(MediaAssetModel, media_asset_id, with_for_update=True)
            if media is None:
                raise NotFoundError("Media asset not found")
            if media.proxy_artifact_id is None:
                media.proxy_artifact_id = new_uuid7()
                media.updated_at = datetime.now(UTC)
            return media.proxy_artifact_id

    async def register_original(
        self,
        *,
        media_asset_id: UUID,
        media_type: str,
        byte_size: int,
        checksum_sha256: str,
        probe: MediaProbe,
        stage_execution_id: UUID,
    ) -> Artifact:
        async with self._sessions.session() as session, session.begin():
            upload = await session.scalar(
                select(UploadIntentModel)
                .where(UploadIntentModel.media_asset_id == media_asset_id)
                .with_for_update()
            )
            media = await session.get(MediaAssetModel, media_asset_id, with_for_update=True)
            if upload is None or media is None:
                raise NotFoundError("Media upload not found")
            existing = await session.get(ArtifactModel, upload.original_artifact_id)
            if existing is not None:
                return _artifact(existing)
            project = await session.get(ProjectModel, media.project_id)
            if project is None:
                raise NotFoundError("Project not found")
            quota = await session.scalar(
                select(QuotaAccountModel)
                .where(QuotaAccountModel.user_id == project.owner_id)
                .with_for_update()
            )
            if quota is None:
                raise NotFoundError("Quota account not found")
            projected = quota.used_storage_bytes + byte_size
            if projected > quota.max_storage_bytes:
                raise QuotaExceededError("Storage quota exceeded after media validation")
            now = datetime.now(UTC)
            row = ArtifactModel(
                id=upload.original_artifact_id,
                project_id=media.project_id,
                media_asset_id=media.id,
                kind=ArtifactKind.ORIGINAL_VIDEO,
                media_type=media_type,
                byte_size=byte_size,
                checksum_sha256=checksum_sha256,
                object_key=upload.sealed_object_key,
                retention_class=RetentionClass.SOURCE,
                state=ArtifactState.AVAILABLE,
                producer_stage_execution_id=stage_execution_id,
                created_at=now,
            )
            session.add(row)
            quota.reserved_storage_bytes = max(
                0, quota.reserved_storage_bytes - upload.declared_size_bytes
            )
            quota.used_storage_bytes = projected
            quota.active_uploads = max(0, quota.active_uploads - 1)
            quota.updated_at = now
            upload.state = UploadState.ACCEPTED
            upload.updated_at = now
            media.probe = {
                "format_name": probe.format_name,
                "duration_us": probe.duration_us,
                "width": probe.width,
                "height": probe.height,
                "frame_rate": probe.frame_rate,
                "video_codec": probe.video_codec,
                "audio_codec": probe.audio_codec,
                "stream_count": probe.stream_count,
            }
            media.status = MediaStatus.PROXY_GENERATING
            media.updated_at = now
            await session.flush()
            return _artifact(row)

    async def register_proxy(
        self,
        *,
        media_asset_id: UUID,
        artifact_id: UUID,
        object_key: str,
        byte_size: int,
        checksum_sha256: str,
        stage_execution_id: UUID,
    ) -> Artifact:
        async with self._sessions.session() as session, session.begin():
            media = await session.get(MediaAssetModel, media_asset_id, with_for_update=True)
            if media is None:
                raise NotFoundError("Media asset not found")
            existing = await session.get(ArtifactModel, artifact_id)
            if existing is not None:
                return _artifact(existing)
            original = await session.get(ArtifactModel, media.original_artifact_id)
            project = await session.get(ProjectModel, media.project_id)
            if original is None or project is None:
                raise NotFoundError("Validated original artifact not found")
            quota = await session.scalar(
                select(QuotaAccountModel)
                .where(QuotaAccountModel.user_id == project.owner_id)
                .with_for_update()
            )
            if quota is None or quota.used_storage_bytes + byte_size > quota.max_storage_bytes:
                raise QuotaExceededError("Storage quota exceeded while publishing proxy")
            now = datetime.now(UTC)
            row = ArtifactModel(
                id=artifact_id,
                project_id=media.project_id,
                media_asset_id=media.id,
                kind=ArtifactKind.PROXY_VIDEO,
                media_type="video/mp4",
                byte_size=byte_size,
                checksum_sha256=checksum_sha256,
                object_key=object_key,
                retention_class=RetentionClass.DERIVED_REUSABLE,
                state=ArtifactState.AVAILABLE,
                producer_stage_execution_id=stage_execution_id,
                created_at=now,
            )
            edge = ArtifactEdgeModel(
                id=new_uuid7(),
                parent_artifact_id=original.id,
                child_artifact_id=row.id,
                relation="derived_from",
                created_at=now,
            )
            session.add(row)
            await session.flush()
            session.add(edge)
            quota.used_storage_bytes += byte_size
            quota.updated_at = now
            media.proxy_artifact_id = artifact_id
            media.status = MediaStatus.READY
            media.error_code = None
            media.updated_at = now
            await session.flush()
            return _artifact(row)

    async def begin_stage(
        self,
        *,
        project_id: UUID,
        media_asset_id: UUID,
        workflow_id: str,
        stage_name: str,
        attempt: int,
        input_fingerprint: str,
        worker_id: str,
    ) -> UUID:
        async with self._sessions.session() as session, session.begin():
            idempotency_key = f"{stage_name}/{media_asset_id}/{input_fingerprint}/media-ingest-v1"
            existing = await session.scalar(
                select(StageExecutionModel).where(
                    StageExecutionModel.workflow_id == workflow_id,
                    StageExecutionModel.stage_name == stage_name,
                    StageExecutionModel.attempt == attempt,
                )
            )
            if existing is not None:
                if existing.input_fingerprint != input_fingerprint:
                    raise ConflictError("Stage attempt was reused with different inputs")
                return existing.id
            stage_id = new_uuid7()
            inserted_id = await session.scalar(
                postgres_insert(StageExecutionModel)
                .values(
                    id=stage_id,
                    project_id=project_id,
                    media_asset_id=media_asset_id,
                    workflow_id=workflow_id,
                    stage_name=stage_name,
                    scope_id=str(media_asset_id),
                    idempotency_key=idempotency_key,
                    input_fingerprint=input_fingerprint,
                    attempt=attempt,
                    status="running",
                    worker_id=worker_id,
                    error_code=None,
                    retryable=None,
                    started_at=datetime.now(UTC),
                    completed_at=None,
                )
                .on_conflict_do_nothing()
                .returning(StageExecutionModel.id)
            )
            if inserted_id is not None:
                return inserted_id
            duplicate = await session.scalar(
                select(StageExecutionModel).where(
                    or_(
                        (
                            (StageExecutionModel.workflow_id == workflow_id)
                            & (StageExecutionModel.stage_name == stage_name)
                            & (StageExecutionModel.attempt == attempt)
                        ),
                        (
                            (StageExecutionModel.idempotency_key == idempotency_key)
                            & (StageExecutionModel.attempt == attempt)
                        ),
                    )
                )
            )
            if duplicate is None:
                raise RuntimeError("Stage insert conflict completed without a readable row")
            if duplicate.input_fingerprint != input_fingerprint:
                raise ConflictError("Stage attempt was reused with different inputs")
            return duplicate.id

    async def finish_stage(
        self,
        stage_execution_id: UUID,
        *,
        status: str,
        error_code: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        async with self._sessions.session() as session, session.begin():
            row = await session.get(StageExecutionModel, stage_execution_id, with_for_update=True)
            if row is None:
                raise NotFoundError("Stage execution not found")
            row.status = status
            row.error_code = error_code
            row.retryable = retryable
            row.completed_at = datetime.now(UTC)
