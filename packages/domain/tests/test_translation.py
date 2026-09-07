from datetime import UTC, datetime
from uuid import uuid4

import pytest

from auto_video_sub_domain import (
    ContextEntity,
    ContextVersion,
    TonePreset,
    TranslationRevision,
    TranslationRevisionOrigin,
    ValidationError,
    contains_han,
    plan_translation_batches,
    validate_translation_items,
)


def test_translation_batch_planning_preserves_owned_ids_and_overlap() -> None:
    segments = tuple((uuid4(), index * 60_000_000, (index + 1) * 60_000_000) for index in range(7))

    plans = plan_translation_batches(segments, max_owned_segments=3, overlap_segments=1)

    assert [len(plan.owned_segment_ids) for plan in plans] == [3, 3, 1]
    assert plans[0].overlap_segment_ids == (segments[3][0],)
    assert plans[1].overlap_segment_ids == (segments[2][0], segments[6][0])
    assert plans[2].overlap_segment_ids == (segments[5][0],)


def test_translation_validation_requires_exact_owned_ids() -> None:
    first = uuid4()
    second = uuid4()

    validated = validate_translation_items(
        owned_segment_ids=(first, second),
        items=((second, "Xin chào"), (first, "Đi thôi")),
    )

    assert validated == ((second, "Xin chào"), (first, "Đi thôi"))
    with pytest.raises(ValidationError) as error:
        validate_translation_items(owned_segment_ids=(first, second), items=((first, "Xin chào"),))
    assert error.value.code == "TRANSLATION_VALIDATION_MISSING_ID"


def test_translation_validation_rejects_unknown_and_duplicate_ids() -> None:
    segment_id = uuid4()
    with pytest.raises(ValidationError) as unknown:
        validate_translation_items(
            owned_segment_ids=(segment_id,),
            items=((uuid4(), "Không hợp lệ"),),
        )
    assert unknown.value.code == "TRANSLATION_VALIDATION_UNKNOWN_ID"

    with pytest.raises(ValidationError) as duplicate:
        validate_translation_items(
            owned_segment_ids=(segment_id,),
            items=((segment_id, "Một"), (segment_id, "Hai")),
        )
    assert duplicate.value.code == "TRANSLATION_VALIDATION_DUPLICATE_ID"


def test_context_version_validates_evidence_and_entity_shape() -> None:
    entity = ContextEntity(
        id=uuid4(),
        kind="character",
        source_forms=("小明",),
        preferred_vietnamese="Tiểu Minh",
        confidence=0.91,
        ambiguous=False,
        notes=None,
        evidence_segment_ids=(uuid4(),),
    )
    context = ContextVersion(
        id=uuid4(),
        project_id=uuid4(),
        media_asset_id=uuid4(),
        transcript_version=3,
        version=1,
        summary="Một cuộc trò chuyện ngắn.",
        entities=(entity,),
        approved=False,
        parent_version_id=None,
        created_by=None,
        created_at=datetime.now(UTC),
    )

    context.validate()


def test_translation_revision_rejects_empty_text() -> None:
    revision = TranslationRevision(
        id=uuid4(),
        subtitle_segment_id=uuid4(),
        version=1,
        text="   ",
        origin=TranslationRevisionOrigin.USER,
        context_version_id=uuid4(),
        policy_version_id=uuid4(),
        provider=None,
        model=None,
        prompt_version=None,
        editor_id=uuid4(),
        parent_revision_id=None,
        created_at=datetime.now(UTC),
    )

    with pytest.raises(ValidationError) as error:
        revision.validate()
    assert error.value.code == "TRANSLATION_TEXT_EMPTY"


def test_tone_catalog_and_han_detection_are_stable() -> None:
    assert {item.value for item in TonePreset} == {"natural", "funny", "formal", "dramatic"}
    assert contains_han("还有中文")
    assert not contains_han("Hoàn toàn tiếng Việt")
