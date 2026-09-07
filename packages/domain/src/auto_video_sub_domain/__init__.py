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
from auto_video_sub_domain.transcript import (
    ConsolidatedSegment,
    OcrObservation,
    SourceRevision,
    SourceRevisionOrigin,
    SubtitleRegion,
    SubtitleSegment,
    TranscriptStatus,
    consolidate_observations,
    normalize_ocr_text,
)

__all__ = [
    "Artifact",
    "ArtifactKind",
    "ArtifactState",
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "ConsolidatedSegment",
    "DomainError",
    "MediaAsset",
    "MediaLimits",
    "MediaProbe",
    "MediaStatus",
    "NotFoundError",
    "OcrObservation",
    "Project",
    "ProjectLifecycle",
    "QuotaExceededError",
    "RetentionClass",
    "SourceRevision",
    "SourceRevisionOrigin",
    "SubtitleRegion",
    "SubtitleSegment",
    "TranscriptStatus",
    "UploadIntent",
    "UploadState",
    "User",
    "ValidationError",
    "__version__",
    "consolidate_observations",
    "new_uuid7",
    "normalize_ocr_text",
    "safe_display_name",
    "validate_probe",
    "validate_project_title",
]

__version__ = "0.1.0"
