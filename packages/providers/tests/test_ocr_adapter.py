from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from auto_video_sub_application.ports import OcrProviderError
from auto_video_sub_providers import RapidOcrProvider


class FakeEngine:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[str] = []

    def __call__(self, path: str) -> object:
        self.calls.append(path)
        return self.result


@pytest.mark.asyncio
async def test_rapidocr_adapter_normalizes_lines_and_confidence(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"fixture")
    engine = FakeEngine(SimpleNamespace(txts=["  你好  ", "", "世界"], scores=[0.9, 0.4, 0.7]))

    result = await RapidOcrProvider(engine=engine).recognize(image)

    assert result.text == "你好\n世界"
    assert result.confidence == pytest.approx(0.8)
    assert result.provider == "rapidocr"
    assert result.model_version == "rapidocr-3.9.2-pp-ocrv6-small-default"
    assert engine.calls == [str(image)]


@pytest.mark.asyncio
async def test_rapidocr_adapter_accepts_no_detection(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"fixture")
    result = await RapidOcrProvider(
        engine=FakeEngine(SimpleNamespace(txts=None, scores=None))
    ).recognize(image)

    assert result.text == ""
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_rapidocr_adapter_rejects_inconsistent_output(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"fixture")
    provider = RapidOcrProvider(
        engine=FakeEngine(SimpleNamespace(txts=["你好", "世界"], scores=[0.9]))
    )

    with pytest.raises(OcrProviderError) as caught:
        await provider.recognize(image)

    assert caught.value.code == "OCR_OUTPUT_INVALID"
    assert caught.value.retryable is False


@pytest.mark.asyncio
async def test_rapidocr_adapter_maps_engine_failure_to_retryable_error(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"fixture")

    def explode(path: str) -> object:
        del path
        raise RuntimeError("provider detail")

    with pytest.raises(OcrProviderError) as caught:
        await RapidOcrProvider(engine=explode).recognize(image)

    assert caught.value.code == "OCR_INFERENCE_FAILED"
    assert caught.value.retryable is True
    assert "provider detail" not in str(caught.value)
