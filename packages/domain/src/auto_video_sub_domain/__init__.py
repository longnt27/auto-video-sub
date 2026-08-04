"""Framework-independent domain package."""

from auto_video_sub_domain.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
    QuotaExceededError,
    ValidationError,
)
from auto_video_sub_domain.ids import new_uuid7
from auto_video_sub_domain.media import (
    Artifact,
    ArtifactKind,
    ArtifactState,
    MediaAsset,
    MediaLimits,
    MediaProbe,
    MediaStatus,
    RetentionClass,
    UploadIntent,
    UploadState,
    safe_display_name,
    validate_probe,
)
from auto_video_sub_domain.projects import Project, ProjectLifecycle, User, validate_project_title

__all__ = [
    "Artifact",
    "ArtifactKind",
    "ArtifactState",
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "DomainError",
    "MediaAsset",
    "MediaLimits",
    "MediaProbe",
    "MediaStatus",
    "NotFoundError",
    "Project",
    "ProjectLifecycle",
    "QuotaExceededError",
    "RetentionClass",
    "UploadIntent",
    "UploadState",
    "User",
    "ValidationError",
    "__version__",
    "new_uuid7",
    "safe_display_name",
    "validate_probe",
    "validate_project_title",
]

__version__ = "0.1.0"
