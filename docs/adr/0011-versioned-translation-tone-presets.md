# ADR-0011: Use versioned project-wide translation tone presets

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

Users want to choose how Vietnamese dialogue sounds—for example funny or formal—while the system must preserve facts, entities, segment IDs, timing, and story-wide consistency. Tone affects paid LLM behavior and downstream TTS, so silently changing a prompt or relabelling existing text would break cost predictability and lineage. Exposing arbitrary system prompts would also weaken validation and prompt-injection boundaries.

## Decision

Provide a small server-owned catalog with stable IDs and separate versioned batch prompts: `natural` (default), `funny`, `formal`, and `dramatic`. The user selects one tone for the project. That selection creates an immutable `TranslationPolicyVersion` pinning the preset ID, exact prompt version/checksum, shared fidelity rules, provider/model settings, and provenance.

Global context extraction remains tone-neutral. Every translation batch, consistency operation, translation revision, and duration rewrite references the selected policy. Tone may change phrasing, register, rhythm, and source-supported humor or emotion; it never authorizes invented facts, jokes, relationships, names, timestamps, IDs, or output fields.

A tone change after translation requires explicit confirmation of paid scope and quota reservation. It starts new translation executions and invalidates downstream TTS/duration/render outputs while reusing compatible upload/media/OCR/transcript/context and batch boundaries. Old results remain immutable, and late responses under the superseded policy cannot become current.

Arbitrary prompt text, user-editable system instructions, and per-segment tone are outside the MVP.

## Consequences

Users get predictable creative control with auditable prompt/model lineage. Tone-specific prompt fixtures and human Vietnamese evaluation increase maintenance. Changing tone can incur nearly the full translation cost again, and subjective quality cannot be proven by schema validation alone. The local duration rewriter must preserve the selected tone without amplifying humor or drama.

## Alternatives considered

- One universal prompt with a tone string interpolated into it: simpler, but tones do not have independently reviewable instructions or regression history.
- Arbitrary user prompts: more flexible, but undermines security, supportability, evaluation, and consistent structured output.
- Per-segment tone: expressive, but creates inconsistent scenes, much more editor state, partial-cost ambiguity, and prompt fragmentation.
- Post-process an existing translation into another tone: may be cheaper in some cases, but compounds meaning drift and still consumes LLM budget; not an MVP shortcut.
- Tone-neutral translation only: cheapest and simplest, but does not meet the requested product behavior.

## Reversibility and review triggers

Easy to add, hide, or deprecate presets; medium to change a promoted prompt because audible/text behavior changes. Reconsider per-scene tone only after project-wide presets have measured demand and a clear inheritance/editor model. Reconsider custom prompts only with a reviewed safety, support, evaluation, and billing design.
