from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"replacement anchor not found in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "packages/domain/src/auto_video_sub_domain/media.py",
    '    SPEECH_ATTEMPT_ENVELOPE = "speech_attempt_envelope"\n',
    '    SPEECH_ATTEMPT_ENVELOPE = "speech_attempt_envelope"\n'
    '    RENDER_MANIFEST = "render_manifest"\n'
    '    RENDER_SUBTITLE_ASS = "render_subtitle_ass"\n'
    '    RENDERED_VIDEO = "rendered_video"\n'
    '    RENDER_VALIDATION_REPORT = "render_validation_report"\n',
)

replace_once(
    "packages/domain/src/auto_video_sub_domain/__init__.py",
    "from auto_video_sub_domain.projects import Project, ProjectLifecycle, User, validate_project_title\n",
    "from auto_video_sub_domain.projects import Project, ProjectLifecycle, User, validate_project_title\n"
    "from auto_video_sub_domain.rendering import OriginalAudioPolicy, RenderJob, RenderStatus\n",
)
replace_once(
    "packages/domain/src/auto_video_sub_domain/__init__.py",
    '    "OcrObservation",\n',
    '    "OcrObservation",\n    "OriginalAudioPolicy",\n',
)
replace_once(
    "packages/domain/src/auto_video_sub_domain/__init__.py",
    '    "RetentionClass",\n',
    '    "RenderJob",\n    "RenderStatus",\n    "RetentionClass",\n',
)

replace_once(
    "packages/application/src/auto_video_sub_application/__init__.py",
    "from auto_video_sub_application.services import (\n",
    "from auto_video_sub_application.render_ports import (\n"
    "    FrozenRenderInput,\n"
    "    RenderObjectStorage,\n"
    "    RenderProcessor,\n"
    "    RenderRepository,\n"
    "    RenderSnapshot,\n"
    "    RenderWorkflowControl,\n"
    "    RenderWorkflowRepository,\n"
    ")\n"
    "from auto_video_sub_application.rendering import RenderService\n"
    "from auto_video_sub_application.services import (\n",
)
replace_once(
    "packages/application/src/auto_video_sub_application/__init__.py",
    '    "IdentityService",\n',
    '    "FrozenRenderInput",\n    "IdentityService",\n',
)
replace_once(
    "packages/application/src/auto_video_sub_application/__init__.py",
    '    "ReadinessReport",\n',
    '    "ReadinessReport",\n'
    '    "RenderObjectStorage",\n'
    '    "RenderProcessor",\n'
    '    "RenderRepository",\n'
    '    "RenderService",\n'
    '    "RenderSnapshot",\n'
    '    "RenderWorkflowControl",\n'
    '    "RenderWorkflowRepository",\n',
)

replace_once(
    "packages/infrastructure/src/auto_video_sub_infrastructure/__init__.py",
    "# Import table mappings so Base.metadata always represents the full schema.\n",
    "# Import table mappings so Base.metadata always represents the full schema.\n"
    "from auto_video_sub_infrastructure import render_models as _render_models  # noqa: F401\n",
)
replace_once(
    "packages/infrastructure/src/auto_video_sub_infrastructure/__init__.py",
    "from auto_video_sub_infrastructure.repository import SqlAlchemyProductRepository\n",
    "from auto_video_sub_infrastructure.render_repository import SqlAlchemyRenderRepository\n"
    "from auto_video_sub_infrastructure.render_workflows import TemporalRenderWorkflowControl\n"
    "from auto_video_sub_infrastructure.repository import SqlAlchemyProductRepository\n",
)
replace_once(
    "packages/infrastructure/src/auto_video_sub_infrastructure/__init__.py",
    '    "SqlAlchemyProductRepository",\n',
    '    "SqlAlchemyProductRepository",\n    "SqlAlchemyRenderRepository",\n',
)
replace_once(
    "packages/infrastructure/src/auto_video_sub_infrastructure/__init__.py",
    '    "TemporalSpeechWorkflowControl",\n',
    '    "TemporalRenderWorkflowControl",\n    "TemporalSpeechWorkflowControl",\n',
)

replace_once(
    "packages/infrastructure/src/auto_video_sub_infrastructure/settings.py",
    '    temporal_translation_task_queue: str = "auto-video-sub-translation"\n',
    '    temporal_translation_task_queue: str = "auto-video-sub-translation"\n'
    '    temporal_render_task_queue: str = "auto-video-sub-render"\n',
)
replace_once(
    "packages/infrastructure/src/auto_video_sub_infrastructure/settings.py",
    '    rewrite_request_timeout_seconds: int = Field(default=90, ge=10, le=600)\n\n'
    '    worker_profile: str = "core"\n',
    '    rewrite_request_timeout_seconds: int = Field(default=90, ge=10, le=600)\n\n'
    '    # Phase 6 final rendering. Font checksum is deliberately blank until a reviewed local\n'
    '    # Noto Sans file is mounted; render admission fails closed when it is not pinned.\n'
    '    render_renderer_version: str = "ffmpeg-libass-v1"\n'
    '    render_font_path: str = ""\n'
    '    render_font_filename: str = "NotoSans-Regular.ttf"\n'
    '    render_font_checksum_sha256: str = ""\n'
    '    render_reduced_original_gain_ppm: int = Field(default=200_000, gt=0, lt=1_000_000)\n'
    '    render_timeout_seconds: int = Field(default=10_800, ge=60, le=43_200)\n'
    '    render_validation_timeout_seconds: int = Field(default=300, ge=10, le=3600)\n'
    '    render_duration_tolerance_us: int = Field(default=500_000, ge=0, le=5_000_000)\n\n'
    '    worker_profile: str = "core"\n',
)

replace_once(
    "packages/providers/src/auto_video_sub_providers/__init__.py",
    "from auto_video_sub_providers.ocr import RapidOcrProvider\n",
    "from auto_video_sub_providers.ocr import RapidOcrProvider\n"
    "from auto_video_sub_providers.render import FFmpegRenderProcessor, RenderProcessError\n",
)
replace_once(
    "packages/providers/src/auto_video_sub_providers/__init__.py",
    '    "FFmpegMediaProcessor",\n',
    '    "FFmpegMediaProcessor",\n    "FFmpegRenderProcessor",\n',
)
replace_once(
    "packages/providers/src/auto_video_sub_providers/__init__.py",
    '    "RewriteProviderError",\n',
    '    "RenderProcessError",\n    "RewriteProviderError",\n',
)

replace_once(
    "packages/infrastructure/src/auto_video_sub_infrastructure/render_repository.py",
    '            audio_object_key=str(item["audio_object_key"]),\n',
    '            audio_object_key=str(item["audio_object_key"]),\n'
    '            audio_checksum_sha256=str(item["audio_checksum_sha256"]),\n',
)
replace_once(
    "packages/infrastructure/src/auto_video_sub_infrastructure/render_repository.py",
    "                if RenderStatus(existing.status) in {RenderStatus.FAILED, RenderStatus.CANCELLED}:\n"
    "                    existing.status = RenderStatus.PROCESSING\n"
    "                    existing.workflow_id = None\n"
    "                    existing.error_code = None\n"
    "                    existing.version += 1\n"
    "                    existing.updated_at = now\n",
    "                if RenderStatus(existing.status) in {RenderStatus.FAILED, RenderStatus.CANCELLED}:\n"
    "                    existing.status = RenderStatus.PROCESSING\n"
    "                    existing.workflow_id = None\n"
    "                    existing.validation_artifact_id = None\n"
    "                    existing.validation_summary = None\n"
    "                    existing.error_code = None\n"
    "                    existing.version += 1\n"
    "                    existing.updated_at = now\n",
)
replace_once(
    "packages/infrastructure/src/auto_video_sub_infrastructure/render_repository.py",
    "            if row.output_artifact_id is not None:\n"
    "                artifact = await session.get(ArtifactModel, row.output_artifact_id)\n",
    "            if (\n"
    "                RenderStatus(row.status) is RenderStatus.SUCCEEDED\n"
    "                and row.output_artifact_id is not None\n"
    "            ):\n"
    "                artifact = await session.get(ArtifactModel, row.output_artifact_id)\n",
)
replace_once(
    "packages/infrastructure/src/auto_video_sub_infrastructure/render_repository.py",
    "                row.validation_summary = validation\n"
    "                row.status = RenderStatus.SUCCEEDED\n"
    "                row.error_code = None\n",
    "                row.validation_summary = validation\n"
    "                if validation is not None and validation.get(\"valid\") is True:\n"
    "                    row.status = RenderStatus.SUCCEEDED\n"
    "                    row.error_code = None\n"
    "                else:\n"
    "                    row.status = RenderStatus.FAILED\n"
    "                    row.error_code = \"RENDER_VALIDATION_FAILED\"\n",
)

replace_once(
    "packages/application/src/auto_video_sub_application/rendering.py",
    "        if snapshot.output_object_key is None:\n",
    "        if (\n"
    "            snapshot.record.status is not RenderStatus.SUCCEEDED\n"
    "            or snapshot.output_object_key is None\n"
    "        ):\n",
)

replace_once(
    "packages/infrastructure/src/auto_video_sub_infrastructure/speech_repository.py",
    "            else:\n"
    "                state.status = SpeechStatus.WAITING_FOR_REVIEW\n"
    "                state.error_code = None\n",
    "            elif all(\n"
    "                SpeechSegmentStatus(value) is SpeechSegmentStatus.FIT for value in statuses\n"
    "            ):\n"
    "                state.status = SpeechStatus.APPROVED\n"
    "                state.error_code = None\n"
    "            else:\n"
    "                state.status = SpeechStatus.WAITING_FOR_REVIEW\n"
    "                state.error_code = None\n",
)

replace_once(
    "apps/worker/src/auto_video_sub_worker/speech_workflow.py",
    "            await workflow.execute_activity(\n"
    "                \"finalize-speech-review-v1\",\n"
    "                payload,\n"
    "                start_to_close_timeout=timedelta(minutes=2),\n"
    "                retry_policy=local_retry,\n"
    "            )\n\n"
    "            while not self._approved:\n",
    "            speech_status = await workflow.execute_activity(\n"
    "                \"finalize-speech-review-v1\",\n"
    "                payload,\n"
    "                start_to_close_timeout=timedelta(minutes=2),\n"
    "                retry_policy=local_retry,\n"
    "            )\n"
    "            if speech_status == \"approved\":\n"
    "                self._approved = True\n\n"
    "            while not self._approved:\n",
)
replace_once(
    "apps/worker/src/auto_video_sub_worker/speech_workflow.py",
    "                    await workflow.execute_activity(\n"
    "                        \"finalize-speech-review-v1\",\n"
    "                        payload,\n"
    "                        start_to_close_timeout=timedelta(minutes=2),\n"
    "                        retry_policy=local_retry,\n"
    "                    )\n",
    "                    speech_status = await workflow.execute_activity(\n"
    "                        \"finalize-speech-review-v1\",\n"
    "                        payload,\n"
    "                        start_to_close_timeout=timedelta(minutes=2),\n"
    "                        retry_policy=local_retry,\n"
    "                    )\n"
    "                    if speech_status == \"approved\":\n"
    "                        self._approved = True\n",
)

replace_once(
    "apps/api/src/auto_video_sub_api/app.py",
    "    ProjectService,\n",
    "    ProjectService,\n    RenderService,\n",
)
replace_once(
    "apps/api/src/auto_video_sub_api/app.py",
    "from auto_video_sub_application.ports import (\n",
    "from auto_video_sub_application.render_ports import RenderRepository, RenderWorkflowControl\n"
    "from auto_video_sub_application.ports import (\n",
)
replace_once(
    "apps/api/src/auto_video_sub_api/app.py",
    "    SqlAlchemyProductRepository,\n",
    "    SqlAlchemyProductRepository,\n    SqlAlchemyRenderRepository,\n",
)
replace_once(
    "apps/api/src/auto_video_sub_api/app.py",
    "    TemporalSpeechWorkflowControl,\n",
    "    TemporalRenderWorkflowControl,\n    TemporalSpeechWorkflowControl,\n",
)
replace_once(
    "apps/api/src/auto_video_sub_api/app.py",
    "from auto_video_sub_api.routes import router\n",
    "from auto_video_sub_api.render_routes import router as render_router\n"
    "from auto_video_sub_api.routes import router\n",
)
replace_once(
    "apps/api/src/auto_video_sub_api/app.py",
    "    speech_workflows: SpeechWorkflowControl | None = None,\n"
    "    subtitle_style_repository: SubtitleStyleRepository | None = None,\n",
    "    speech_workflows: SpeechWorkflowControl | None = None,\n"
    "    render_repository: RenderRepository | None = None,\n"
    "    render_workflows: RenderWorkflowControl | None = None,\n"
    "    subtitle_style_repository: SubtitleStyleRepository | None = None,\n",
)
replace_once(
    "apps/api/src/auto_video_sub_api/app.py",
    "        resolved_subtitle_style_repository = subtitle_style_repository\n",
    "        resolved_render_repository = render_repository\n"
    "        if resolved_render_repository is None and sessions is not None:\n"
    "            resolved_render_repository = SqlAlchemyRenderRepository(sessions)\n"
    "        resolved_render_workflows = render_workflows or TemporalRenderWorkflowControl(\n"
    "            address=resolved_settings.temporal_address,\n"
    "            namespace=resolved_settings.temporal_namespace,\n"
    "            task_queue=resolved_settings.temporal_render_task_queue,\n"
    "        )\n"
    "        resolved_subtitle_style_repository = subtitle_style_repository\n",
)
replace_once(
    "apps/api/src/auto_video_sub_api/app.py",
    "        app.state.subtitle_style_service = (\n",
    "        app.state.render_service = (\n"
    "            RenderService(\n"
    "                repository=resolved_render_repository,\n"
    "                workflows=resolved_render_workflows,\n"
    "                storage=resolved_storage,\n"
    "                renderer_version=resolved_settings.render_renderer_version,\n"
    "                font_filename=resolved_settings.render_font_filename,\n"
    "                font_checksum_sha256=resolved_settings.render_font_checksum_sha256,\n"
    "                reduced_original_gain_ppm=(\n"
    "                    resolved_settings.render_reduced_original_gain_ppm\n"
    "                ),\n"
    "                download_url_ttl=timedelta(\n"
    "                    seconds=resolved_settings.download_url_ttl_seconds\n"
    "                ),\n"
    "            )\n"
    "            if resolved_render_repository is not None\n"
    "            else None\n"
    "        )\n"
    "        app.state.subtitle_style_service = (\n",
)
replace_once(
    "apps/api/src/auto_video_sub_api/app.py",
    "    application.include_router(router)\n",
    "    application.include_router(router)\n    application.include_router(render_router)\n",
)

replace_once(
    "apps/worker/src/auto_video_sub_worker/main.py",
    "import signal\n",
    "import signal\nfrom pathlib import Path\n",
)
replace_once(
    "apps/worker/src/auto_video_sub_worker/main.py",
    "    SqlAlchemyProductRepository,\n",
    "    SqlAlchemyProductRepository,\n    SqlAlchemyRenderRepository,\n",
)
replace_once(
    "apps/worker/src/auto_video_sub_worker/main.py",
    "    FFmpegMediaProcessor,\n",
    "    FFmpegMediaProcessor,\n    FFmpegRenderProcessor,\n",
)
replace_once(
    "apps/worker/src/auto_video_sub_worker/main.py",
    "from auto_video_sub_worker.media_workflow import MediaActivities\n",
    "from auto_video_sub_worker.media_workflow import MediaActivities\n"
    "from auto_video_sub_worker.render_activities import RenderActivities\n"
    "from auto_video_sub_worker.render_workflow import RenderWorkflow\n",
)
replace_once(
    "apps/worker/src/auto_video_sub_worker/main.py",
    "    speech_repository = SqlAlchemySpeechRepository(sessions)\n",
    "    speech_repository = SqlAlchemySpeechRepository(sessions)\n"
    "    render_repository = SqlAlchemyRenderRepository(sessions)\n",
)
replace_once(
    "apps/worker/src/auto_video_sub_worker/main.py",
    "    media_worker = Worker(\n",
    "    render_activities = RenderActivities(\n"
    "        repository=render_repository,\n"
    "        storage=storage,\n"
    "        processor=FFmpegRenderProcessor(\n"
    "            ffmpeg_path=settings.ffmpeg_path,\n"
    "            ffprobe_path=settings.ffprobe_path,\n"
    "            render_timeout_seconds=settings.render_timeout_seconds,\n"
    "            validation_timeout_seconds=settings.render_validation_timeout_seconds,\n"
    "            duration_tolerance_us=settings.render_duration_tolerance_us,\n"
    "        ),\n"
    "        font_path=Path(settings.render_font_path),\n"
    "    )\n"
    "    media_worker = Worker(\n",
)
replace_once(
    "apps/worker/src/auto_video_sub_worker/main.py",
    "    try:\n"
    "        return await _run_workers((media_worker, local_ai_worker), profile=\"core\")\n",
    "    render_worker = Worker(\n"
    "        temporal_client,\n"
    "        task_queue=settings.temporal_render_task_queue,\n"
    "        workflows=[RenderWorkflow],\n"
    "        activities=[\n"
    "            render_activities.freeze_manifest,\n"
    "            render_activities.render_video,\n"
    "            render_activities.validate_output,\n"
    "            render_activities.mark_failed,\n"
    "        ],\n"
    "    )\n"
    "    try:\n"
    "        return await _run_workers(\n"
    "            (media_worker, local_ai_worker, render_worker), profile=\"core\"\n"
    "        )\n",
)

replace_once(
    ".env.example",
    "TEMPORAL_TRANSLATION_TASK_QUEUE=auto-video-sub-translation\n",
    "TEMPORAL_TRANSLATION_TASK_QUEUE=auto-video-sub-translation\n"
    "TEMPORAL_RENDER_TASK_QUEUE=auto-video-sub-render\n",
)
replace_once(
    ".env.example",
    "REWRITE_REQUEST_TIMEOUT_SECONDS=90\n\nWORKER_PROFILE=core\n",
    "REWRITE_REQUEST_TIMEOUT_SECONDS=90\n\n"
    "# Phase 6 render uses an exact local font file. Set the SHA-256 before requesting a render.\n"
    "RENDER_RENDERER_VERSION=ffmpeg-libass-v1\n"
    "RENDER_FONT_HOST_PATH=./.local/fonts/NotoSans-Regular.ttf\n"
    "RENDER_FONT_PATH=/fonts/NotoSans-Regular.ttf\n"
    "RENDER_FONT_FILENAME=NotoSans-Regular.ttf\n"
    "RENDER_FONT_CHECKSUM_SHA256=\n"
    "RENDER_REDUCED_ORIGINAL_GAIN_PPM=200000\n"
    "RENDER_TIMEOUT_SECONDS=10800\n"
    "RENDER_VALIDATION_TIMEOUT_SECONDS=300\n"
    "RENDER_DURATION_TOLERANCE_US=500000\n\n"
    "WORKER_PROFILE=core\n",
)

replace_once(
    "deploy/compose.yaml",
    "  TEMPORAL_TRANSLATION_TASK_QUEUE: auto-video-sub-translation\n",
    "  TEMPORAL_TRANSLATION_TASK_QUEUE: auto-video-sub-translation\n"
    "  TEMPORAL_RENDER_TASK_QUEUE: auto-video-sub-render\n",
)
replace_once(
    "deploy/compose.yaml",
    "  REWRITE_REQUEST_TIMEOUT_SECONDS: ${REWRITE_REQUEST_TIMEOUT_SECONDS:-90}\n",
    "  REWRITE_REQUEST_TIMEOUT_SECONDS: ${REWRITE_REQUEST_TIMEOUT_SECONDS:-90}\n"
    "  RENDER_RENDERER_VERSION: ${RENDER_RENDERER_VERSION:-ffmpeg-libass-v1}\n"
    "  RENDER_FONT_PATH: /fonts/NotoSans-Regular.ttf\n"
    "  RENDER_FONT_FILENAME: ${RENDER_FONT_FILENAME:-NotoSans-Regular.ttf}\n"
    "  RENDER_FONT_CHECKSUM_SHA256: ${RENDER_FONT_CHECKSUM_SHA256:-}\n"
    "  RENDER_REDUCED_ORIGINAL_GAIN_PPM: ${RENDER_REDUCED_ORIGINAL_GAIN_PPM:-200000}\n"
    "  RENDER_TIMEOUT_SECONDS: ${RENDER_TIMEOUT_SECONDS:-10800}\n"
    "  RENDER_VALIDATION_TIMEOUT_SECONDS: ${RENDER_VALIDATION_TIMEOUT_SECONDS:-300}\n"
    "  RENDER_DURATION_TOLERANCE_US: ${RENDER_DURATION_TOLERANCE_US:-500000}\n",
)
replace_once(
    "deploy/compose.yaml",
    "    volumes:\n"
    "      - ${TTS_MODEL_HOST_PATH:-./.local/models/vieneu}:/models/vieneu:ro\n",
    "    volumes:\n"
    "      - ${TTS_MODEL_HOST_PATH:-./.local/models/vieneu}:/models/vieneu:ro\n"
    "      - ${RENDER_FONT_HOST_PATH:-./.local/fonts/NotoSans-Regular.ttf}:/fonts/NotoSans-Regular.ttf:ro\n",
)
