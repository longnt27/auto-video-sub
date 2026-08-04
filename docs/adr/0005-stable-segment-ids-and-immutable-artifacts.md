# ADR-0005: Use stable segment IDs and immutable versioned outputs

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

AI providers can omit, duplicate, reorder, or invent output fields. Users edit transcripts/translations, duration repair creates variants, and retries must reuse or supersede outputs without losing history. Final renders need exact lineage.

## Decision

Assign backend-generated UUIDv7 IDs to subtitle segments and retain them across text revisions. Keep timing and metadata backend-owned. Store transcript, context, translation policies/tone prompts, translation, subtitle styles/font assets, TTS, render manifests, and artifacts as immutable versions with explicit current/approved pointers and lineage. Use integer microsecond media times.

## Consequences

Responses can be validated by ID; partial retries, audit, rollback, and reproducible render inputs become practical. Storage and schema are more verbose, garbage collection requires retention policy, and merge/split edits need explicit identity rules rather than overwrites.

## Alternatives considered

- Use line number/index as identity: breaks on edits, overlap, batching, and reordering.
- Let LLM return timestamps/full records: risks corrupting backend authority.
- Update artifacts/revisions in place: reduces storage but destroys provenance and retry safety.

## Reversibility and review triggers

Difficult and foundational. Review explicit merge/split identity semantics during transcript-editor design, but preserve stable IDs and immutable history.
