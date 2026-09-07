from dataclasses import replace

import pytest
from auto_video_sub_domain import SubtitleAlignment, SubtitleStyleDraft, ValidationError


def default_style() -> SubtitleStyleDraft:
    return SubtitleStyleDraft(
        font_id="noto-sans",
        font_family="Noto Sans",
        font_license="OFL-1.1",
        font_size_pct=5.0,
        text_color="#FFFFFF",
        outline_color="#000000",
        background_color="#000000",
        background_opacity_pct=0,
        outline_px=2.0,
        shadow_px=1.0,
        alignment=SubtitleAlignment.CENTER,
    )


def test_approved_mvp_style_validates() -> None:
    default_style().validate()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("font_size_pct", 2.99),
        ("font_size_pct", 8.01),
        ("text_color", "white"),
        ("background_opacity_pct", 91),
        ("outline_px", 4.01),
        ("shadow_px", -0.01),
    ],
)
def test_style_rejects_values_outside_mvp_policy(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as error:
        replace(default_style(), **{field: value}).validate()

    assert error.value.code == "SUBTITLE_STYLE_INVALID"
