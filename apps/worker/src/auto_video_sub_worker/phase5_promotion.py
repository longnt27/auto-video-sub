from __future__ import annotations

import argparse
import asyncio
import json
import math
import platform
import resource
import time
import wave
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path

from auto_video_sub_application.speech_ports import TtsRequest
from auto_video_sub_domain import new_uuid7
from auto_video_sub_providers import VieNeuTtsProvider

FIXTURES = (
    "Xin chào, hôm nay chúng ta sẽ bắt đầu từ những điều đơn giản nhất.",
    "Tiểu Minh nói rằng ngày mai cậu ấy sẽ đến lúc tám giờ ba mươi.",
    "Đừng lo, tôi đã kiểm tra lại địa chỉ và số điện thoại rồi.",
    "Nếu trời mưa, chúng ta sẽ chuyển buổi gặp sang chiều thứ Sáu.",
    "Cô ấy hỏi: Bạn có thật sự muốn tiếp tục không?",
    "Giá của ba món này lần lượt là một trăm, hai trăm và ba trăm nghìn đồng.",
    "Hà Nội, Thành phố Hồ Chí Minh và Đà Nẵng đều có cách phát âm cần rõ ràng.",
    "Tôi không đồng ý với cách làm đó, nhưng chúng ta vẫn có thể tìm một phương án khác.",
)


@dataclass(frozen=True, slots=True)
class SampleResult:
    index: int
    text: str
    file: str
    wall_seconds: float
    audio_seconds: float
    realtime_factor: float
    sample_rate_hz: int
    channels: int


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def _inspect_wav(payload: bytes) -> tuple[int, int, float]:
    with wave.open(BytesIO(payload), "rb") as audio:
        sample_rate = audio.getframerate()
        channels = audio.getnchannels()
        frames = audio.getnframes()
    if sample_rate != 48_000 or channels != 1 or frames <= 0:
        raise RuntimeError(
            f"Unexpected VieNeu WAV shape: rate={sample_rate}, channels={channels}, frames={frames}"
        )
    return sample_rate, channels, frames / sample_rate


def _max_rss_mib() -> float:
    # Linux ru_maxrss is KiB. This harness runs in the Linux arm64 worker image.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


async def run(args: argparse.Namespace) -> int:
    machine = platform.machine().lower()
    if args.require_arm64 and machine not in {"aarch64", "arm64"}:
        raise RuntimeError(f"Phase 5 promotion requires arm64/aarch64; got {machine}")

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    provider = VieNeuTtsProvider(
        model_root=args.model_root,
        model_revision=args.model_revision,
        voice_id=args.voice,
        precision=args.precision,
        threads=args.threads,
    )

    samples: list[SampleResult] = []
    failures: list[dict[str, str | int]] = []
    for index, text in enumerate(FIXTURES, start=1):
        try:
            started = time.perf_counter()
            result = await provider.synthesize(
                TtsRequest(segment_id=new_uuid7(), text=text, voice_id=args.voice)
            )
            wall_seconds = time.perf_counter() - started
            sample_rate, channels, audio_seconds = _inspect_wav(result.wav_bytes)
            filename = f"sample-{index:02d}.wav"
            (output / filename).write_bytes(result.wav_bytes)
            samples.append(
                SampleResult(
                    index=index,
                    text=text,
                    file=filename,
                    wall_seconds=round(wall_seconds, 6),
                    audio_seconds=round(audio_seconds, 6),
                    realtime_factor=round(wall_seconds / audio_seconds, 6),
                    sample_rate_hz=sample_rate,
                    channels=channels,
                )
            )
        except Exception as error:  # promotion evidence must record every failed fixture
            failures.append(
                {
                    "index": index,
                    "text": text,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )

    wall = [item.wall_seconds for item in samples]
    rtf = [item.realtime_factor for item in samples]
    report = {
        "schema_version": "phase5-promotion-v1",
        "machine": machine,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "provider": provider.provider_name,
        "model": provider.model_name,
        "model_revision": provider.model_revision,
        "voice_id": args.voice,
        "precision": args.precision,
        "threads": args.threads,
        "network_expectation": "container must be launched with --network none",
        "fixture_count": len(FIXTURES),
        "success_count": len(samples),
        "failure_count": len(failures),
        "wall_seconds_p50": round(_percentile(wall, 0.50), 6),
        "wall_seconds_p95": round(_percentile(wall, 0.95), 6),
        "realtime_factor_p50": round(_percentile(rtf, 0.50), 6),
        "realtime_factor_p95": round(_percentile(rtf, 0.95), 6),
        "max_rss_mib": round(_max_rss_mib(), 2),
        "samples": [asdict(item) for item in samples],
        "failures": failures,
    }
    (output / "benchmark.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    checklist = [
        "# Phase 5 VieNeu listening review",
        "",
        f"Model revision: `{args.model_revision}`  ",
        f"Voice: `{args.voice}`  ",
        f"Precision: `{args.precision}`",
        "",
        "Promotion requires every generated sample to preserve the written content and be intelligible in Vietnamese. Mark each row only after listening to the WAV.",
        "",
        "| # | WAV | Expected text | Content intact | Pronunciation acceptable |",
        "|---:|---|---|:---:|:---:|",
    ]
    for item in samples:
        escaped = item.text.replace("|", "\\|")
        checklist.append(f"| {item.index} | `{item.file}` | {escaped} | ☐ | ☐ |")
    if failures:
        checklist.extend(["", "## Generation failures", ""])
        checklist.extend(
            f"- Sample {item['index']}: `{item['error_type']}` — {item['error']}"
            for item in failures
        )
    checklist.extend(
        [
            "",
            "## Reviewer decision",
            "",
            "- [ ] All fixture text is preserved without additions or omissions.",
            "- [ ] All pronunciation is acceptable for the MVP preset voice.",
            "- [ ] No sample has corruption, clipping, or unexplained silence.",
            "- [ ] Approve this exact model revision + voice for Phase 5 promotion.",
            "",
            "Reviewer: ____________________",
            "",
            "Date: ____________________",
        ]
    )
    (output / "LISTENING_REVIEW.md").write_text("\n".join(checklist) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if len(samples) == len(FIXTURES) and not failures else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 5 arm64 VieNeu promotion evidence")
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--voice", required=True)
    parser.add_argument("--precision", choices=("fp32", "int8"), default="int8")
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--output", default="/reports")
    parser.add_argument("--require-arm64", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
