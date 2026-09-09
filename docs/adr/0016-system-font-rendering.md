# ADR 0016: Use system font families for subtitle rendering

- Status: Accepted
- Date: 2026-09-09
- Owners: project maintainers
- Supersedes: the pinned-font-file portion of ADR 0012

## Context

ADR 0012 deliberately pinned subtitle font files so browser preview and final rendering could avoid host-dependent substitution. That trade-off made sense for a distributable multi-host system, but it creates unnecessary setup for the current single-user self-hosted product: the user had to download `NotoSans-Regular.ttf`, mount it into the render worker, calculate a SHA-256 checksum, and keep several render-font environment variables synchronized.

The application already models subtitle appearance as structured data and never needs a user-controlled font path, CSS fragment, ASS fragment, or FFmpeg argument. We can keep that safety boundary without treating a font as a separately provisioned artifact.

## Decision

1. Subtitle style continues to store a structured font selection, but the supported catalog now represents runtime system families: `sans-serif`, `serif`, and `monospace`.
2. The render worker resolves those families through the normal fontconfig/libass stack. It does not accept or mount a user-provided font file.
3. The worker image installs fontconfig plus baseline Noto and Liberation font packages as application dependencies, so a clean Docker build has usable fonts without user setup. Existing `Noto Sans` style versions remain renderable.
4. `render_jobs` records the selected `font_family`. The old `font_filename` field is migrated to `font_family`, and `font_checksum_sha256` is removed.
5. Render manifests record the requested family and `system-fontconfig` as the font-resolution mode. They no longer claim an exact user-provided font-file checksum.
6. The existing security boundary remains: users select a server-defined structured family identifier; raw filesystem paths, URLs, CSS, ASS, and FFmpeg fragments are still rejected by design.
7. Exact pixel identity across different runtime images is no longer promised. Reproducibility is scoped to the same application/runtime image and selected family.

## Consequences

- A normal user never downloads, copies, mounts, or hashes a subtitle font.
- Clean Docker setup is materially simpler.
- Font packages become ordinary worker-image dependencies and are updated through normal image changes.
- Historical render artifacts remain immutable. Existing Noto-based styles continue to work because Noto is bundled in the worker image.
- A future product requirement for arbitrary user fonts would require a separate reviewed design; this ADR does not authorize font uploads or raw font paths.
