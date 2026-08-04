from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from auto_video_sub_domain import (
    Artifact,
    ConflictError,
    MediaAsset,
    MediaLimits,
    MediaStatus,
    Project,
    UploadIntent,
    UploadState,
    User,
    ValidationError,
    safe_display_name,
    validate_project_title,
)

from auto_video_sub_application.ports import (
    ObjectStorage,
    ProductRepository,
    SignedUpload,
    WorkflowStarter,
)


@dataclass(frozen=True, slots=True)
class UploadGrant:
    intent: UploadIntent
    signed_upload: SignedUpload


@dataclass(frozen=True, slots=True)
class MediaView:
    media: MediaAsset
    proxy_url: str | None
    proxy_url_expires_at: datetime | None


class IdentityService:
    def __init__(self, repository: ProductRepository) -> None:
        self._repository = repository

    async def resolve(self, external_login: str) -> User:
        normalized = external_login.strip().casefold()
        if not normalized or len(normalized) > 320:
            raise ValidationError("Invalid external identity", code="AUTH_IDENTITY_INVALID")
        return await self._repository.get_or_create_user(normalized)


class ProjectService:
    def __init__(self, repository: ProductRepository) -> None:
        self._repository = repository

    async def create(self, *, owner_id: UUID, title: str, idempotency_key: str) -> Project:
        return await self._repository.create_project(
            owner_id=owner_id,
            title=validate_project_title(title),
            idempotency_key=idempotency_key,
        )

    async def list(self, *, owner_id: UUID) -> list[Project]:
        return await self._repository.list_projects(owner_id=owner_id)

    async def get(self, *, owner_id: UUID, project_id: UUID) -> Project:
        return await self._repository.get_project(owner_id=owner_id, project_id=project_id)


class UploadService:
    def __init__(
        self,
        *,
        repository: ProductRepository,
        storage: ObjectStorage,
        workflows: WorkflowStarter,
        limits: MediaLimits,
        upload_url_ttl: timedelta,
        download_url_ttl: timedelta,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._workflows = workflows
        self._limits = limits
        self._upload_url_ttl = upload_url_ttl
        self._download_url_ttl = download_url_ttl

    async def create_intent(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        file_name: str,
        content_type: str,
        byte_size: int,
        idempotency_key: str,
    ) -> UploadGrant:
        self._limits.validate_upload_declaration(byte_size=byte_size, content_type=content_type)
        now = datetime.now(UTC)
        expires_at = now + self._upload_url_ttl
        intent = await self._repository.create_upload_intent(
            owner_id=owner_id,
            project_id=project_id,
            display_name=safe_display_name(file_name),
            content_type=content_type,
            byte_size=byte_size,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
        )
        if intent.state is not UploadState.PENDING:
            raise ConflictError("Upload intent is no longer pending")
        signed = self._storage.sign_upload(
            object_key=intent.object_key,
            content_type=intent.declared_content_type,
            byte_size=intent.declared_size_bytes,
            expires_at=intent.expires_at,
        )
        return UploadGrant(intent=intent, signed_upload=signed)

    async def complete(
        self, *, owner_id: UUID, project_id: UUID, upload_intent_id: UUID
    ) -> MediaAsset:
        intent = await self._repository.get_upload_intent(
            owner_id=owner_id,
            project_id=project_id,
            upload_intent_id=upload_intent_id,
        )
        if intent.state is UploadState.PENDING:
            if intent.expires_at <= datetime.now(UTC):
                await self._repository.reject_upload(
                    upload_intent_id=intent.id,
                    error_code="UPLOAD_INTENT_EXPIRED",
                )
                raise ConflictError("Upload intent has expired")
            try:
                await self._storage.seal_upload(
                    staging_key=intent.object_key,
                    sealed_key=intent.sealed_object_key,
                    expected_size=intent.declared_size_bytes,
                    expected_content_type=intent.declared_content_type,
                )
            except ValidationError as error:
                await self._repository.reject_upload(
                    upload_intent_id=intent.id,
                    error_code=error.code,
                )
                raise
            media = await self._repository.mark_upload_received(
                owner_id=owner_id,
                upload_intent_id=intent.id,
            )
        elif intent.state in {UploadState.OBJECT_RECEIVED, UploadState.ACCEPTED}:
            media = await self._repository.get_media_asset(
                owner_id=owner_id,
                project_id=project_id,
                media_asset_id=intent.media_asset_id,
            )
        else:
            raise ConflictError(f"Upload intent cannot be completed from state {intent.state}")

        await self._workflows.start_media_ingest(
            project_id=project_id,
            media_asset_id=intent.media_asset_id,
        )
        return media

    async def get_media(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> MediaView:
        media = await self._repository.get_media_asset(
            owner_id=owner_id,
            project_id=project_id,
            media_asset_id=media_asset_id,
        )
        if media.status is not MediaStatus.READY or media.proxy_artifact_id is None:
            return MediaView(media=media, proxy_url=None, proxy_url_expires_at=None)
        artifact: Artifact = await self._repository.get_artifact_for_owner(
            owner_id=owner_id,
            project_id=project_id,
            artifact_id=media.proxy_artifact_id,
        )
        expires_at = datetime.now(UTC) + self._download_url_ttl
        return MediaView(
            media=media,
            proxy_url=self._storage.sign_download(
                object_key=artifact.object_key,
                expires_at=expires_at,
            ),
            proxy_url_expires_at=expires_at,
        )
