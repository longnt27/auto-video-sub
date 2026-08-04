from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from auto_video_sub_api.app import create_app
from auto_video_sub_application.ports import ObjectMetadata, SignedUpload
from auto_video_sub_domain import (
    Artifact,
    MediaAsset,
    MediaStatus,
    NotFoundError,
    Project,
    ProjectLifecycle,
    UploadIntent,
    UploadState,
    User,
    new_uuid7,
)
from auto_video_sub_infrastructure import Settings
from fastapi.testclient import TestClient


class FakeRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.projects: dict[UUID, Project] = {}
        self.project_keys: dict[tuple[UUID, str], UUID] = {}
        self.uploads: dict[UUID, UploadIntent] = {}
        self.upload_keys: dict[tuple[UUID, str], UUID] = {}
        self.media: dict[UUID, MediaAsset] = {}

    async def get_or_create_user(self, external_login: str) -> User:
        if external_login not in self.users:
            self.users[external_login] = User(new_uuid7(), external_login, datetime.now(UTC))
        return self.users[external_login]

    async def create_project(self, *, owner_id: UUID, title: str, idempotency_key: str) -> Project:
        key = (owner_id, idempotency_key)
        if key in self.project_keys:
            return self.projects[self.project_keys[key]]
        now = datetime.now(UTC)
        project = Project(new_uuid7(), owner_id, title, ProjectLifecycle.DRAFT, 1, now, now)
        self.projects[project.id] = project
        self.project_keys[key] = project.id
        return project

    async def list_projects(self, *, owner_id: UUID) -> list[Project]:
        return [project for project in self.projects.values() if project.owner_id == owner_id]

    async def get_project(self, *, owner_id: UUID, project_id: UUID) -> Project:
        project = self.projects.get(project_id)
        if project is None or project.owner_id != owner_id:
            raise NotFoundError("Project not found")
        return project

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
        await self.get_project(owner_id=owner_id, project_id=project_id)
        existing_id = self.upload_keys.get((project_id, idempotency_key))
        existing = self.uploads.get(existing_id) if existing_id is not None else None
        if existing is not None:
            return existing
        intent_id = new_uuid7()
        media_id = new_uuid7()
        artifact_id = new_uuid7()
        intent = UploadIntent(
            id=intent_id,
            project_id=project_id,
            media_asset_id=media_id,
            original_artifact_id=artifact_id,
            object_key=f"staging/{intent_id}",
            sealed_object_key=f"artifacts/{project_id}/{artifact_id}/original",
            display_name=display_name,
            declared_content_type=content_type,
            declared_size_bytes=byte_size,
            state=UploadState.PENDING,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )
        now = datetime.now(UTC)
        self.uploads[intent.id] = intent
        self.upload_keys[(project_id, idempotency_key)] = intent.id
        self.media[media_id] = MediaAsset(
            media_id,
            project_id,
            display_name,
            MediaStatus.UPLOAD_PENDING,
            artifact_id,
            None,
            None,
            None,
            now,
            now,
        )
        return intent

    async def get_upload_intent(
        self, *, owner_id: UUID, project_id: UUID, upload_intent_id: UUID
    ) -> UploadIntent:
        await self.get_project(owner_id=owner_id, project_id=project_id)
        intent = self.uploads.get(upload_intent_id)
        if intent is None or intent.project_id != project_id:
            raise NotFoundError("Upload intent not found")
        return intent

    async def mark_upload_received(self, *, owner_id: UUID, upload_intent_id: UUID) -> MediaAsset:
        intent = self.uploads[upload_intent_id]
        await self.get_project(owner_id=owner_id, project_id=intent.project_id)
        self.uploads[intent.id] = replace(intent, state=UploadState.OBJECT_RECEIVED)
        old = self.media[intent.media_asset_id]
        updated = MediaAsset(
            old.id,
            old.project_id,
            old.display_name,
            MediaStatus.OBJECT_RECEIVED,
            old.original_artifact_id,
            old.proxy_artifact_id,
            old.probe,
            old.error_code,
            old.created_at,
            datetime.now(UTC),
        )
        self.media[old.id] = updated
        return updated

    async def reject_upload(self, *, upload_intent_id: UUID, error_code: str) -> None:
        del error_code
        self.uploads.pop(upload_intent_id, None)

    async def get_media_asset(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> MediaAsset:
        await self.get_project(owner_id=owner_id, project_id=project_id)
        media = self.media.get(media_asset_id)
        if media is None or media.project_id != project_id:
            raise NotFoundError("Media asset not found")
        return media

    async def get_media_asset_internal(self, media_asset_id: UUID) -> MediaAsset:
        return self.media[media_asset_id]

    async def get_upload_for_media_internal(self, media_asset_id: UUID) -> UploadIntent:
        return next(item for item in self.uploads.values() if item.media_asset_id == media_asset_id)

    async def get_artifact_for_owner(
        self, *, owner_id: UUID, project_id: UUID, artifact_id: UUID
    ) -> Artifact:
        del owner_id, project_id, artifact_id
        raise NotFoundError("Artifact not found")


class FakeStorage:
    def sign_upload(
        self, *, object_key: str, content_type: str, byte_size: int, expires_at: datetime
    ) -> SignedUpload:
        del byte_size
        return SignedUpload(
            url=f"https://objects.test/{object_key}",
            method="PUT",
            headers={"content-type": content_type},
            expires_at=expires_at,
        )

    async def seal_upload(
        self,
        *,
        staging_key: str,
        sealed_key: str,
        expected_size: int,
        expected_content_type: str,
    ) -> ObjectMetadata:
        del staging_key, sealed_key
        return ObjectMetadata(expected_size, expected_content_type, "etag")

    async def delete_object(self, object_key: str) -> None:
        del object_key

    def sign_download(self, *, object_key: str, expires_at: datetime) -> str:
        del expires_at
        return f"https://objects.test/{object_key}"


class FakeWorkflows:
    def __init__(self) -> None:
        self.started: list[UUID] = []

    async def start_media_ingest(self, *, project_id: UUID, media_asset_id: UUID) -> str:
        del project_id
        self.started.append(media_asset_id)
        return f"media-ingest-v1/{media_asset_id}"


class ExplodingStorage(FakeStorage):
    async def seal_upload(
        self,
        *,
        staging_key: str,
        sealed_key: str,
        expected_size: int,
        expected_content_type: str,
    ) -> ObjectMetadata:
        del staging_key, sealed_key, expected_size, expected_content_type
        raise RuntimeError("secret storage detail")


def _headers(login: str, *, idempotency: str | None = None) -> dict[str, str]:
    headers = {
        "x-forwarded-tailscale-user-login": login,
        "x-internal-proxy-secret": "test-secret-that-is-at-least-32-characters",
    }
    if idempotency is not None:
        headers["idempotency-key"] = idempotency
    return headers


def test_owner_can_create_project_and_start_direct_upload() -> None:
    repository = FakeRepository()
    workflows = FakeWorkflows()
    settings = Settings(
        tailscale_auth_enabled=True,
        tailscale_allowed_logins_csv="one@example.com,two@example.com",
        trusted_identity_proxy_ips_csv="testclient",
        internal_proxy_secret="test-secret-that-is-at-least-32-characters",
    )
    app = create_app(
        settings=settings,
        probes=[],
        repository=repository,
        storage=FakeStorage(),
        workflows=workflows,
    )
    with TestClient(app) as client:
        created = client.post(
            "/v1/projects",
            headers=_headers("one@example.com", idempotency="project-0001"),
            json={"title": " Episode 01 "},
        )
        assert created.status_code == 201
        project_id = created.json()["id"]

        forbidden = client.get(
            f"/v1/projects/{project_id}",
            headers=_headers("two@example.com"),
        )
        assert forbidden.status_code == 404

        intent = client.post(
            f"/v1/projects/{project_id}/uploads",
            headers=_headers("one@example.com", idempotency="upload-0001"),
            json={"file_name": "source.mp4", "content_type": "video/mp4", "byte_size": 1234},
        )
        assert intent.status_code == 201
        assert intent.json()["upload"]["method"] == "PUT"

        completed = client.post(
            f"/v1/projects/{project_id}/uploads/{intent.json()['id']}/complete",
            headers=_headers("one@example.com"),
        )
        assert completed.status_code == 202
        assert completed.json()["status"] == "object_received"
        media_id = UUID(intent.json()["media_asset_id"])
        assert workflows.started == [media_id]

        repository.media[media_id] = replace(
            repository.media[media_id],
            status=MediaStatus.PROXY_GENERATING,
            proxy_artifact_id=new_uuid7(),
        )
        processing = client.get(
            f"/v1/projects/{project_id}/media/{media_id}",
            headers=_headers("one@example.com"),
        )
        assert processing.status_code == 200
        assert processing.json()["proxy_url"] is None


def test_authentication_and_upload_limits_fail_closed() -> None:
    app = create_app(
        settings=Settings(
            tailscale_auth_enabled=True,
            tailscale_allowed_logins_csv="one@example.com",
            trusted_identity_proxy_ips_csv="testclient",
            internal_proxy_secret="test-secret-that-is-at-least-32-characters",
            max_upload_bytes=100,
        ),
        probes=[],
        repository=FakeRepository(),
        storage=FakeStorage(),
        workflows=FakeWorkflows(),
    )
    with TestClient(app) as client:
        missing_proxy_secret = client.get(
            "/v1/projects",
            headers={"x-forwarded-tailscale-user-login": "one@example.com"},
        )
        assert missing_proxy_secret.status_code == 401

        project = client.post(
            "/v1/projects",
            headers=_headers("one@example.com", idempotency="project-0002"),
            json={"title": "Limits"},
        )
        response = client.post(
            f"/v1/projects/{project.json()['id']}/uploads",
            headers=_headers("one@example.com", idempotency="upload-0002"),
            json={"file_name": "huge.mp4", "content_type": "video/mp4", "byte_size": 101},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "UPLOAD_TOO_LARGE"


def test_unexpected_errors_use_the_safe_structured_envelope() -> None:
    app = create_app(
        settings=Settings(dev_auth_login="owner@example.com"),
        probes=[],
        repository=FakeRepository(),
        storage=ExplodingStorage(),
        workflows=FakeWorkflows(),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        project = client.post(
            "/v1/projects",
            headers={"idempotency-key": "project-error-0001"},
            json={"title": "Errors"},
        )
        intent = client.post(
            f"/v1/projects/{project.json()['id']}/uploads",
            headers={"idempotency-key": "upload-error-0001"},
            json={"file_name": "source.mp4", "content_type": "video/mp4", "byte_size": 1234},
        )
        response = client.post(
            f"/v1/projects/{project.json()['id']}/uploads/{intent.json()['id']}/complete"
        )

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert "secret storage detail" not in response.text
