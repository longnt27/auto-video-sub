"""Infrastructure adapters and configuration."""

from auto_video_sub_infrastructure.database import SessionProvider, create_engine
from auto_video_sub_infrastructure.probes import build_dependency_probes
from auto_video_sub_infrastructure.repository import SqlAlchemyProductRepository
from auto_video_sub_infrastructure.settings import Settings, get_settings
from auto_video_sub_infrastructure.storage import S3ObjectStorage
from auto_video_sub_infrastructure.transcript_repository import SqlAlchemyTranscriptRepository
from auto_video_sub_infrastructure.translation_repository import SqlAlchemyTranslationRepository
from auto_video_sub_infrastructure.translation_workflows import TemporalTranslationWorkflowControl
from auto_video_sub_infrastructure.workflows import TemporalWorkflowStarter

# Import Phase 4 table mappings so Base.metadata always represents the full schema.
from auto_video_sub_infrastructure import translation_models as _translation_models

__all__ = [
    "S3ObjectStorage",
    "SessionProvider",
    "Settings",
    "SqlAlchemyProductRepository",
    "SqlAlchemyTranscriptRepository",
    "SqlAlchemyTranslationRepository",
    "TemporalTranslationWorkflowControl",
    "TemporalWorkflowStarter",
    "build_dependency_probes",
    "create_engine",
    "get_settings",
]
