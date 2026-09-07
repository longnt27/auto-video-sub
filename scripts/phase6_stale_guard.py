from pathlib import Path

path = Path("packages/infrastructure/src/auto_video_sub_infrastructure/render_repository.py")
text = path.read_text(encoding="utf-8")

old_import = '''from auto_video_sub_infrastructure.translation_models import (
    TranslationRevisionModel,
    TranslationStateModel,
)
'''
new_import = '''from auto_video_sub_infrastructure.translation_models import (
    SegmentTranslationHeadModel,
    TranslationRevisionModel,
    TranslationStateModel,
)
'''
if old_import not in text:
    raise SystemExit("translation model import anchor not found")
text = text.replace(old_import, new_import, 1)

old_guard = '''                revision = await session.get(
                    TranslationRevisionModel, segment_state.translation_revision_id
                )
                if revision is None or revision.id != attempt.translation_revision_id:
                    raise ConflictError("Speech is stale for the current Vietnamese translation")
'''
new_guard = '''                current_translation = await session.get(
                    SegmentTranslationHeadModel, segment.id
                )
                if (
                    current_translation is None
                    or current_translation.translation_revision_id
                    != segment_state.translation_revision_id
                ):
                    raise ConflictError("Speech is stale for the current Vietnamese translation")
                revision = await session.get(
                    TranslationRevisionModel, segment_state.translation_revision_id
                )
                if revision is None or revision.id != attempt.translation_revision_id:
                    raise ConflictError("Speech is stale for the current Vietnamese translation")
'''
if old_guard not in text:
    raise SystemExit("speech revision guard anchor not found")
text = text.replace(old_guard, new_guard, 1)
path.write_text(text, encoding="utf-8")
