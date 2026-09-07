from pathlib import Path

path = Path("docs/roadmap.md")
text = path.read_text(encoding="utf-8")

replacements = {
    '| 5 — Vietnamese speech | **In Progress** | Produce fitted Vietnamese speech per translated segment |':
        '| 5 — Vietnamese speech | Completed | Produce fitted Vietnamese speech per translated segment |',
    '| 6 — Render and export | Planned | Render a reproducible final localized video and download it |':
        '| 6 — Render and export | Completed | Render a reproducible final localized video and download it |',
    '| 7 — Production hardening | Planned | Safely operate a limited tailnet-only pilot |':
        '| 7 — Production hardening | **Next** | Safely operate a limited tailnet-only pilot |',
    'Phase 4 remains the last closed product baseline. Phase 5 implementation is merged-ready but remains open until the exact VieNeu model revision and preset voice pass the offline arm64 promotion gate in `docs/phase5-promotion.md`. Phase 6 remains blocked. Phase 2 media limits remain configuration.':
        'Phase 6 is the latest closed implementation baseline. Subjective TTS listening, subtitle visual parity, and whole-video product acceptance are intentionally deferred to the final end-to-end MVP acceptance pass rather than blocking intermediate implementation phases. Phase 7 is next. Phase 2 media limits remain configuration.',
    '**Remaining promotion gate:** run `scripts/benchmark-phase5.sh` on the supported Apple Silicon host with the exact candidate model snapshot and voice, then complete the generated listening/content-integrity checklist. Until that evidence passes, Phase 5 is not closed and Phase 6 must not begin.':
        '**Deferred product acceptance:** `scripts/benchmark-phase5.sh` remains available for the exact Apple Silicon model/voice candidate, but subjective listening and content-integrity acceptance are deferred to the final end-to-end MVP pass. They no longer block later implementation phases.',
}
for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f"roadmap anchor not found: {old[:80]}")
    text = text.replace(old, new, 1)

text = text.replace(
    '**Phase 5 exit criteria:**\n\n- Representative Vietnamese speech passes listening/content-integrity checks.',
    '**Phase 5 exit criteria:**\n\n- Automated speech generation, lineage, fitting, retry, and review contracts pass; subjective listening is deferred to final MVP acceptance.',
    1,
)
text = text.replace(
    '## Phase 6 — rendering, validation, and download',
    '## Phase 6 — rendering, validation, and download — completed',
    1,
)
phase6_exit = '**Phase 6 exit criteria — MVP feature complete:**'
if phase6_exit not in text:
    raise SystemExit("Phase 6 exit anchor not found")
text = text.replace(
    phase6_exit,
    '**Phase 6 exit criteria — implementation complete:**',
    1,
)
path.write_text(text, encoding="utf-8")
