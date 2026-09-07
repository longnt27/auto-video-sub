"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type SpeechAttempt = {
  id: string;
  attempt_index: number;
  parent_attempt_id: string | null;
  translation_revision_id: string;
  text: string;
  text_origin: string;
  provider: string;
  model: string;
  model_revision: string;
  voice_id: string;
  measured_duration_us: number | null;
  trimmed_duration_us: number | null;
  final_duration_us: number | null;
  silence_removed_us: number;
  speed_factor_ppm: number;
  slot_us: number;
  tolerance_us: number;
  outcome: string | null;
  error_code: string | null;
};

type SpeechSegment = {
  id: string;
  ordinal: number;
  start_us: number;
  end_us: number;
  translation_revision_id: string;
  text: string;
  tone: string;
  status: string;
  current_attempt: SpeechAttempt | null;
  attempts: SpeechAttempt[];
  audio_url: string | null;
};

type Speech = {
  project_id: string;
  media_asset_id: string;
  status: string;
  workflow_id: string | null;
  error_code: string | null;
  provider: string;
  model: string;
  model_revision: string;
  voice_id: string;
  policy: {
    version: string;
    tolerance_us: number;
    max_speed_factor_ppm: number;
    max_rewrite_attempts: number;
  };
  version: number;
  segments: SpeechSegment[];
};

type Props = {
  projectId: string;
  mediaAssetId: string;
  disabled?: boolean;
  onMessage?: (message: string) => void;
};

class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

const API = "/api/backend/v1";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { cache: "no-store", ...init });
  const payload = await response.json();
  if (!response.ok) {
    throw new ApiError(payload?.error?.message ?? "Request failed", response.status);
  }
  return payload as T;
}

function duration(value: number | null): string {
  return value === null ? "—" : `${(value / 1_000_000).toFixed(2)}s`;
}

export default function SpeechReview({
  projectId,
  mediaAssetId,
  disabled = false,
  onMessage,
}: Props) {
  const [speech, setSpeech] = useState<Speech | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [repairBaselineVersion, setRepairBaselineVersion] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const applySpeech = useCallback((next: Speech) => {
    setSpeech(next);
    setDrafts(
      Object.fromEntries(
        next.segments.map((segment) => [
          segment.id,
          segment.current_attempt?.text ?? segment.text,
        ]),
      ),
    );
  }, []);

  const load = useCallback(async () => {
    try {
      const next = await api<Speech>(`/projects/${projectId}/media/${mediaAssetId}/speech`);
      applySpeech(next);
      setError(null);
      if (repairBaselineVersion !== null && next.version > repairBaselineVersion) {
        setRepairBaselineVersion(null);
      }
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 404) {
        setSpeech(null);
        return;
      }
      const message = reason instanceof Error ? reason.message : "Could not load speech review";
      setError(message);
      onMessage?.(message);
    }
  }, [applySpeech, mediaAssetId, onMessage, projectId, repairBaselineVersion]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!speech || (speech.status !== "processing" && repairBaselineVersion === null)) return;
    const timer = window.setInterval(() => void load(), 2000);
    return () => window.clearInterval(timer);
  }, [load, repairBaselineVersion, speech]);

  const allFit = Boolean(
    speech && speech.segments.length > 0 && speech.segments.every((segment) => segment.status === "fit"),
  );
  const playable = useMemo(
    () => speech?.segments.filter((segment) => segment.audio_url) ?? [],
    [speech],
  );

  async function start() {
    setBusy(true);
    try {
      const next = await api<Speech>(`/projects/${projectId}/media/${mediaAssetId}/speech/start`, {
        method: "POST",
      });
      applySpeech(next);
      setError(null);
      onMessage?.("Vietnamese speech fitting started on the local-AI queue.");
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Speech start failed";
      setError(message);
      onMessage?.(message);
    } finally {
      setBusy(false);
    }
  }

  async function retry(segment: SpeechSegment) {
    if (!speech) return;
    const candidate = drafts[segment.id]?.trim() ?? "";
    const currentText = segment.current_attempt?.text ?? segment.text;
    setBusy(true);
    try {
      const baseline = speech.version;
      await api<Speech>(
        `/projects/${projectId}/media/${mediaAssetId}/speech/segments/${segment.id}/retry`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ text: candidate && candidate !== currentText ? candidate : null }),
        },
      );
      setRepairBaselineVersion(baseline);
      setError(null);
      onMessage?.(`Queued speech refit for segment ${segment.ordinal + 1}.`);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Speech retry failed";
      setError(message);
      onMessage?.(message);
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    if (!speech) return;
    setBusy(true);
    try {
      const next = await api<Speech>(`/projects/${projectId}/media/${mediaAssetId}/speech/approve`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ expected_version: speech.version }),
      });
      applySpeech(next);
      setError(null);
      onMessage?.("Vietnamese speech approved. Phase 6 can freeze these selected attempts.");
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Speech approval failed";
      setError(message);
      onMessage?.(message);
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!speech) return;
    setBusy(true);
    try {
      const next = await api<Speech>(`/projects/${projectId}/media/${mediaAssetId}/speech/cancel`, {
        method: "POST",
      });
      applySpeech(next);
      setRepairBaselineVersion(null);
      setError(null);
      onMessage?.("Speech workflow cancelled; immutable completed attempts were retained.");
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Speech cancellation failed";
      setError(message);
      onMessage?.(message);
    } finally {
      setBusy(false);
    }
  }

  async function playSequence() {
    for (const segment of playable) {
      if (!segment.audio_url) continue;
      await new Promise<void>((resolve, reject) => {
        const player = new Audio(segment.audio_url ?? "");
        player.onended = () => resolve();
        player.onerror = () => reject(new Error("Sequence audio playback failed"));
        void player.play().catch(reject);
      });
    }
  }

  return (
    <section aria-label="Vietnamese speech review" style={{ marginTop: "1.5rem" }}>
      <div className="preview-heading">
        <div>
          <p className="step">09 · Vietnamese speech</p>
          <h3>Duration-fitted local speech</h3>
        </div>
        <span className={`badge ${speech?.status ?? "idle"}`}>
          {speech?.status ?? "not started"}
        </span>
      </div>

      {!speech && (
        <div className="cost-box">
          <p className="control-copy">
            Start only after the Vietnamese translation is approved. VieNeu synthesis, FFmpeg
            fitting, and local rewrite run without a paid provider.
          </p>
          <button type="button" disabled={disabled || busy} onClick={() => void start()}>
            Start Vietnamese speech
          </button>
        </div>
      )}

      {speech && (
        <>
          <div className="cost-summary">
            <span>
              {speech.provider} · {speech.model}
            </span>
            <span>voice {speech.voice_id}</span>
            <span>speed ≤ {(speech.policy.max_speed_factor_ppm / 1_000_000).toFixed(2)}×</span>
            <span>rewrite ≤ {speech.policy.max_rewrite_attempts}</span>
          </div>
          <div className="inline" style={{ marginBottom: "1rem" }}>
            <button
              type="button"
              className="secondary"
              disabled={disabled || busy || playable.length === 0}
              onClick={() => void playSequence().catch((reason) => setError(String(reason)))}
            >
              Play fitted sequence
            </button>
            {!["approved", "cancelled", "failed"].includes(speech.status) && (
              <button
                type="button"
                className="secondary"
                disabled={disabled || busy}
                onClick={() => void cancel()}
              >
                Cancel speech
              </button>
            )}
          </div>

          <div className="translation-list">
            {speech.segments.map((segment) => {
              const attempt = segment.current_attempt;
              return (
                <article className="translation-row" key={segment.id}>
                  <div className="segment-time">
                    <strong>#{segment.ordinal + 1}</strong>
                    <span>{segment.status}</span>
                    <small>
                      slot {duration(segment.end_us - segment.start_us)} · final {duration(attempt?.final_duration_us ?? null)}
                    </small>
                  </div>
                  <div className="translation-edit">
                    <small>
                      {attempt?.text_origin ?? "translation"} · {attempt?.outcome ?? "pending"}
                    </small>
                    <textarea
                      rows={2}
                      maxLength={4000}
                      value={drafts[segment.id] ?? attempt?.text ?? segment.text}
                      disabled={
                        disabled || busy || speech.status !== "waiting_for_review"
                      }
                      onChange={(event) =>
                        setDrafts((current) => ({ ...current, [segment.id]: event.target.value }))
                      }
                    />
                    {speech.status === "waiting_for_review" && (
                      <button
                        type="button"
                        className="secondary"
                        disabled={disabled || busy || !drafts[segment.id]?.trim()}
                        onClick={() => void retry(segment)}
                      >
                        Retry / refit segment
                      </button>
                    )}
                  </div>
                  <div className="source-card">
                    <small>Selected audio</small>
                    {segment.audio_url ? (
                      <audio src={segment.audio_url} controls preload="metadata" />
                    ) : (
                      <p>No selectable fitted audio yet.</p>
                    )}
                    {attempt && (
                      <small>
                        raw {duration(attempt.measured_duration_us)} · trimmed {duration(attempt.trimmed_duration_us)} · speed {(attempt.speed_factor_ppm / 1_000_000).toFixed(3)}×
                      </small>
                    )}
                    {segment.attempts.length > 0 && (
                      <details>
                        <summary>{segment.attempts.length} immutable attempt(s)</summary>
                        {segment.attempts.map((item) => (
                          <p key={item.id}>
                            #{item.attempt_index} · {item.text_origin} · {item.outcome ?? "running"} · {duration(item.final_duration_us ?? item.trimmed_duration_us)}
                            {item.error_code ? ` · ${item.error_code}` : ""}
                          </p>
                        ))}
                      </details>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
          {speech.status === "waiting_for_review" && (
            <button
              type="button"
              className="approve-wide"
              disabled={disabled || busy || !allFit}
              onClick={() => void approve()}
            >
              Approve Vietnamese speech
            </button>
          )}
          {speech.error_code && <p className="status-line">Speech error: {speech.error_code}</p>}
        </>
      )}
      {error && <p className="status-line">{error}</p>}
    </section>
  );
}
