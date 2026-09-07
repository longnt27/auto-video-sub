"use client";

import { useCallback, useEffect, useState } from "react";

type AudioPolicy = "retain" | "reduce" | "remove";

type RenderSnapshot = {
  id: string;
  project_id: string;
  media_asset_id: string;
  status: string;
  workflow_id: string | null;
  input_fingerprint: string;
  audio_policy: AudioPolicy;
  original_audio_gain_ppm: number;
  renderer_version: string;
  font_filename: string;
  font_checksum_sha256: string;
  manifest_artifact_id: string | null;
  subtitle_artifact_id: string | null;
  output_artifact_id: string | null;
  validation_artifact_id: string | null;
  error_code: string | null;
  version: number;
  validation: Record<string, unknown> | null;
  download_url: string | null;
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

function policyLabel(policy: AudioPolicy): string {
  if (policy === "retain") return "Keep original audio at full level";
  if (policy === "remove") return "Remove original audio";
  return "Keep original audio quietly under Vietnamese speech";
}

export default function RenderReview({
  projectId,
  mediaAssetId,
  disabled = false,
  onMessage,
}: Props) {
  const [render, setRender] = useState<RenderSnapshot | null>(null);
  const [audioPolicy, setAudioPolicy] = useState<AudioPolicy | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await api<RenderSnapshot>(`/projects/${projectId}/media/${mediaAssetId}/render`);
      setRender(next);
      setAudioPolicy((current) => current || next.audio_policy);
      setError(null);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 404) {
        setRender(null);
        return;
      }
      const message = reason instanceof Error ? reason.message : "Could not load render status";
      setError(message);
      onMessage?.(message);
    }
  }, [mediaAssetId, onMessage, projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!render || !["processing", "validating"].includes(render.status)) return;
    const timer = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(timer);
  }, [load, render]);

  async function start() {
    if (!audioPolicy) return;
    setBusy(true);
    try {
      const next = await api<RenderSnapshot>(
        `/projects/${projectId}/media/${mediaAssetId}/render/start`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ audio_policy: audioPolicy }),
        },
      );
      setRender(next);
      setError(null);
      onMessage?.("Final render started from frozen approved inputs.");
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Render start failed";
      setError(message);
      onMessage?.(message);
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!render) return;
    setBusy(true);
    try {
      const next = await api<RenderSnapshot>(
        `/projects/${projectId}/media/${mediaAssetId}/render/cancel`,
        { method: "POST" },
      );
      setRender(next);
      setError(null);
      onMessage?.("Render cancelled; immutable upstream inputs were retained.");
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Render cancellation failed";
      setError(message);
      onMessage?.(message);
    } finally {
      setBusy(false);
    }
  }

  const running = Boolean(render && ["processing", "validating"].includes(render.status));
  const canStart = !running && render?.status !== "succeeded";

  return (
    <section aria-label="Final render and download" style={{ marginTop: "1.5rem" }}>
      <div className="preview-heading">
        <div>
          <p className="step">10 · Render + export</p>
          <h3>Freeze, render, validate, download</h3>
        </div>
        <span className={`badge ${render?.status ?? "idle"}`}>
          {render?.status ?? "not started"}
        </span>
      </div>

      <div className="cost-box">
        <label htmlFor="original-audio-policy">Original audio treatment</label>
        <select
          id="original-audio-policy"
          value={audioPolicy}
          disabled={disabled || busy || running || render?.status === "succeeded"}
          onChange={(event) => setAudioPolicy(event.target.value as AudioPolicy | "")}
        >
          <option value="">Choose before rendering</option>
          <option value="reduce">Reduce under Vietnamese speech</option>
          <option value="retain">Retain at full level</option>
          <option value="remove">Remove original audio</option>
        </select>
        {audioPolicy && <p className="control-copy">{policyLabel(audioPolicy)}</p>}

        {canStart && (
          <button
            type="button"
            disabled={disabled || busy || !audioPolicy}
            onClick={() => void start()}
          >
            {render && ["failed", "cancelled"].includes(render.status)
              ? "Retry final render"
              : "Render final video"}
          </button>
        )}
        {running && (
          <button
            type="button"
            className="secondary"
            disabled={disabled || busy}
            onClick={() => void cancel()}
          >
            Cancel render
          </button>
        )}
      </div>

      {render && (
        <div className="cost-summary">
          <span>{render.renderer_version}</span>
          <span>{render.font_filename}</span>
          <span>manifest {render.manifest_artifact_id ? "frozen" : "pending"}</span>
          <span>validation {render.validation_artifact_id ? "recorded" : "pending"}</span>
        </div>
      )}

      {render?.validation && (
        <details>
          <summary>Output validation report</summary>
          <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
            {JSON.stringify(render.validation, null, 2)}
          </pre>
        </details>
      )}

      {render?.status === "succeeded" && render.download_url && (
        <div className="cost-box">
          <p className="control-copy">
            Output passed backend media validation. This signed link is short-lived and remains
            tailnet-only.
          </p>
          <a className="approve-wide" href={render.download_url}>
            Download validated Vietnamese video
          </a>
        </div>
      )}

      {render?.error_code && <p className="status-line">Render error: {render.error_code}</p>}
      {render && (
        <p className="status-line">
          Frozen input {render.input_fingerprint.slice(0, 12)}… · audio {render.audio_policy}
        </p>
      )}
      {error && <p className="status-line">{error}</p>}
    </section>
  );
}
