# Product overview

## Problem and outcome

The product converts Chinese-language videos into reviewable and downloadable Vietnamese-language videos. The MVP is deliberately narrow: it handles ordinary subtitles in a small, predictable band near the bottom of the frame. It does not solve arbitrary scene-text translation, signs, phone screens, perspective-aware replacement, or video inpainting.

The result may combine Vietnamese subtitle overlays, per-segment Vietnamese TTS, and a configurable treatment of the original audio.

## Primary workflow

1. An authenticated user creates a project and uploads directly to object storage with a short-lived signed URL.
2. The backend validates and probes the uploaded media, then generates a low-resolution proxy.
3. Workers sample the configured subtitle band, run Chinese OCR, and consolidate detections into stable timestamped subtitle segments.
4. The user corrects the transcript when needed.
5. The system extracts a global story context: characters, aliases, organizations, places, terms, relationships, ambiguities, evidence segment IDs, and a summary.
6. The user resolves important uncertainties.
7. The user chooses a project-wide translation tone such as natural, funny, formal, or dramatic. A cloud LLM translates semantic batches using that tone's versioned prompt, stable IDs, glossary context, rolling history, overlap, and speech timing budgets. Backend timestamps remain authoritative.
8. Validation and a cross-batch consistency pass surface invalid or inconsistent results for repair or review.
9. TTS runs per segment. Actual audio duration drives trimming, bounded speed-up, and—only when necessary—a concise Vietnamese rewrite by a small local model. Every attempt is retained as an immutable version.
10. The user edits Vietnamese subtitles and a project-wide subtitle style including font family, relative size, weight/italic style, color, outline/border, shadow/background, alignment, and safe-area spacing. The browser previews the proxy plus structured HTML overlays and audio metadata without re-encoding video.
11. An asynchronous FFmpeg render creates and validates the final output for signed download.

## Personas and permissions

The MVP assumes a single owner per project. Owners can upload, edit, approve reviews, start/cancel processing, render, download, and delete. A future collaborator role is possible but is not part of the initial authorization model.

## Success criteria

- A supported video can complete without restarting from the beginning after a transient failure.
- OCR and translation can be corrected without changing stable segment identities or timestamps implicitly.
- Names and important terms remain consistent across semantic batches, or conflicts are surfaced.
- Every translation revision identifies the selected tone and exact prompt version; tone changes never silently reuse text generated under another tone.
- Duration failures are limited to individual segments and produce actionable review tasks.
- Subtitle-style edits update the HTML preview without translation or video encoding; final renders pin the exact style and font assets.
- Users cannot access other users' projects or artifacts.
- Operators can explain stage history, artifact lineage, cost, and failures for a project.

## MVP exclusions

Collaboration, mobile-native apps, live streaming, automatic scene-text replacement, lip synchronization, voice cloning, speaker diarization guarantees, DRM ingestion, public sharing, arbitrary user-authored LLM prompts, arbitrary font uploads, per-segment subtitle styling, and high-availability multi-region deployment are excluded unless approved later.

## Product assumptions

- Supported input limits will be explicit and conservative at launch.
- Chinese subtitles are visually stable enough for region-based OCR.
- Human review gates are acceptable where confidence or consistency is insufficient.
- Main translation uses the only paid runtime service: a cloud LLM. Tests and CI never call it by default.
- OCR, TTS, FFmpeg, local Vietnamese rewriting, workflow orchestration, storage, database, and observability are self-hosted with free/open-source software.
- Initial development and the first deployment run on an owner-operated Apple Silicon machine reachable through Tailscale. Container images should remain multi-architecture where practical.
- Single-host downtime and recovery from local backups are acceptable for the personal MVP; high availability remains out of scope.
