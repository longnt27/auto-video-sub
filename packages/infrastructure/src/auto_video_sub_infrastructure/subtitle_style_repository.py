from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from auto_video_sub_domain import (
    ConflictError,
    NotFoundError,
    SubtitleAlignment,
    SubtitleStyleDraft,
    SubtitleStyleVersion,
    new_uuid7,
)
from sqlalchemy import func, select

from auto_video_sub_infrastructure.database import SessionProvider
from auto_video_sub_infrastructure.models import MediaAssetModel, ProjectModel
from auto_video_sub_infrastructure.subtitle_style_models import SubtitleStyleVersionModel


def _style(row: SubtitleStyleVersionModel) -> SubtitleStyleVersion:
    return SubtitleStyleVersion(
        id=row.id,
        project_id=row.project_id,
        media_asset_id=row.media_asset_id,
        version=row.version,
        style=SubtitleStyleDraft(
            font_id=row.font_id,
            font_family=row.font_family,
            font_license=row.font_license,
            font_size_pct=row.font_size_ppm / 1_000_000,
            text_color=row.text_color,
            outline_color=row.outline_color,
            background_color=row.background_color,
            background_opacity_pct=row.background_opacity_pct,
            outline_px=row.outline_millipx / 1000,
            shadow_px=row.shadow_millipx / 1000,
            alignment=SubtitleAlignment(row.alignment),
        ),
        parent_version_id=row.parent_version_id,
        created_by=row.created_by,
        created_at=row.created_at,
    )


class SqlAlchemySubtitleStyleRepository:
    def __init__(self, sessions: SessionProvider) -> None:
        self._sessions = sessions

    async def _require_owned_media(
        self, session: object, *, owner_id: UUID, project_id: UUID, media_asset_id: UUID
    ) -> None:
        media_id = await session.scalar(  # type: ignore[attr-defined]
            select(MediaAssetModel.id)
            .join(ProjectModel, ProjectModel.id == MediaAssetModel.project_id)
            .where(
                MediaAssetModel.id == media_asset_id,
                MediaAssetModel.project_id == project_id,
                ProjectModel.owner_id == owner_id,
            )
        )
        if media_id is None:
            raise NotFoundError("Media asset not found")

    async def get_or_create_default(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        default_style: SubtitleStyleDraft,
    ) -> SubtitleStyleVersion:
        default_style.validate()
        async with self._sessions.session() as session, session.begin():
            await self._require_owned_media(
                session,
                owner_id=owner_id,
                project_id=project_id,
                media_asset_id=media_asset_id,
            )
            existing = await session.scalar(
                select(SubtitleStyleVersionModel)
                .where(SubtitleStyleVersionModel.media_asset_id == media_asset_id)
                .order_by(SubtitleStyleVersionModel.version.desc())
                .limit(1)
            )
            if existing is not None:
                return _style(existing)
            now = datetime.now(UTC)
            row = SubtitleStyleVersionModel(
                id=new_uuid7(),
                project_id=project_id,
                media_asset_id=media_asset_id,
                version=1,
                font_id=default_style.font_id,
                font_family=default_style.font_family,
                font_license=default_style.font_license,
                font_size_ppm=round(default_style.font_size_pct * 1_000_000),
                text_color=default_style.text_color,
                outline_color=default_style.outline_color,
                background_color=default_style.background_color,
                background_opacity_pct=default_style.background_opacity_pct,
                outline_millipx=round(default_style.outline_px * 1000),
                shadow_millipx=round(default_style.shadow_px * 1000),
                alignment=default_style.alignment.value,
                parent_version_id=None,
                created_by=owner_id,
                created_at=now,
            )
            session.add(row)
            await session.flush()
            return _style(row)

    async def create_version(
        self,
        *,
        owner_id: UUID,
        project_id: UUID,
        media_asset_id: UUID,
        expected_version: int,
        style: SubtitleStyleDraft,
    ) -> SubtitleStyleVersion:
        style.validate()
        async with self._sessions.session() as session, session.begin():
            await self._require_owned_media(
                session,
                owner_id=owner_id,
                project_id=project_id,
                media_asset_id=media_asset_id,
            )
            current = await session.scalar(
                select(SubtitleStyleVersionModel)
                .where(SubtitleStyleVersionModel.media_asset_id == media_asset_id)
                .order_by(SubtitleStyleVersionModel.version.desc())
                .limit(1)
                .with_for_update()
            )
            if current is None:
                raise ConflictError("Load the default subtitle style before editing")
            if current.version != expected_version:
                raise ConflictError("Subtitle style changed after it was loaded")
            latest_version = await session.scalar(
                select(func.max(SubtitleStyleVersionModel.version)).where(
                    SubtitleStyleVersionModel.media_asset_id == media_asset_id
                )
            )
            row = SubtitleStyleVersionModel(
                id=new_uuid7(),
                project_id=project_id,
                media_asset_id=media_asset_id,
                version=(latest_version or 0) + 1,
                font_id=style.font_id,
                font_family=style.font_family,
                font_license=style.font_license,
                font_size_ppm=round(style.font_size_pct * 1_000_000),
                text_color=style.text_color,
                outline_color=style.outline_color,
                background_color=style.background_color,
                background_opacity_pct=style.background_opacity_pct,
                outline_millipx=round(style.outline_px * 1000),
                shadow_millipx=round(style.shadow_px * 1000),
                alignment=style.alignment.value,
                parent_version_id=current.id,
                created_by=owner_id,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.flush()
            return _style(row)
