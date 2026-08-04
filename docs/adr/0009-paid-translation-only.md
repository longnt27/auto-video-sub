# ADR-0009: Make translation the only paid runtime provider

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

High-quality, story-aware Chinese-to-Vietnamese translation benefits from a capable cloud LLM, while OCR, narrow Vietnamese rewriting, TTS, media processing, workflow orchestration, persistence, and telemetry can run on the owner's hardware. The project must keep recurring costs near zero and predictable.

## Decision

Allow paid runtime usage only for the main translation capability: global context/entity extraction, semantic translation batches, and optional LLM-assisted consistency proposals. Run RapidOCR/ONNX Runtime, deterministic validation, VieNeu-TTS, llama.cpp duration rewriting, FFmpeg, PostgreSQL, Temporal, Garage, and observability locally. Give only the dedicated translation worker profile the provider credential and necessary egress. Record tokens and estimated cost per stage, reserve a per-project budget, and require explicit opt-in for real-provider smoke tests.

Pin and review licenses/model cards for OCR models, VieNeu-TTS code/model/preset assets, and GGUF models. Free of monetary charge does not imply unrestricted redistribution or commercial use.

## Consequences

Variable spend is concentrated in the capability with the largest expected quality benefit. Local TTS may sound worse than paid voices, local inference consumes RAM/CPU, and the owner maintains models and runtimes. The translation API remains an external availability/privacy dependency and needs hard quotas, timeouts, retry bounds, and redacted artifacts.

## Alternatives considered

- Paid cloud OCR/TTS/observability: potentially better quality or lower maintenance, but introduces multiple unpredictable bills.
- Fully local translation: no API cost but likely misses quality/context goals on available hardware.
- Free-tier cloud services: pricing and quotas can change and are not an acceptable architectural guarantee.

## Reversibility and review triggers

Easy/medium because providers are behind ports. Reconsider a paid non-translation provider only with explicit human approval, measured local quality failure, a cost ceiling, updated threat/data analysis, and an ADR. Re-evaluate local main translation when hardware/model quality demonstrably meets the evaluation set.
