# ADR-0012: Use structured subtitle styles with pinned font assets

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

Users need to change subtitle font family, relative size, weight/italic style, colors, border/outline, and related placement effects in the browser without re-encoding video. The final FFmpeg output must reproduce the selected appearance closely enough to be trustworthy. Host fonts, arbitrary CSS/ASS, and unversioned render settings would make output non-reproducible and create injection, path, licensing, and cross-platform risks.

## Decision

Represent subtitle appearance as immutable, project-wide `SubtitleStyleVersion` records containing validated typed fields and an approved `font_asset_id`. Store dimensions in fixed-point units relative to active video geometry and colors in canonical RGBA. The MVP supports bounded font size, available weight/italic face, text color, border/outline, shadow/background, line spacing, alignment, maximum width, and bottom safe-area margin.

Ship a small license-reviewed font catalog. Browser webfonts and renderer fonts derive from the same pinned release and have checksums/provenance. Render final subtitles by escaping text into a backend-generated ASS artifact and using version-pinned FFmpeg/libass with explicit font assets. Never accept raw CSS, HTML, ASS override tags, FFmpeg/filter fragments, remote font URLs, or font paths from users.

Style changes update HTML overlay state immediately and invalidate only future render manifests/outputs. Translation, TTS, OCR, proxy generation, and paid providers are unaffected. Historical outputs keep their pinned style and font assets.

## Consequences

The editor remains responsive and renders are reproducible across hosts. A curated catalog limits font choice but avoids silent substitution and licensing ambiguity. HTML and libass have different layout engines, so exact pixel identity is not promised; golden comparisons and declared tolerances are required for line wrapping, metrics, borders, colors, and safe-area placement.

## Alternatives considered

- Use host-installed font family names: convenient but non-reproducible across macOS/Linux/containers and prone to silent fallback.
- Allow font uploads: flexible but adds parser/malware, storage, licensing, provenance, glyph-coverage, and lifecycle work outside MVP scope.
- Store raw CSS or ASS: expressive but unsafe, renderer-specific, hard to validate, and incompatible with a stable API contract.
- Canvas/WebGL editor: could improve visual control, but HTML overlays meet current subtitle-only needs.
- Re-encode after every style edit: authoritative but too slow for interactive editing.

## Reversibility and review triggers

Easy/medium. New structured fields and fonts can be added compatibly; changing units or canonicalization is a persistent-data contract change. Introduce per-segment styles, font upload, Canvas/WebGL, or a renderer other than libass only after a concrete requirement and new ADR.
