from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from auto_video_sub_application.render_ports import (
    FrozenRenderInput,
    PublishedRenderArtifact,
    RenderSnapshot,
    RenderSpeechTrack,
)
from auto_video_sub_domain import (
    ArtifactKind,
    ArtifactState,
    ConflictError,
    MediaStatus,
    NotFoundError,
    RetentionClass,
    SpeechAttemptOutcome,
    SpeechSegmentStatus,
    SpeechStatus,
    SubtitleAlignment,
    SubtitleStyleDraft,
    TranslationStatus,
    new_uuid7,
)
from auto_video_sub_domain.rendering import OriginalAudioPolicy, RenderJob, RenderStatus
from sqlalchemy import select

from auto_video_sub_infrastructure.database import SessionProvider
from auto_video_sub_infrastructure.models import (
    ArtifactEdgeModel,
    ArtifactModel,
    MediaAssetModel,
    ProjectModel,
    SubtitleSegmentModel,
)
from auto_video_sub_infrastructure.render_models import RenderJobModel
from auto_video_sub_infrastructure.speech_models import (
    SpeechAttemptModel,
    SpeechSegmentStateModel,
    SpeechStateModel,
)
from auto_video_sub_infrastructure.subtitle_style_models import SubtitleStyleVersionModel
from auto_video_sub_infrastructure.translation_models import (
    TranslationRevisionModel,
    TranslationStateModel,
)


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _record(row: RenderJobModel) -> RenderJob:
    value = RenderJob(
        id=row.id,
        project_id=row.project_id,
        media_asset_id=row.media_asset_id,
        status=RenderStatus(row.status),
        workflow_id=row.workflow_id,
        input_fingerprint=row.input_fingerprint,
        audio_policy=OriginalAudioPolicy(row.audio_policy),
        original_audio_gain_ppm=row.original_audio_gain_ppm,
        renderer_version=row.renderer_version,
        font_filename=row.font_filename,
        font_checksum_sha256=row.font_checksum_sha256,
        manifest_artifact_id=row.manifest_artifact_id,
        subtitle_artifact_id=row.subtitle_artifact_id,
        output_artifact_id=row.output_artifact_id,
        validation_artifact_id=row.validation_artifact_id,
        error_code=row.error_code,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    value.validate()
    return value


def _style_from_payload(payload: dict[str, Any]) -> SubtitleStyleDraft:
    value = SubtitleStyleDraft(
        font_id=str(payload["font_id"]),
        font_family=str(payload["font_family"]),
        font_license=str(payload["font_license"]),
        font_size_pct=float(payload["font_size_pct"]),
        text_color=str(payload["text_color"]),
        outline_color=str(payload["outline_color"]),
        background_color=str(payload["background_color"]),
        background_opacity_pct=int(payload["background_opacity_pct"]),
        outline_px=float(payload["outline_px"]),
        shadow_px=float(payload["shadow_px"]),
        alignment=SubtitleAlignment(str(payload["alignment"])),
    )
    value.validate()
    return value


def _input(row: RenderJobModel) -> FrozenRenderInput:
    payload = row.manifest_payload
    media = payload["media"]
    style = payload["subtitle_style"]
    tracks = tuple(
        RenderSpeechTrack(
            segment_id=UUID(str(item["segment_id"])),
            ordinal=int(item["ordinal"]),
            start_us=int(item["start_us"]),
            end_us=int(item["end_us"]),
            text=str(item["text"]),
            translation_revision_id=UUID(str(item["translation_revision_id"])),
            speech_attempt_id=UUID(str(item["speech_attempt_id"])),
            audio_artifact_id=UUID(str(item["audio_artifact_id"])),
            audio_object_key=str(item["audio_object_key"]),
            audio_checksum_sha256=str(item["audio_checksum_sha256"]),
        )
        for item in payload["speech_tracks"]
    )
    return FrozenRenderInput(
        render_id=row.id,
        project_id=row.project_id,
        media_asset_id=row.media_asset_id,
        original_artifact_id=UUID(str(media["original_artifact_id"])),
        original_object_key=str(media["original_object_key"]),
        original_checksum_sha256=str(media["original_checksum_sha256"]),
        duration_us=int(media["duration_us"]),
        width=int(media["width"]),
        height=int(media["height"]),
        source_has_audio=bool(media["source_has_audio"]),
        transcript_version=int(payload["transcript_version"]),
        translation_policy_version_id=UUID(str(payload["translation_policy_version_id"])),
        subtitle_style_version_id=UUID(str(payload["subtitle_style_version_id"])),
        subtitle_style=_style_from_payload(style),
        speech_tracks=tracks,
        audio_policy=OriginalAudioPolicy(row.audio_policy),
        original_audio_gain_ppm=row.original_audio_gain_ppm,
        renderer_version=row.renderer_version,
        font_filename=row.font_filename,
        font_checksum_sha256=row.font_checksum_sha256,
        input_fingerprint=row.input_fingerprint,
    )


class SqlAlchemyRenderRepository:
    def __init__(self, sessions: SessionProvider) -> None:
        self._sessions = sessions

    async def prepare(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        audio_policy: OriginalAudioPolicy,
        original_audio_gain_ppm: int,
        renderer_version: str,
        font_filename: str,
        font_checksum_sha256: str,
    ) -> RenderJob:
        async with self._sessions.session() as session, session.begin():
            project = await session.scalar(
                select(ProjectModel).where(
                    ProjectModel.id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
            )
            if project is None:
                raise NotFoundError("Project not found")
            media = await session.get(MediaAssetModel, media_asset_id)
            if (
                media is None
                or media.project_id != project_id
                or MediaStatus(media.status) is not MediaStatus.READY
                or media.probe is None
            ):
                raise ConflictError("Media must be ready before rendering")
            original = await session.get(ArtifactModel, media.original_artifact_id)
            if original is None or ArtifactState(original.state) is not ArtifactState.AVAILABLE:
                raise ConflictError("Validated original video is unavailable")

            translation = await session.get(TranslationStateModel, media_asset_id)
            if (
                translation is None
                or TranslationStatus(translation.status) is not TranslationStatus.APPROVED
            ):
                raise ConflictError("Vietnamese translation must be approved before rendering")
            speech = await session.get(SpeechStateModel, media_asset_id)
            if speech is None or SpeechStatus(speech.status) not in {
                SpeechStatus.WAITING_FOR_REVIEW,
                SpeechStatus.APPROVED,
            }:
                raise ConflictError("Fitted Vietnamese speech is required before rendering")
            style = await session.scalar(
                select(SubtitleStyleVersionModel)
                .where(SubtitleStyleVersionModel.media_asset_id == media_asset_id)
                .order_by(SubtitleStyleVersionModel.version.desc())
                .limit(1)
            )
            if style is None:
                raise ConflictError("Load or save a subtitle style before rendering")

            segments = (
                await session.scalars(
                    select(SubtitleSegmentModel)
                    .where(SubtitleSegmentModel.media_asset_id == media_asset_id)
                    .order_by(SubtitleSegmentModel.ordinal)
                )
            ).all()
            tracks: list[dict[str, object]] = []
            for segment in segments:
                segment_state = await session.get(SpeechSegmentStateModel, segment.id)
                if (
                    segment_state is None
                    or SpeechSegmentStatus(segment_state.status) is not SpeechSegmentStatus.FIT
                    or segment_state.current_attempt_id is None
                ):
                    raise ConflictError(
                        "Every subtitle segment needs fitted speech before rendering"
                    )
                attempt = await session.get(SpeechAttemptModel, segment_state.current_attempt_id)
                if (
                    attempt is None
                    or attempt.outcome != SpeechAttemptOutcome.FIT.value
                    or attempt.final_audio_artifact_id is None
                ):
                    raise ConflictError("Selected speech attempt is not renderable")
                revision = await session.get(
                    TranslationRevisionModel, segment_state.translation_revision_id
                )
                if revision is None or revision.id != attempt.translation_revision_id:
                    raise ConflictError("Speech is stale for the current Vietnamese translation")
                audio = await session.get(ArtifactModel, attempt.final_audio_artifact_id)
                if audio is None or ArtifactState(audio.state) is not ArtifactState.AVAILABLE:
                    raise ConflictError("Fitted speech artifact is unavailable")
                tracks.append(
                    {
                        "segment_id": str(segment.id),
                        "ordinal": segment.ordinal,
                        "start_us": segment.start_us,
                        "end_us": segment.end_us,
                        "text": revision.text,
                        "translation_revision_id": str(revision.id),
                        "speech_attempt_id": str(attempt.id),
                        "audio_artifact_id": str(audio.id),
                        "audio_object_key": audio.object_key,
                        "audio_checksum_sha256": audio.checksum_sha256,
                    }
                )
            if not tracks:
                raise ConflictError("Render input has no subtitle segments")

            probe = media.probe
            payload: dict[str, Any] = {
                "schema_version": "render-manifest-v1",
                "project_id": str(project_id),
                "media_asset_id": str(media_asset_id),
                "media": {
                    "original_artifact_id": str(original.id),
                    "original_object_key": original.object_key,
                    "original_checksum_sha256": original.checksum_sha256,
                    "duration_us": int(probe["duration_us"]),
                    "width": int(probe["width"]),
                    "height": int(probe["height"]),
                    "source_has_audio": bool(probe.get("audio_codec")),
                },
                "transcript_version": translation.transcript_version,
                "translation_policy_version_id": str(translation.policy_version_id),
                "subtitle_style_version_id": str(style.id),
                "subtitle_style": {
                    "font_id": style.font_id,
                    "font_family": style.font_family,
                    "font_license": style.font_license,
                    "font_size_pct": style.font_size_ppm / 1_000_000,
                    "text_color": style.text_color,
                    "outline_color": style.outline_color,
                    "background_color": style.background_color,
                    "background_opacity_pct": style.background_opacity_pct,
                    "outline_px": style.outline_millipx / 1000,
                    "shadow_px": style.shadow_millipx / 1000,
                    "alignment": style.alignment,
                },
                "speech_tracks": tracks,
                "audio_policy": audio_policy.value,
                "original_audio_gain_ppm": original_audio_gain_ppm,
                "renderer_version": renderer_version,
                "font_filename": font_filename,
                "font_checksum_sha256": font_checksum_sha256,
            }
            input_fingerprint = _fingerprint(payload)
            existing = await session.scalar(
                select(RenderJobModel)
                .where(
                    RenderJobModel.media_asset_id == media_asset_id,
                    RenderJobModel.input_fingerprint == input_fingerprint,
                )
                .with_for_update()
            )
            now = datetime.now(UTC)
            if existing is not None:
                if RenderStatus(existing.status) in {RenderStatus.FAILED, RenderStatus.CANCELLED}:
                    existing.status = RenderStatus.PROCESSING
                    existing.workflow_id = None
                    existing.validation_artifact_id = None
                    existing.validation_summary = None
                    existing.error_code = None
                    existing.version += 1
                    existing.updated_at = now
                return _record(existing)

            row = RenderJobModel(
                id=new_uuid7(),
                project_id=project_id,
                media_asset_id=media_asset_id,
                status=RenderStatus.PROCESSING,
                workflow_id=None,
                input_fingerprint=input_fingerprint,
                audio_policy=audio_policy,
                original_audio_gain_ppm=original_audio_gain_ppm,
                renderer_version=renderer_version,
                font_filename=font_filename,
                font_checksum_sha256=font_checksum_sha256,
                manifest_payload=payload,
                manifest_artifact_id=None,
                subtitle_artifact_id=None,
                output_artifact_id=None,
                validation_artifact_id=None,
                validation_summary=None,
                error_code=None,
                version=1,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            return _record(row)

    async def bind_workflow(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        render_id: UUID,
        workflow_id: str,
    ) -> RenderJob:
        async with self._sessions.session() as session, session.begin():
            row = await session.scalar(
                select(RenderJobModel)
                .join(ProjectModel, ProjectModel.id == RenderJobModel.project_id)
                .where(
                    RenderJobModel.id == render_id,
                    RenderJobModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
                .with_for_update()
            )
            if row is None:
                raise NotFoundError("Render not found")
            if row.workflow_id is not None and row.workflow_id != workflow_id:
                raise ConflictError("Render is already bound to another workflow")
            row.workflow_id = workflow_id
            row.updated_at = datetime.now(UTC)
            return _record(row)

    async def snapshot(
        self, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> RenderSnapshot:
        async with self._sessions.session() as session:
            row = await session.scalar(
                select(RenderJobModel)
                .join(ProjectModel, ProjectModel.id == RenderJobModel.project_id)
                .where(
                    RenderJobModel.media_asset_id == media_asset_id,
                    RenderJobModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
                .order_by(RenderJobModel.created_at.desc())
                .limit(1)
            )
            if row is None:
                raise NotFoundError("Render not found")
            output_key = None
            if (
                RenderStatus(row.status) is RenderStatus.SUCCEEDED
                and row.output_artifact_id is not None
            ):
                artifact = await session.get(ArtifactModel, row.output_artifact_id)
                if (
                    artifact is not None
                    and ArtifactState(artifact.state) is ArtifactState.AVAILABLE
                ):
                    output_key = artifact.object_key
            return RenderSnapshot(
                record=_record(row),
                output_object_key=output_key,
                validation=(dict(row.validation_summary) if row.validation_summary else None),
            )

    async def mark_cancelled(
        self, *, owner_id: UUID, project_id: UUID, render_id: UUID
    ) -> RenderJob:
        async with self._sessions.session() as session, session.begin():
            row = await session.scalar(
                select(RenderJobModel)
                .join(ProjectModel, ProjectModel.id == RenderJobModel.project_id)
                .where(
                    RenderJobModel.id == render_id,
                    RenderJobModel.project_id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
                .with_for_update()
            )
            if row is None:
                raise NotFoundError("Render not found")
            if RenderStatus(row.status) is not RenderStatus.SUCCEEDED:
                row.status = RenderStatus.CANCELLED
                row.version += 1
                row.updated_at = datetime.now(UTC)
            return _record(row)

    async def get_input_internal(self, render_id: UUID) -> FrozenRenderInput:
        async with self._sessions.session() as session:
            row = await session.get(RenderJobModel, render_id)
            if row is None:
                raise NotFoundError("Render not found")
            return _input(row)

    async def register_artifact(
        self,
        *,
        render_id: UUID,
        role: str,
        artifact: PublishedRenderArtifact,
        validation: dict[str, object] | None = None,
    ) -> RenderJob:
        field_by_role = {
            "manifest": "manifest_artifact_id",
            "subtitle": "subtitle_artifact_id",
            "output": "output_artifact_id",
            "validation": "validation_artifact_id",
        }
        field = field_by_role.get(role)
        if field is None:
            raise ValueError(f"Unknown render artifact role: {role}")
        async with self._sessions.session() as session, session.begin():
            row = await session.get(RenderJobModel, render_id, with_for_update=True)
            if row is None:
                raise NotFoundError("Render not found")
            existing = await session.get(ArtifactModel, artifact.id)
            now = datetime.now(UTC)
            if existing is None:
                kind = {
                    "manifest": ArtifactKind.RENDER_MANIFEST,
                    "subtitle": ArtifactKind.RENDER_SUBTITLE_ASS,
                    "output": ArtifactKind.RENDERED_VIDEO,
                    "validation": ArtifactKind.RENDER_VALIDATION_REPORT,
                }[role]
                session.add(
                    ArtifactModel(
                        id=artifact.id,
                        project_id=row.project_id,
                        media_asset_id=row.media_asset_id,
                        kind=kind,
                        media_type=artifact.media_type,
                        byte_size=artifact.byte_size,
                        checksum_sha256=artifact.checksum_sha256,
                        object_key=artifact.object_key,
                        retention_class=RetentionClass.DERIVED_REUSABLE,
                        state=ArtifactState.AVAILABLE,
                        producer_stage_execution_id=None,
                        created_at=now,
                    )
                )
                await session.flush()
            setattr(row, field, artifact.id)
            payload = row.manifest_payload
            edge_specs: list[tuple[UUID, UUID, str]] = []
            original_id = UUID(str(payload["media"]["original_artifact_id"]))
            if role == "manifest":
                edge_specs.append((original_id, artifact.id, "describes"))
            elif role == "subtitle" and row.manifest_artifact_id is not None:
                edge_specs.append((row.manifest_artifact_id, artifact.id, "materialized_as"))
            elif role == "output":
                edge_specs.append((original_id, artifact.id, "video_source"))
                if row.manifest_artifact_id is not None:
                    edge_specs.append((row.manifest_artifact_id, artifact.id, "rendered_from"))
                if row.subtitle_artifact_id is not None:
                    edge_specs.append((row.subtitle_artifact_id, artifact.id, "subtitle_source"))
                for item in payload["speech_tracks"]:
                    edge_specs.append(
                        (UUID(str(item["audio_artifact_id"])), artifact.id, "mixed_from")
                    )
                row.status = RenderStatus.VALIDATING
            elif role == "validation" and row.output_artifact_id is not None:
                edge_specs.append((row.output_artifact_id, artifact.id, "validated_by"))
                row.validation_summary = validation
                if validation is not None and validation.get("valid") is True:
                    row.status = RenderStatus.SUCCEEDED
                    row.error_code = None
                else:
                    row.status = RenderStatus.FAILED
                    row.error_code = "RENDER_VALIDATION_FAILED"
            for parent_id, child_id, relation in edge_specs:
                existing_edge = await session.scalar(
                    select(ArtifactEdgeModel).where(
                        ArtifactEdgeModel.parent_artifact_id == parent_id,
                        ArtifactEdgeModel.child_artifact_id == child_id,
                        ArtifactEdgeModel.relation == relation,
                    )
                )
                if existing_edge is None:
                    session.add(
                        ArtifactEdgeModel(
                            id=new_uuid7(),
                            parent_artifact_id=parent_id,
                            child_artifact_id=child_id,
                            relation=relation,
                            created_at=now,
                        )
                    )
            row.version += 1
            row.updated_at = now
            await session.flush()
            return _record(row)

    async def set_status(
        self,
        render_id: UUID,
        status: RenderStatus,
        *,
        error_code: str | None = None,
    ) -> None:
        async with self._sessions.session() as session, session.begin():
            row = await session.get(RenderJobModel, render_id, with_for_update=True)
            if row is None:
                return
            row.status = status
            row.error_code = error_code
            row.version += 1
            row.updated_at = datetime.now(UTC)
