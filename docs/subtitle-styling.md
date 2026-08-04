# Subtitle styling and preview parity

## Goal and scope

The owner can choose one subtitle style for the project and see it immediately over the proxy without encoding video. The final render uses the same structured style and pinned font assets. Per-segment styling, animation, karaoke effects, arbitrary positioning, user-uploaded fonts, raw CSS/ASS, and general graphics composition are outside the MVP.

## Style contract

Every persisted style save creates or reuses an immutable `SubtitleStyleVersion`; a project pointer selects the current version. Slider/color interactions update local preview immediately and are debounced or explicitly committed, so dragging a control does not create an unbounded revision stream. The API accepts only typed, bounded fields:

| Field | MVP behavior |
|---|---|
| `font_asset_id` | ID from the approved font catalog, never a host family name or path |
| `font_size_per_mille` | Fixed-point size relative to active video height so proxy and output resolutions scale consistently |
| `font_weight` | Only weights present in the selected font asset, initially normal or bold |
| `italic` | Boolean, only when the selected font provides or permits an italic face |
| `text_color` | Canonical RGBA value |
| `outline_color`, `outline_width_per_mille` | Subtitle border/outline with bounded relative width |
| `shadow` | Bounded enabled flag, relative offset/blur, and RGBA color |
| `background` | Optional bounded box opacity/color and padding |
| `line_spacing_per_mille` | Bounded relative spacing for two-line subtitles |
| `horizontal_alignment` | Initially left, center, or right within the subtitle safe area |
| `max_width_per_mille` | Maximum line-box width relative to active video width |
| `bottom_margin_per_mille` | Distance from the active video bottom safe area |

The server canonicalizes colors, fixed-point values, and enums before hashing/versioning. Numerical limits are configuration with versioned defaults, not browser-only validation. Subtitle timing and text remain separate backend-owned records; style changes cannot alter either.

## Font catalog

The MVP ships a small, reviewed catalog rather than reading fonts installed on the host. Each font asset records family/face identifiers, supported Vietnamese glyph coverage, weight/style, source version, license/provenance, checksum, browser artifact, renderer artifact, and fallback policy. Browser and renderer files must derive from the same pinned font release.

Missing font files or glyph coverage are render-validation failures, not permission to silently substitute a host font. Arbitrary font upload and remote font URLs remain out of scope because they add licensing, malware/parser, storage, and preview-parity risks.

## Preview and final render

The browser loads the pinned webfont and maps the structured style to an HTML overlay synchronized to the proxy video. It must not accept raw CSS from the API or user. Local UI updates are immediate; persistence uses optimistic concurrency so two tabs cannot silently overwrite each other's selected style.

The backend escapes subtitle text and generates an ASS document from the same style version, then renders it with version-pinned FFmpeg/libass and explicitly mounted font artifacts. Users never supply ASS override tags or FFmpeg filter arguments. The render manifest pins the style version, font checksums, generated ASS artifact, video geometry, and renderer versions.

HTML and libass use different layout engines, so pixel identity is not promised. The target is bounded visual parity for font face, relative size, colors, border, line breaks, alignment, and safe-area placement. The editor identifies preview as approximate if a known renderer difference exceeds tolerance; the backend output remains authoritative.

## Versioning and invalidation

- Creating or selecting a style version updates only structured editor state.
- No translation, TTS, OCR, proxy generation, or paid provider call is triggered.
- Existing final outputs remain immutable and continue to reference their old style.
- A newly requested render freezes the selected style and creates a new render manifest/output.
- Re-selecting an identical canonical style resolves to the same input fingerprint and does not create duplicate render work.
- Font catalog upgrades create new font asset IDs; they never mutate files used by historical manifests.

## Validation and security

Validate ownership, optimistic version, field types, numeric ranges, color syntax, font catalog membership, supported weight/style combinations, safe-area bounds, and maximum rendered lines. Escape braces, backslashes, newlines, and other ASS-sensitive characters as text. Never concatenate user text into shell commands, CSS declarations, ASS headers/overrides, font paths, or filter expressions.

Preview and render endpoints enforce the same project authorization as subtitle text and artifacts. Font files are read-only release assets, not public uploads. Font license notices accompany distribution where required.

## Testing and acceptance

- Unit/property tests cover canonicalization, bounds, stable fingerprints, invalid combinations, and render-only invalidation.
- Security tests cover CSS/ASS/filter injection strings, path traversal, remote URLs, oversized values, malformed colors, and cross-project style IDs.
- Browser tests cover immediate control updates, refresh persistence, optimistic conflicts, responsive proxy sizing, and no encode/provider call after style edits.
- Golden media tests cover Vietnamese diacritics, numbers, punctuation, one/two lines, long wrapping, every approved weight/style, border widths, colors, shadow/background, alignment, and common aspect ratios.
- Preview-versus-render image comparisons use declared geometry/color tolerances and human visual review before a font or renderer upgrade.
- Final-output validation confirms the manifest's font/style checksums and checks for missing glyphs, clipped text, unsafe placement, and unexpected font substitution.
