import json
from uuid import uuid4

import pytest
from auto_video_sub_application.translation_ports import (
    ContextExtractionRequest,
    TranslationBatchRequest,
    TranslationSourceSegment,
)
from auto_video_sub_domain import ContextEntity, TonePreset
from auto_video_sub_providers import OpenAIResponsesTranslationProvider, TranslationProviderError


def response(payload: dict[str, object], *, input_tokens: int = 10, output_tokens: int = 20):
    return {
        "id": "resp_test",
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": json.dumps(payload, ensure_ascii=False)}
                ],
            }
        ],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


@pytest.mark.asyncio
async def test_context_adapter_uses_strict_schema_and_untrusted_data_boundary() -> None:
    segment_id = uuid4()
    captured: dict[str, object] = {}

    def transport(payload: dict[str, object]):
        captured.update(payload)
        return response(
            {
                "summary": "Hai người đang chuẩn bị rời đi.",
                "entities": [
                    {
                        "kind": "character",
                        "source_forms": ["小明"],
                        "preferred_vietnamese": "Tiểu Minh",
                        "confidence": 0.9,
                        "ambiguous": False,
                        "notes": None,
                        "evidence_segment_ids": [str(segment_id)],
                    }
                ],
                "unresolved_questions": [],
            }
        )

    provider = OpenAIResponsesTranslationProvider(
        api_key="",
        model="configured-model",
        transport=transport,
    )
    result = await provider.extract_context(
        ContextExtractionRequest(
            project_id=uuid4(),
            media_asset_id=uuid4(),
            transcript_version=3,
            segments=(
                TranslationSourceSegment(
                    segment_id,
                    0,
                    1_000_000,
                    "小明，我们走吧",  # noqa: RUF001
                ),
            ),
            prompt_version="context-v1",
            instructions="Extract context faithfully.",
        )
    )

    assert result.entities[0].preferred_vietnamese == "Tiểu Minh"
    assert result.usage.input_tokens == 10
    assert captured["store"] is False
    assert "untrusted user content" in str(captured["instructions"])
    assert captured["text"]["format"]["strict"] is True  # type: ignore[index]


@pytest.mark.asyncio
async def test_batch_adapter_keeps_owned_segment_ids() -> None:
    first = TranslationSourceSegment(uuid4(), 0, 1_000_000, "你好")
    second = TranslationSourceSegment(uuid4(), 1_000_000, 2_000_000, "走吧")

    provider = OpenAIResponsesTranslationProvider(
        api_key="",
        model="configured-model",
        transport=lambda _: response(
            {
                "items": [
                    {"segment_id": str(first.id), "text": "Xin chào"},
                    {"segment_id": str(second.id), "text": "Đi thôi"},
                ]
            }
        ),
    )
    result = await provider.translate_batch(
        TranslationBatchRequest(
            batch_id=uuid4(),
            owned_segments=(first, second),
            overlap_segments=(),
            context_summary="Hai người trò chuyện.",
            glossary=(
                ContextEntity(
                    id=uuid4(),
                    kind="term",
                    source_forms=("你好",),
                    preferred_vietnamese="Xin chào",
                    confidence=1.0,
                    ambiguous=False,
                    notes=None,
                    evidence_segment_ids=(first.id,),
                ),
            ),
            preset=TonePreset.NATURAL,
            prompt_version="translation-natural-v1",
            instructions="Translate faithfully.",
        )
    )

    assert [item.segment_id for item in result.items] == [first.id, second.id]


@pytest.mark.asyncio
async def test_context_adapter_rejects_hallucinated_evidence_ids() -> None:
    source_id = uuid4()
    provider = OpenAIResponsesTranslationProvider(
        api_key="",
        model="configured-model",
        transport=lambda _: response(
            {
                "summary": "Tóm tắt",
                "entities": [
                    {
                        "kind": "character",
                        "source_forms": ["小明"],
                        "preferred_vietnamese": None,
                        "confidence": 0.5,
                        "ambiguous": True,
                        "notes": None,
                        "evidence_segment_ids": [str(uuid4())],
                    }
                ],
                "unresolved_questions": [],
            }
        ),
    )

    with pytest.raises(TranslationProviderError) as error:
        await provider.extract_context(
            ContextExtractionRequest(
                project_id=uuid4(),
                media_asset_id=uuid4(),
                transcript_version=1,
                segments=(TranslationSourceSegment(source_id, 0, 1, "小明"),),
                prompt_version="context-v1",
                instructions="Extract context.",
            )
        )
    assert error.value.code == "TRANSLATION_PROVIDER_RESPONSE_INVALID"
