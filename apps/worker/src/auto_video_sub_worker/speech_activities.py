from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from auto_video_sub_application.speech_ports import (
    LocalRewriteProvider,
    PublishedSpeechArtifact,
    RewriteProviderError,
    RewriteRequest,
    SpeechAudioProcessor,
    SpeechObjectStorage,
    SpeechWorkflowRepository,
    TtsProvider,
    TtsProviderError,
    TtsRequest,
)
from auto_video_sub_domain import (
    ArtifactKind,
    DurationFitAction,
    DurationFitPolicy,
    SpeechAttempt,
    SpeechAttemptOutcome,
    SpeechStatus,
    SpeechTextOrigin,
    decide_duration_fit,
)
from temporalio import activity
from temporalio.exceptions import ApplicationError


class SpeechActivities:
    def __init__(
        self,
        *,
        repository: SpeechWorkflowRepository,
        storage: SpeechObjectStorage,
        tts: TtsProvider,
        audio: SpeechAudioProcessor,
        rewriter: LocalRewriteProvider,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._tts = tts
        self._audio = audio
        self._rewriter = rewriter

    @activity.defn(name="list-speech-segments-v1")
    async def list_segments(self, payload: dict[str, str]) -> list[str]:
        media_asset_id = UUID(payload["media_asset_id"])
        inputs = await self._repository.list_inputs_internal(media_asset_id)
        return [str(item.id) for item in inputs]

    @activity.defn(name="fit-speech-segment-v1")
    async def fit_segment(self, payload: dict[str, str]) -> dict[str, str]:
        media_asset_id = UUID(payload["media_asset_id"])
        segment_id = UUID(payload["segment_id"])
        cycle_index = int(payload["cycle_index"])
        if cycle_index < 0:
            raise ApplicationError(
                "Speech repair cycle is invalid",
                type="DURATION_ATTEMPT_INVALID",
                non_retryable=True,
            )
        record = await self._repository.get_record_internal(media_asset_id)
        inputs = await self._repository.list_inputs_internal(media_asset_id)
        segment = next((item for item in inputs if item.id == segment_id), None)
        if segment is None:
            raise ApplicationError(
                "Speech segment does not exist",
                type="TTS_SEGMENT_NOT_FOUND",
                non_retryable=True,
            )
        await self._repository.mark_segment_fitting(segment.id)

        override = payload.get("text", "").strip()
        text = override or segment.text
        origin = SpeechTextOrigin.USER if override else SpeechTextOrigin.TRANSLATION
        previous_rewrites: list[str] = []
        parent_attempt_id: UUID | None = None
        rewrite_index = 0
        width = record.policy.max_rewrite_attempts + 1

        while True:
            activity.heartbeat(
                {
                    "segment_id": str(segment.id),
                    "cycle_index": cycle_index,
                    "rewrite_index": rewrite_index,
                }
            )
            attempt_index = cycle_index * width + rewrite_index
            attempt = await self._repository.begin_attempt(
                segment=segment,
                attempt_index=attempt_index,
                parent_attempt_id=parent_attempt_id,
                text=text,
                text_origin=origin,
                provider=record.provider,
                model=record.model,
                model_revision=record.model_revision,
                voice_id=record.voice_id,
                policy=record.policy,
            )

            if attempt.outcome is SpeechAttemptOutcome.FIT:
                await self._repository.mark_segment_fit(segment.id, attempt.id)
                return {"status": "fit", "segment_id": str(segment.id)}
            if attempt.outcome is SpeechAttemptOutcome.NEEDS_REVIEW:
                await self._repository.mark_segment_needs_review(segment.id, attempt.id)
                return {"status": "needs_review", "segment_id": str(segment.id)}
            if attempt.outcome is SpeechAttemptOutcome.FAILED:
                raise ApplicationError(
                    "Speech attempt already failed permanently",
                    type=attempt.error_code or "TTS_ATTEMPT_FAILED",
                    non_retryable=True,
                )

            if attempt.outcome is None:
                attempt = await self._synthesize_and_measure(
                    attempt,
                    policy=record.policy,
                    rewrite_attempts_used=rewrite_index,
                )

            if attempt.outcome is SpeechAttemptOutcome.FIT:
                await self._repository.mark_segment_fit(segment.id, attempt.id)
                return {"status": "fit", "segment_id": str(segment.id)}
            if attempt.outcome is SpeechAttemptOutcome.NEEDS_REVIEW:
                await self._repository.mark_segment_needs_review(segment.id, attempt.id)
                return {"status": "needs_review", "segment_id": str(segment.id)}
            if attempt.outcome is not SpeechAttemptOutcome.REWRITE_REQUIRED:
                raise ApplicationError(
                    "Speech attempt ended in an invalid state",
                    type="INTERNAL_INVARIANT",
                    non_retryable=True,
                )

            measured_us = attempt.trimmed_duration_us or attempt.measured_duration_us
            if measured_us is None:
                raise ApplicationError(
                    "Speech rewrite is missing measured duration",
                    type="INTERNAL_INVARIANT",
                    non_retryable=True,
                )
            try:
                rewritten = await self._rewriter.rewrite(
                    RewriteRequest(
                        segment_id=segment.id,
                        text=attempt.text,
                        tone=segment.tone,
                        protected_terms=segment.protected_terms,
                        target_duration_us=segment.slot_us + record.policy.tolerance_us,
                        measured_duration_us=measured_us,
                        previous_rewrites=tuple(previous_rewrites),
                    )
                )
            except RewriteProviderError as error:
                if not error.retryable:
                    await self._repository.mark_segment_needs_review(segment.id, attempt.id)
                    return {"status": "needs_review", "segment_id": str(segment.id)}
                raise ApplicationError(
                    str(error),
                    type=error.code,
                    non_retryable=False,
                ) from error

            previous_rewrites.append(rewritten.text)
            parent_attempt_id = attempt.id
            text = rewritten.text
            origin = SpeechTextOrigin.LOCAL_REWRITE
            rewrite_index += 1
            if rewrite_index > record.policy.max_rewrite_attempts:
                await self._repository.mark_segment_needs_review(segment.id, attempt.id)
                return {"status": "needs_review", "segment_id": str(segment.id)}

    async def _synthesize_and_measure(
        self,
        attempt: SpeechAttempt,
        *,
        policy: DurationFitPolicy,
        rewrite_attempts_used: int,
    ) -> SpeechAttempt:
        try:
            with tempfile.TemporaryDirectory(prefix="auto-video-sub-speech-") as temp_dir:
                root = Path(temp_dir)
                raw_path = root / "raw.wav"
                trimmed_path = root / "trimmed.wav"
                fitted_path = root / "fitted.wav"
                envelope_path = root / "attempt.json"

                result = await self._tts.synthesize(
                    TtsRequest(
                        segment_id=attempt.subtitle_segment_id,
                        text=attempt.text,
                        voice_id=attempt.voice_id,
                    )
                )
                raw_path.write_bytes(result.wav_bytes)
                measured_us = await self._audio.probe_duration(raw_path)
                trimmed = await self._audio.trim_edge_silence(raw_path, trimmed_path)
                decision = decide_duration_fit(
                    slot_us=attempt.slot_us,
                    measured_us=measured_us,
                    trimmed_us=trimmed.duration_us,
                    rewrite_attempts_used=rewrite_attempts_used,
                    policy=policy,
                )

                raw_artifact = await self._publish(
                    attempt,
                    raw_path,
                    kind=ArtifactKind.SPEECH_RAW_AUDIO,
                    role="raw",
                    media_type="audio/wav",
                )
                trimmed_artifact = await self._publish(
                    attempt,
                    trimmed_path,
                    kind=ArtifactKind.SPEECH_TRIMMED_AUDIO,
                    role="trimmed",
                    media_type="audio/wav",
                )

                final_artifact = None
                final_duration_us: int | None = None
                speed_factor_ppm = 1_000_000
                outcome = SpeechAttemptOutcome.REWRITE_REQUIRED
                if decision.action is DurationFitAction.ACCEPT:
                    final_artifact = trimmed_artifact
                    final_duration_us = trimmed.duration_us
                    outcome = SpeechAttemptOutcome.FIT
                elif decision.action is DurationFitAction.SPEED_UP:
                    speed_factor_ppm = decision.speed_factor_ppm
                    fitted = await self._audio.speed_up(
                        trimmed_path,
                        fitted_path,
                        speed_factor_ppm=speed_factor_ppm,
                    )
                    if fitted.duration_us > decision.target_us:
                        outcome = SpeechAttemptOutcome.NEEDS_REVIEW
                        final_artifact = trimmed_artifact
                        final_duration_us = trimmed.duration_us
                        speed_factor_ppm = 1_000_000
                    else:
                        final_artifact = await self._publish(
                            attempt,
                            fitted_path,
                            kind=ArtifactKind.SPEECH_FITTED_AUDIO,
                            role="fitted",
                            media_type="audio/wav",
                        )
                        final_duration_us = fitted.duration_us
                        outcome = SpeechAttemptOutcome.FIT
                elif decision.action is DurationFitAction.REVIEW:
                    final_artifact = trimmed_artifact
                    final_duration_us = trimmed.duration_us
                    outcome = SpeechAttemptOutcome.NEEDS_REVIEW

                envelope = {
                    "segment_id": str(attempt.subtitle_segment_id),
                    "attempt_id": str(attempt.id),
                    "attempt_index": attempt.attempt_index,
                    "translation_revision_id": str(attempt.translation_revision_id),
                    "text": attempt.text,
                    "text_origin": attempt.text_origin.value,
                    "provider": attempt.provider,
                    "model": attempt.model,
                    "model_revision": attempt.model_revision,
                    "voice_id": attempt.voice_id,
                    "policy_version": attempt.policy_version,
                    "slot_us": attempt.slot_us,
                    "tolerance_us": attempt.tolerance_us,
                    "measured_duration_us": measured_us,
                    "trimmed_duration_us": trimmed.duration_us,
                    "final_duration_us": final_duration_us,
                    "silence_removed_us": trimmed.silence_removed_us,
                    "speed_factor_ppm": speed_factor_ppm,
                    "outcome": outcome.value,
                }
                envelope_path.write_text(
                    json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8",
                )
                envelope_artifact = await self._publish(
                    attempt,
                    envelope_path,
                    kind=ArtifactKind.SPEECH_ATTEMPT_ENVELOPE,
                    role="envelope",
                    media_type="application/json",
                )
                artifacts = [raw_artifact, trimmed_artifact, envelope_artifact]
                if final_artifact is not None and final_artifact.id not in {
                    raw_artifact.id,
                    trimmed_artifact.id,
                }:
                    artifacts.append(final_artifact)
                return await self._repository.finish_attempt(
                    attempt_id=attempt.id,
                    artifacts=tuple(artifacts),
                    raw_audio_artifact_id=raw_artifact.id,
                    trimmed_audio_artifact_id=trimmed_artifact.id,
                    final_audio_artifact_id=(
                        final_artifact.id if final_artifact is not None else None
                    ),
                    envelope_artifact_id=envelope_artifact.id,
                    measured_duration_us=measured_us,
                    trimmed_duration_us=trimmed.duration_us,
                    final_duration_us=final_duration_us,
                    silence_removed_us=trimmed.silence_removed_us,
                    speed_factor_ppm=speed_factor_ppm,
                    outcome=outcome.value,
                )
        except TtsProviderError as error:
            if not error.retryable:
                await self._repository.mark_attempt_failed(
                    attempt_id=attempt.id, error_code=error.code
                )
            raise ApplicationError(
                str(error),
                type=error.code,
                non_retryable=not error.retryable,
            ) from error

    async def _publish(
        self,
        attempt: SpeechAttempt,
        path: Path,
        *,
        kind: ArtifactKind,
        role: str,
        media_type: str,
    ) -> PublishedSpeechArtifact:
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        artifact_id = uuid5(
            NAMESPACE_URL,
            f"auto-video-sub:speech:{attempt.id}:{role}:{checksum}",
        )
        suffix = path.suffix or ".bin"
        object_key = f"artifacts/{attempt.project_id}/{artifact_id}/{role}{suffix}"
        metadata = await self._storage.upload_file(path, object_key, media_type)
        return PublishedSpeechArtifact(
            id=artifact_id,
            kind=kind,
            object_key=object_key,
            media_type=media_type,
            byte_size=metadata.byte_size,
            checksum_sha256=checksum,
        )

    @activity.defn(name="finalize-speech-review-v1")
    async def finalize(self, payload: dict[str, str]) -> str:
        status = await self._repository.finalize_speech(UUID(payload["media_asset_id"]))
        return status.value

    @activity.defn(name="mark-speech-failed-v1")
    async def mark_failed(self, payload: dict[str, str]) -> None:
        await self._repository.set_speech_status(
            UUID(payload["media_asset_id"]),
            SpeechStatus.FAILED,
            error_code=payload.get("error_code", "TTS_PROCESSING_EXHAUSTED"),
        )
