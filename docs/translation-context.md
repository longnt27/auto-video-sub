# Translation context and validation

## Goals

Translation must sound like spoken Vietnamese in the user's selected tone while keeping names, relationships, facts, and important terms coherent across a long story. Context is versioned data with evidence, not an ever-growing prompt string.

## Translation tone presets

The MVP provides a small server-owned catalog with stable preset IDs and separate, versioned prompt templates:

| Preset | Intended behavior | Guardrail |
|---|---|---|
| `natural` | Contemporary, conversational Vietnamese suitable for general dialogue | Default; avoid unnecessary slang or stiffness |
| `funny` | Playful phrasing, comic timing, and idioms where the source supports them | Never invent jokes, events, relationships, insults, or facts |
| `formal` | Polished, respectful register and restrained word choice | Preserve story-appropriate intimacy, hierarchy, and forms of address |
| `dramatic` | More emotionally vivid spoken delivery | Do not exaggerate plot facts or add emotional claims absent from context |

Tone is a project-wide translation policy, chosen before translation. A preset resolves to an immutable policy version containing an exact prompt checksum/version and shared fidelity constraints. Users select preset IDs; they cannot view-edit system instructions or provide arbitrary prompts in the MVP. Global context extraction remains tone-neutral so it can be reused when tone changes.

Tone guides phrasing, register, humor, and rhythm. It never relaxes glossary choices, segment-ID completeness, backend-owned timing, meaning preservation, output schemas, safety rules, or review requirements. User-edited translations keep their explicit user provenance and are not automatically rewritten merely to match a tone.

## Global context

For an approved transcript version, extract an immutable context version containing:

- characters, aliases, organizations, places, and important terminology;
- original Chinese forms and preferred Vietnamese renderings;
- relationships and role descriptions;
- confidence and ambiguity classifications;
- evidence subtitle segment IDs;
- a global story summary;
- unresolved questions requiring human review.

Extraction output is schema-validated. High-impact ambiguity and low-confidence names become review tasks. Approval creates a new context version with a human-authored provenance trail.

## Semantic batching

Plan batches by scene/topic boundaries when detectable, targeting roughly 3–7 minutes and enforcing provider token limits. Each batch distinguishes:

- **owned segments:** the only IDs the model must translate and the only outputs that can be persisted;
- **prefix/suffix overlap:** read-only neighboring segments for continuity;
- **global context subset:** all mandatory glossary entries plus characters/entities relevant by evidence or retrieval;
- **rolling summary:** bounded summary of preceding approved events, versioned and updated outside the model's translation response;
- **timing budget:** available microseconds and configurable speech-density hints per owned segment.
- **translation policy:** selected tone ID, exact tone prompt version, and shared fidelity constraints.

Each tone has its own batch prompt template composed with shared non-overridable contract instructions. Prompts instruct the model to preserve one output object per owned ID, produce Vietnamese text only in the translation field, keep content faithful, and never return or modify timestamps.

## Provider boundary

The provider receives a request envelope with schema version, batch ID, stable segment IDs, source text, context, timing hints, translation-policy version, tone preset ID, provider/model ID, and prompt version. Raw request/response envelopes are redacted where necessary and retained as access-controlled artifacts according to policy.

The backend joins results to segments by ID. Array position is never authoritative. Unknown fields and metadata from the provider are ignored or rejected according to schema; timing remains from backend records.

## Validation pipeline

Validate before accepting a batch:

1. Parse against a strict versioned schema and detect truncation.
2. Require exactly one result for each owned ID.
3. Reject missing, duplicate, unknown, overlap-only, or empty IDs/results.
4. Flag residual Han characters using allowlists for intentional names/terms; do not assume every character is wrong.
5. Check length extremes, placeholders, refusal/meta text, and obvious source omission.
6. Compare entity renderings against the approved glossary.
7. Apply tone-specific regression checks for obvious violations, while treating subjective tone quality as a human/evaluation concern rather than a deterministic validator claim.
8. Persist valid per-segment outputs and findings independently so a bad result does not erase good prior versions.

Invalid structure may receive a bounded same-provider repair request that includes validation errors but never silently invents missing translations. Exhaustion creates a scoped review task.

## Consistency pass

After batch validation, build an index of source entity/term mentions to proposed Vietnamese forms. Detect conflicts with the glossary and cross-batch variants, then classify:

- safe deterministic normalization;
- model-assisted proposed correction requiring validation;
- ambiguous conflict requiring human choice.

Corrections create new translation revisions; they do not edit accepted history. Changing the glossary marks affected segments/batches stale through evidence and mention indexes.

## Prompt and model lifecycle

Treat tone preset definitions, prompt templates, schema versions, model identifiers, sampling settings, and context-selection rules as versioned inputs. Record token counts, latency, estimated price snapshot, finish reason, and provider request ID. Each tone prompt change creates a new prompt/policy version and requires tone-specific fixtures and regression evaluation before rollout. A model alias alone is insufficient for reproducibility; store the resolved identifier when the provider supplies it.

Changing tone after translation is an explicit paid operation. The API shows that translation and downstream TTS/render outputs will be superseded, reserves budget, and starts new translation executions only after confirmation. Existing batch boundaries and tone-neutral context may be reused, but old translated text is never relabelled as if generated under the new tone. Pending old-policy work is cancelled where safe; a provider response that arrives late is retained for audit but cannot become current.

The paid translation-LLM budget covers only this translation capability: global context/entity extraction, semantic batch translation, and an optional LLM-assisted consistency proposal. These calls run in the isolated translation worker profile. Structural validation remains deterministic and local. OCR, TTS, duration rewriting, media processing, storage, and observability do not use the paid provider.

## Privacy and safety

Send only required subtitle/context data. Do not send object-store URLs or unrelated account data. Delimit user-authored transcript/context fields as data and never interpolate them into the system-instruction channel. Document provider retention settings and regional processing. Redact secrets and authorization headers from stored envelopes and logs. Human review is mandatory where entity choices could materially change identity or meaning and confidence is inadequate.
