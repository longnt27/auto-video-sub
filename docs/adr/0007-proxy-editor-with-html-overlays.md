# ADR-0007: Use a proxy-video editor with HTML overlays

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

Users need responsive transcript, translation, and audio editing. Re-encoding on every edit is slow and expensive. The MVP only overlays ordinary subtitles and previews per-segment audio; advanced compositing is out of scope.

## Decision

Generate a lower-resolution proxy once. Synchronize structured timeline state to the browser video element and render initial subtitle overlays from validated structured style state as HTML/CSS. Use only pinned webfonts from the approved catalog. Preview selected audio segments through browser audio scheduling. Final media remains an asynchronous backend FFmpeg/libass render from a frozen manifest that pins the same style and font release. ADR-0012 defines the style boundary.

## Consequences

Editing is responsive and style changes require no encode. Browser HTML and libass can differ slightly in wrapping and metrics, so declared parity tolerances, pinned font files, missing-glyph validation, and golden comparisons are required. HTML overlays are not intended for arbitrary scene graphics, and raw CSS/ASS is never user input.

## Alternatives considered

- Encode preview after each edit: authoritative but unusably slow/costly.
- Canvas/WebGL from the start: greater compositing control but needless complexity for the subtitle-only MVP.
- Server-streamed compositing: operationally heavy and latency-sensitive.

## Reversibility and review triggers

Easy/medium. Introduce Canvas/WebGL only when measured preview accuracy or overlay requirements cannot be met with HTML; keep structured timeline and render manifest contracts stable.
