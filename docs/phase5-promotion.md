# Phase 5 promotion evidence

Phase 5 implementation may merge before local TTS promotion, but Phase 5 does not close and Phase 6 does not start until the exact VieNeu model revision and preset voice pass this gate.

## Run on the supported Apple Silicon host

Configure the exact candidate snapshot and voice, then run:

```bash
export VIENEU_MODEL_HOST_PATH=/absolute/path/to/pinned/vieneu
export VIENEU_MODEL_REVISION=<exact-reviewed-revision>
export VIENEU_VOICE_ID=<preset-voice-id>
export VIENEU_PRECISION=int8
./scripts/benchmark-phase5.sh
```

The command builds the worker image for `linux/arm64`, runs it with `--network none`, and writes evidence to `reports/phase5-promotion/` by default.

## Automated promotion checks

`benchmark.json` must show:

- `machine` is `aarch64` or `arm64`;
- the exact intended model revision, voice, and precision;
- all fixtures synthesize successfully;
- every output is non-empty mono 48 kHz WAV;
- per-sample wall time, audio duration, real-time factor, and aggregate p50/p95 are recorded;
- peak process RSS is recorded;
- the benchmark was invoked through the provided network-disabled container command.

Phase 5 does not set a throughput target; Phase 7 owns capacity/admission targets. The Phase 5 benchmark proves the supported arm64 container can run the pinned local TTS path successfully and records its measured envelope.

## Human listening/content-integrity gate

Open every generated WAV listed in `LISTENING_REVIEW.md` and approve only when all samples:

1. preserve the written Vietnamese content without additions or omissions;
2. have acceptable pronunciation for the single MVP preset voice;
3. contain no corruption, clipping, or unexplained silence.

Check every row and the final reviewer decision in `LISTENING_REVIEW.md`. Keep `benchmark.json` and the completed review together as the promotion evidence for the exact model revision + voice pair.

A different model revision, preset voice, precision mode, or TTS provider requires fresh promotion evidence. Voice cloning is not part of the MVP.
