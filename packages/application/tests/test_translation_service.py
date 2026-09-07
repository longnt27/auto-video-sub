from datetime import UTC, datetime
from uuid import uuid4

import pytest

from auto_video_sub_application.translation import TranslationService
from auto_video_sub_domain import (
    SourceRevision,
    SourceRevisionOrigin,
    SubtitleSegment,
    TonePreset,
    ValidationError,
)


class EstimateRepository:
    def __init__(self, source_texts: tuple[str, ...]) -> None:
        now = datetime.now(UTC)
        project_id = uuid4()
        media_asset_id = uuid4()
        self.segments = tuple(
            SubtitleSegment(
                id=(segment_id := uuid4()),
                project_id=project_id,
                media_asset_id=media_asset_id,
                ordinal=index,
                start_us=index * 1_000_000,
                end_us=(index + 1) * 1_000_000,
                current_revision=SourceRevision(
                    id=uuid4(),
                    subtitle_segment_id=segment_id,
                    version=1,
                    text=text,
                    origin=SourceRevisionOrigin.USER,
                    confidence=None,
                    editor_id=uuid4(),
                    parent_revision_id=None,
                    created_at=now,
                ),
                version=1,
                created_at=now,
                updated_at=now,
            )
            for index, text in enumerate(source_texts)
        )

    async def source_for_estimate(self, **_: object):
        return 4, self.segments


class NoopWorkflows:
    pass


def service(repository: EstimateRepository) -> TranslationService:
    return TranslationService(
        repository=repository,  # type: ignore[arg-type]
        workflows=NoopWorkflows(),  # type: ignore[arg-type]
        provider="openai",
        model="configured-model",
        input_cost_micros_per_million_tokens=2_000_000,
        output_cost_micros_per_million_tokens=8_000_000,
    )


@pytest.mark.asyncio
async def test_estimate_is_conservative_and_uses_configured_price_snapshot() -> None:
    result = await service(EstimateRepository(("你好世界", "我们走吧"))).estimate(
        owner_id=uuid4(),
        project_id=uuid4(),
        media_asset_id=uuid4(),
        preset=TonePreset.NATURAL,
    )

    assert result.source_characters == 8
    assert result.estimated_input_tokens == 256
    assert result.estimated_output_tokens == 128
    assert result.estimated_cost_micros == 1536


@pytest.mark.asyncio
async def test_paid_translation_requires_explicit_confirmation() -> None:
    with pytest.raises(ValidationError) as error:
        await service(EstimateRepository(("你好",))).start(
            owner_id=uuid4(),
            project_id=uuid4(),
            media_asset_id=uuid4(),
            preset=TonePreset.NATURAL,
            confirm_paid=False,
            max_cost_micros=100_000,
        )

    assert error.value.code == "TRANSLATION_CONFIRMATION_REQUIRED"


@pytest.mark.asyncio
async def test_confirmed_ceiling_must_cover_current_estimate() -> None:
    with pytest.raises(ValidationError) as error:
        await service(EstimateRepository(("你好",))).start(
            owner_id=uuid4(),
            project_id=uuid4(),
            media_asset_id=uuid4(),
            preset=TonePreset.FORMAL,
            confirm_paid=True,
            max_cost_micros=1,
        )

    assert error.value.code == "TRANSLATION_BUDGET_CONFIRMATION_EXCEEDED"


def test_tone_catalog_is_server_owned_and_versioned() -> None:
    catalog = TranslationService.tone_catalog()

    assert [item.preset for item in catalog] == list(TonePreset)
    assert all(item.prompt_version.startswith("translation-") for item in catalog)
    assert all(len(item.checksum) == 64 for item in catalog)
