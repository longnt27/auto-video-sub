# ADR-0010: Use VieNeu-TTS for local Vietnamese synthesis

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

Vietnamese TTS must run locally on Apple Silicon without per-character charges and must sound natural enough for dubbed video. The owner evaluated Piper and rejected its output quality. The replacement must work behind the existing TTS port, preserve segment-level retries and immutable attempts, and not expand the MVP into voice cloning.

The current VieNeu-TTS project is Vietnamese-specific, labels its code and v3 Turbo model Apache-2.0, provides built-in regional preset voices, and documents a torch-free ONNX CPU path as the preferred Apple Silicon route. The v3 Turbo line produces 48 kHz audio but is currently labelled early access, so repository claims alone are not sufficient production evidence.

## Decision

Use VieNeu-TTS v3 Turbo through its ONNX CPU path as the proposed local TTS adapter. Use exactly one reviewed built-in preset voice for the first vertical slice. Pin the code revision, model revision, model and asset checksums, backend, precision, voice identifier, normalization settings, and sampling settings in every attempt.

Do not enable voice cloning, accept reference audio, or let project data choose model paths. Promote the adapter only after it passes the approved Vietnamese listening/content-integrity corpus and an arm64 Colima-container capacity test. If the early-access v3 line fails stability or compatibility, evaluate the stable VieNeu v2 CPU path through the same port without changing domain or workflow contracts.

## Consequences

The system gains a Vietnamese-focused, offline TTS candidate with no runtime fee and a practical CPU path. ONNX also aligns with the first OCR runtime, although each adapter retains its own pinned dependency boundary. The local-AI worker needs materially more model storage, memory, startup time, and supply-chain review than Piper.

Naturalness, pronunciation, duration, and content fidelity remain empirical. Generative TTS can repeat, omit, or hallucinate speech, and the current model is early access. Every output still receives format/duration validation, suspicious failures become scoped review, and releases require human listening evidence. Apache-2.0 metadata does not remove the need to review upstream components, training-data disclosures, and preset-voice provenance for the intended use.

## Alternatives considered

- Piper: small and operationally simple, but rejected after the owner's listening test.
- VieNeu v2 CPU: fully local and a suitable fallback, but uses the older 24 kHz architecture and is not the preferred quality target.
- Chatterbox Multilingual v3: MIT and MPS-capable, but its publisher reports Vietnamese is not production quality and recommends against commercial deployment for Vietnamese.
- Vietnamese F5-TTS checkpoints: potentially strong output, but the reviewed prominent checkpoints use non-commercial Creative Commons licenses and rely on reference audio.
- Qwen3-TTS: capable and Apache-2.0, but its official language list does not include Vietnamese.
- macOS system voices: useful as a host-only benchmark, but do not provide the intended portable, containerized Linux arm64/amd64 path.
- Cloud TTS: may provide better quality and operations, but would break the paid-translation-only cost boundary.

## Reversibility and review triggers

Easy at the adapter boundary and medium for audible behavior because changing a model/voice changes every generated segment. Reconsider when v3 leaves early access, a materially better permissively licensed Vietnamese model appears, container performance misses the agreed throughput, quality regression exceeds thresholds, licensing/provenance changes, or paid TTS receives explicit approval.

## Evidence to review at approval

- [VieNeu-TTS repository and Apple Silicon/ONNX guidance](https://github.com/pnnbao97/VieNeu-TTS)
- [VieNeu-TTS v3 Turbo model card and files](https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo)
- [Chatterbox v3 documented Vietnamese limitation](https://www.resemble.ai/resources/chatterbox-multilingual-v3-tts-with-embedded-watermarking-for-25-languages)
- [F5-TTS Vietnamese ViVoice model license](https://huggingface.co/hynt/F5-TTS-Vietnamese-ViVoice)
- [Qwen3-TTS official supported-language list](https://github.com/QwenLM/Qwen3-TTS)
