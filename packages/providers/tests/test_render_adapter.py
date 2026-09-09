from uuid import UUID

from auto_video_sub_application.render_ports import FrozenRenderInput, RenderSpeechTrack
from auto_video_sub_domain import SubtitleAlignment, SubtitleStyleDraft
from auto_video_sub_domain.rendering import OriginalAudioPolicy
from auto_video_sub_providers.render import FFmpegRenderProcessor


def _input(text: str) -> FrozenRenderInput:
    style = SubtitleStyleDraft(
        font_id="system-sans",
        font_family="sans-serif",
        font_license="system",
        font_size_pct=5.0,
        text_color="#FFFFFF",
        outline_color="#000000",
        background_color="#000000",
        background_opacity_pct=0,
        outline_px=2.0,
        shadow_px=1.0,
        alignment=SubtitleAlignment.CENTER,
    )
    return FrozenRenderInput(
        render_id=UUID(int=1),
        project_id=UUID(int=2),
        media_asset_id=UUID(int=3),
        original_artifact_id=UUID(int=4),
        original_object_key="artifacts/project/original/video.mp4",
        original_checksum_sha256="a" * 64,
        duration_us=3_000_000,
        width=1280,
        height=720,
        source_has_audio=True,
        transcript_version=2,
        translation_policy_version_id=UUID(int=5),
        subtitle_style_version_id=UUID(int=6),
        subtitle_style=style,
        speech_tracks=(
            RenderSpeechTrack(
                segment_id=UUID(int=7),
                ordinal=0,
                start_us=500_000,
                end_us=2_000_000,
                text=text,
                translation_revision_id=UUID(int=8),
                speech_attempt_id=UUID(int=9),
                audio_artifact_id=UUID(int=10),
                audio_object_key="artifacts/project/speech.wav",
                audio_checksum_sha256="b" * 64,
            ),
        ),
        audio_policy=OriginalAudioPolicy.REDUCE,
        original_audio_gain_ppm=200_000,
        renderer_version="ffmpeg-libass-system-font-v2",
        font_family="sans-serif",
        input_fingerprint="d" * 64,
    )


def test_ass_writer_neutralizes_user_override_syntax(tmp_path) -> None:
    processor = FFmpegRenderProcessor(
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
        render_timeout_seconds=60,
        validation_timeout_seconds=30,
        duration_tolerance_us=500_000,
    )
    target = tmp_path / "subtitles.ass"
    processor.write_ass(_input(r"xin {\pos(10,10)}chào\\test"), target)

    document = target.read_text(encoding="utf-8")
    dialogue = next(line for line in document.splitlines() if line.startswith("Dialogue:"))
    assert r"{\pos(10,10)}" not in dialogue
    assert chr(0xFF5B) in dialogue
    assert chr(0xFF5D) in dialogue
    assert chr(0xFF3C) in dialogue
    assert "sans-serif" in document
    assert "0:00:00.50,0:00:02.00" in dialogue
