# ADR-0006: Isolate providers behind ports and version AI contracts

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

OCR, cloud LLM, local rewrite LLM, TTS, storage, and media integrations vary by accuracy, price, platform, and failure modes. Nevertheless, building a generalized multi-provider framework before evaluating real adapters would be speculative.

## Decision

Define narrow application ports around domain capabilities and build one production adapter per capability first. Proposed evaluations start with RapidOCR/ONNX Runtime, an approved paid translation LLM with structured outputs, llama.cpp, VieNeu-TTS v3 Turbo through local ONNX, Garage S3, and FFmpeg. Compare PaddleOCR for accuracy while treating its Apple Silicon runtime build as a deployment cost. Normalize errors and usage. Version schemas, prompts, models, voices, and policies; retain redacted request/response artifacts where permitted. Use shared adapter contract tests. ADR-0010 records the TTS-specific choice and promotion gate.

## Consequences

SDK payloads remain outside the domain, fakes are deterministic, and a provider can be replaced with bounded application change. Only translation incurs provider usage cost. Behavior is not perfectly portable—prompts, voices, and model quality remain sticky—and every local model/voice license and architecture must be recorded.

## Alternatives considered

- Call SDKs directly from workflows/domain: faster for a spike but spreads vendor types and failure behavior.
- Implement multiple adapters immediately: proves portability but doubles work before quality/cost evidence.
- Cloud OCR/TTS/local rewrite: may improve quality but violates the paid-translation-only constraint.
- Self-host main translation: removes provider spend but does not meet the expected quality/hardware envelope for long contextual Chinese-to-Vietnamese translation.

## Reversibility and review triggers

Easy to replace adapters, medium to change behavior/versioning policy. Reassess providers using approved evaluation sets, costs, data terms, and reliability.
