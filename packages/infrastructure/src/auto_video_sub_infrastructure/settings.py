from __future__ import annotations

from functools import lru_cache

from pydantic import Field
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
    dependency_timeout_seconds: float = Field(default=3.0, gt=0, le=30)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
