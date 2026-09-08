from datetime import UTC, datetime
from uuid import uuid4

import pytest
from auto_video_sub_application.provider_settings import TranslationProviderSettingsView
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


class CapturePrepareRepository(EstimateRepository):
    def __init__(self, source_texts: tuple[str, ...]) -> None:
        super().__init__(source_texts)
        self.prepare_kwargs: dict[str, object] = {}

    async def prepare(self, **kwargs: object):
        self.prepare_kwargs = kwargs
        raise RuntimeError("stop after prepare")


class NoopWorkflows:
    pass


class StaticProviderSettings:
    def __init__(
        self,
        *,
        provider: str = "openai",
        model: str = "gpt-5.6-luna",
        configured: bool = True,
    ) -> None:
        self.view = TranslationProviderSettingsView(
            provider=provider,
            model=model,
            api_key_configured=configured,
            api_key_hint="••••test" if configured else None,
        )

    async def get_active(self) -> TranslationProviderSettingsView:
        return self.view


def service(
    repository: EstimateRepository,
    *,
    provider_settings: StaticProviderSettings | None = None,
) -> TranslationService:
    return TranslationService(
        repository=repository,  # type: ignore[arg-type]
        workflows=NoopWorkflows(),  # type: ignore[arg-type]
        provider_settings=provider_settings or StaticProviderSettings(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_estimate_reports_scope_without_guessing_monetary_cost() -> None:
    result = await service(EstimateRepository(("你好世界", "我们走吧"))).estimate(
        owner_id=uuid4(),
        project_id=uuid4(),
        media_asset_id=uuid4(),
        preset=TonePreset.NATURAL,
    )

    assert result.source_characters == 8
    assert result.estimated_input_tokens == 256
    assert result.estimated_output_tokens == 128
    assert result.estimated_cost_micros == 0
    assert result.provider == "openai"
    assert result.model == "gpt-5.6-luna"


@pytest.mark.asyncio
async def test_estimate_requires_runtime_provider_configuration() -> None:
    with pytest.raises(ValidationError) as error:
        await service(
            EstimateRepository(("你好",)),
            provider_settings=StaticProviderSettings(configured=False),
        ).estimate(
            owner_id=uuid4(),
            project_id=uuid4(),
            media_asset_id=uuid4(),
            preset=TonePreset.NATURAL,
        )

    assert error.value.code == "TRANSLATION_PROVIDER_UNCONFIGURED"


@pytest.mark.asyncio
async def test_paid_translation_requires_explicit_confirmation() -> None:
    with pytest.raises(ValidationError) as error:
        await service(EstimateRepository(("你好",))).start(
            owner_id=uuid4(),
            project_id=uuid4(),
            media_asset_id=uuid4(),
            preset=TonePreset.NATURAL,
            confirm_paid=False,
        )

    assert error.value.code == "TRANSLATION_CONFIRMATION_REQUIRED"


@pytest.mark.asyncio
async def test_start_pins_runtime_provider_and_uses_no_guessed_budget() -> None:
    repository = CapturePrepareRepository(("你好世界", "我们走吧"))
    provider_settings = StaticProviderSettings(provider="deepseek", model="deepseek-v4-flash")

    with pytest.raises(RuntimeError, match="stop after prepare"):
        await service(repository, provider_settings=provider_settings).start(
            owner_id=uuid4(),
            project_id=uuid4(),
            media_asset_id=uuid4(),
            preset=TonePreset.NATURAL,
            confirm_paid=True,
        )

    assert repository.prepare_kwargs["provider"] == "deepseek"
    assert repository.prepare_kwargs["model"] == "deepseek-v4-flash"
    assert repository.prepare_kwargs["estimated_cost_micros"] == 0
    assert repository.prepare_kwargs["max_cost_micros"] == 0


def test_tone_catalog_is_server_owned_and_versioned() -> None:
    catalog = TranslationService.tone_catalog()

    assert [item.preset for item in catalog] == list(TonePreset)
    assert all(item.prompt_version.startswith("translation-") for item in catalog)
    assert all(len(item.checksum) == 64 for item in catalog)


def test_provider_catalog_is_server_owned() -> None:
    catalog = TranslationService.provider_catalog()

    assert {item.id for item in catalog} == {"openai", "deepseek", "openrouter"}
    assert all(item.base_url.startswith("https://") for item in catalog)
