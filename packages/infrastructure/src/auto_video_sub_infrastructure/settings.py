from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    service_name: str = "auto-video-sub"
    service_version: str = "0.1.0"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/auto_video_sub"
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "auto-video-sub-workflow"
    object_store_endpoint: str = "http://localhost:3900"
    object_store_bucket: str = "auto-video-sub-local"
    object_store_region: str = "garage"
    object_store_access_key: str = "replace-me"
    object_store_secret_key: str = "replace-me"
    public_object_store_base_url: str = "http://127.0.0.1:3900"
    dependency_timeout_seconds: float = Field(default=3.0, gt=0, le=30)

    tailscale_auth_enabled: bool = False
    tailscale_allowed_logins_csv: str = "owner@example.com"
    trusted_identity_proxy_ips_csv: str = "127.0.0.1,::1"
    internal_proxy_secret: str = "local-development-proxy-secret"
    dev_auth_login: str = "owner@example.com"
    cors_allowed_origins_csv: str = "http://127.0.0.1:3100,http://localhost:3100"

    upload_url_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    download_url_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    max_upload_bytes: int = Field(default=2 * 1024**3, gt=0)
    max_media_duration_seconds: int = Field(default=3 * 60 * 60, gt=0)
    max_media_width: int = Field(default=3840, ge=320, le=7680)
    max_media_height: int = Field(default=2160, ge=240, le=4320)
    max_media_frame_rate: float = Field(default=60.0, gt=0, le=240)
    max_media_streams: int = Field(default=16, ge=1, le=64)
    allowed_upload_content_types_csv: str = "video/mp4,video/quicktime,video/x-matroska,video/webm"
    default_max_projects: int = Field(default=10, ge=1, le=1000)
    default_max_concurrent_uploads: int = Field(default=1, ge=1, le=100)
    default_max_storage_bytes: int = Field(default=4 * 1024**3, gt=0)

    temporal_media_task_queue: str = "auto-video-sub-media"
    temporal_local_ai_task_queue: str = "auto-video-sub-local-ai"
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    media_probe_timeout_seconds: int = Field(default=60, ge=5, le=600)
    proxy_timeout_seconds: int = Field(default=7200, ge=60, le=43_200)

    @staticmethod
    def _csv(value: str) -> tuple[str, ...]:
        return tuple(item.strip() for item in value.split(",") if item.strip())

    @property
    def tailscale_allowed_logins(self) -> tuple[str, ...]:
        return tuple(item.casefold() for item in self._csv(self.tailscale_allowed_logins_csv))

    @property
    def trusted_identity_proxy_ips(self) -> tuple[str, ...]:
        return self._csv(self.trusted_identity_proxy_ips_csv)

    @property
    def cors_allowed_origins(self) -> tuple[str, ...]:
        return self._csv(self.cors_allowed_origins_csv)

    @property
    def allowed_upload_content_types(self) -> frozenset[str]:
        return frozenset(self._csv(self.allowed_upload_content_types_csv))

    @model_validator(mode="after")
    def validate_tailnet_authentication(self) -> Settings:
        if not self.tailscale_auth_enabled:
            return self
        if not self.tailscale_allowed_logins:
            raise ValueError("Tailnet authentication requires at least one allowed login")
        if not self.trusted_identity_proxy_ips:
            raise ValueError("Tailnet authentication requires a trusted proxy IP or CIDR")
        if len(self.internal_proxy_secret) < 32 or self.internal_proxy_secret in {
            "local-development-proxy-secret",
            "replace-me",
        }:
            raise ValueError("Tailnet authentication requires a distinct 32+ character secret")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
