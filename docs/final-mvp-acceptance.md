# Final MVP acceptance pass

This is the deferred manual acceptance pass for the completed implementation phases. It does not replace automated CI gates; run it on the supported Apple Silicon deployment candidate after Phase 7 hardening is ready.

## Candidate freeze

Record before testing:

- application image digests and Git commit;
- exact VieNeu model revision and preset voice;
- exact Noto Sans renderer font file and SHA-256;
- FFmpeg/libass version;
- local rewrite model revision when enabled;
- translation provider/model/prompt policy and explicit test budget;
- database migration head and deployment configuration snapshot.

Do not change any pinned input during the pass. A changed model, font, renderer, prompt policy, or application build starts a new candidate.

## One representative full-video pass

Use a legally usable Chinese-subtitled video representative of the intended MVP input. Complete the product through the normal UI:

1. create a project and upload the video;
2. verify validation, proxy generation, and playback;
3. run subtitle extraction/OCR and correct the source transcript where necessary;
4. review context/glossary and produce Vietnamese translation under one approved tone;
5. correct Vietnamese text where necessary and confirm subtitle-style preview;
6. generate fitted Vietnamese speech and resolve only segments that need review;
7. choose the desired original-audio policy and request a final render;
8. wait for backend validation, then download the validated output.

The pass fails if the workflow requires database edits, direct object-store edits, manual Temporal intervention, or bypassing an application review/validation gate.

## Manual quality checks

Review the final output once, end to end:

- Chinese subtitle meaning is represented correctly in Vietnamese after intended human corrections;
- names and important terms remain consistent;
- Vietnamese speech contains no material omission, repetition, clipping, or wrong segment ordering;
- pronunciation and voice quality are acceptable for the MVP candidate;
- speech remains acceptably synchronized and no unsafe duration truncation occurred;
- subtitle font, size, color, outline, wrapping, alignment, Vietnamese diacritics, and safe-area placement are acceptable;
- HTML preview and final libass render are close enough for the approved MVP style contract;
- the selected original-audio treatment is reflected in the final mix;
- final video duration, video/audio streams, playback, and download are valid;
- no output becomes downloadable before backend render validation succeeds.

## Recovery and selective reprocessing spot checks

On the same candidate, perform these focused checks without repeating the entire project:

- edit one Vietnamese segment and confirm only its speech descendants plus render become stale;
- change subtitle style and confirm OCR, translation, and speech are reused while render changes;
- cancel and retry one render;
- restart API/worker processes during a retry-safe stage and confirm durable state recovers;
- confirm an old immutable render remains traceable to its frozen manifest after a newer render is created.

## Acceptance record

Record PASS/FAIL, tester, date, candidate identifiers, input fixture, chosen tone/audio policy, observed defects, and links or artifact IDs for the final manifest, output, and validation report. Any defect that requires code or policy changes gets a regression test before a new candidate is accepted.
