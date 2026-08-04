from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from auto_video_sub_domain.errors import ValidationError


class ProjectLifecycle(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    DELETION_PENDING = "deletion_pending"
    DELETED = "deleted"


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    external_login: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    owner_id: UUID
    title: str
    lifecycle: ProjectLifecycle
    version: int
    created_at: datetime
    updated_at: datetime


def validate_project_title(value: str) -> str:
    title = " ".join(value.split())
    if not title:
        raise ValidationError("Project title is required", code="PROJECT_TITLE_REQUIRED")
    if len(title) > 160:
        raise ValidationError(
            "Project title must be 160 characters or fewer",
            code="PROJECT_TITLE_TOO_LONG",
        )
    return title
