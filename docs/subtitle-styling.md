# Subtitle styling and preview parity

## Goal and scope

The owner can choose one subtitle style for a video and preview it immediately over the proxy without encoding video. The final render consumes the same immutable structured style version. Per-segment styling, animation, karaoke effects, arbitrary positioning, user-uploaded fonts, raw CSS/ASS, and general graphics composition remain outside the MVP.

## Style contract

Every persisted save creates an immutable `SubtitleStyleVersion`. The API accepts only typed, bounded fields:

| Field | MVP behavior |
|---|---|
| `font_id` | Server-defined system-font alias; never a filesystem path or URL |
| `font_family` | Canonical runtime family resolved by browser CSS / renderer fontconfig |
| `font_size_pct` | 3–8% of video height |
| `text_color` | Canonical RGB hex |
| `outline_color` | Canonical RGB hex |
| `background_color` | Canonical RGB hex |
| `background_opacity_pct` | 0–90% |
| `outline_px` | 0–4 px |
| `shadow_px` | 0–4 px |
| `alignment` | Center only in the current MVP |

Subtitle timing and text remain separate backend-owned records; style changes cannot alter either and never trigger OCR, translation, TTS, or rendering by themselves.

## System font families

The normal user does not install or provision a render font. The supported style catalog represents runtime system families rather than font files. The current choices are:

- `sans-serif`
- `serif`
- `monospace`

The render worker image installs fontconfig plus baseline Noto and Liberation font packages as ordinary application dependencies. Existing style versions that reference `Noto Sans` remain renderable.

No API accepts a user-controlled font path, font URL, CSS declaration, ASS fragment, or FFmpeg argument. Arbitrary font uploads remain out of scope.

## Preview and final render

The browser maps the structured style to an HTML overlay synchronized to the proxy video. Browser CSS resolves the selected family through its normal font stack.

The backend escapes subtitle text, generates an ASS document from the same style version, and renders it with FFmpeg/libass. libass resolves the selected family through the worker's fontconfig database. There is no dedicated `.ttf` mount and no user-managed font checksum.

The render manifest pins the style version, requested `font_family`, `system-fontconfig` resolution mode, video geometry, speech inputs, and renderer version. Exact pixel identity across different operating systems or container-image versions is not promised; the rendered output is authoritative.

## Versioning and invalidation

- Creating or selecting a style version updates only structured editor state.
- No translation, TTS, OCR, proxy generation, or paid provider call is triggered.
- Existing final outputs remain immutable and keep their old style lineage.
- A newly requested render freezes the selected style into a new render manifest/output.
- Re-selecting identical canonical inputs resolves to the same render fingerprint and avoids duplicate work.

## Validation and security

Validate ownership, optimistic version, field types, numeric ranges, color syntax, and membership in the server-defined system-font catalog. Escape braces, backslashes, newlines, and other ASS-sensitive characters as text. Never concatenate user text into shell commands, CSS declarations, ASS headers/overrides, font paths, or filter expressions.

The font-selection change in ADR 0016 supersedes the pinned-font-file portion of ADR 0012. The structured-style and injection-safety decisions from ADR 0012 remain in force.

## Testing and acceptance

- Unit tests cover style bounds, system-font catalog selection, and render input validation.
- Security tests cover ASS override syntax and other user-text injection strings.
- Browser tests cover immediate style preview, persistence, and no encode/provider call after style edits.
- Render tests cover Vietnamese text, system family resolution, subtitle geometry, and output validation.
- A clean Docker build must render without any manually supplied font file or checksum.
