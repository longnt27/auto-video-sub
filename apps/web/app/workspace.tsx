"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import SubtitleStyleReview from "./subtitle-style-review";

type Project = { id: string; title: string; lifecycle: string };
type Media = {
  id: string;
  project_id: string;
  display_name: string;
  status: string;
  error_code: string | null;
  proxy_url: string | null;
};
type UploadIntent = {
  id: string;
  media_asset_id: string;
  upload: { url: string; method: string; headers: Record<string, string> };
};
type SubtitleSegment = {
  id: string;
  ordinal: number;
  start_us: number;
  end_us: number;
  version: number;
  source: {
    id: string;
    version: number;
    text: string;
    origin: string;
    confidence: number | null;
  };
};
type Transcript = {
  project_id: string;
  media_asset_id: string;
  status: string;
  version: number;
  error_code: string | null;
  segments: SubtitleSegment[];
};
type TonePreset = { id: "natural" | "funny" | "formal" | "dramatic"; label: string };
type TranslationEstimate = {
  preset: TonePreset["id"];
  provider: string;
  model: string;
  source_characters: number;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  estimated_cost_micros: number;
};
type ContextEntity = {
  id: string;
  kind: string;
  source_forms: string[];
  preferred_vietnamese: string | null;
  confidence: number;
  ambiguous: boolean;
  notes: string | null;
  evidence_segment_ids: string[];
};
type ContextVersion = {
  id: string;
  transcript_version: number;
  version: number;
  summary: string;
  entities: ContextEntity[];
  approved: boolean;
};
type TranslationRevision = {
  id: string;
  version: number;
  text: string;
  origin: string;
  provider: string | null;
  model: string | null;
  prompt_version: string | null;
};
type TranslationSegment = {
  id: string;
  ordinal: number;
  start_us: number;
  end_us: number;
  source_text: string;
  source_version: number;
  segment_version: number;
  translation: TranslationRevision | null;
};
type Translation = {
  project_id: string;
  media_asset_id: string;
  status: string;
  version: number;
  error_code: string | null;
  estimated_cost_micros: number;
  reserved_cost_micros: number;
  actual_cost_micros: number;
  policy: {
    id: string;
    preset: TonePreset["id"];
    prompt_version: string;
    provider: string;
    model: string;
    version: number;
  };
  context: ContextVersion | null;
  segments: TranslationSegment[];
  findings: { code: string; segment_id: string | null; message: string }[];
};
type ContextDraft = { summary: string; entities: ContextEntity[] };

const API = "/api/backend/v1";
const ACCEPTED_MEDIA_TYPES = new Set([
  "video/mp4",
  "video/quicktime",
  "video/x-matroska",
  "video/webm",
]);

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { cache: "no-store", ...init });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? "Request failed");
  return payload as T;
}

function mediaContentType(file: File): string {
  if (ACCEPTED_MEDIA_TYPES.has(file.type)) return file.type;
  const extension = file.name.split(".").pop()?.toLowerCase();
  const byExtension: Record<string, string> = {
    mp4: "video/mp4",
    mov: "video/quicktime",
    mkv: "video/x-matroska",
    webm: "video/webm",
  };
  const inferred = extension ? byExtension[extension] : undefined;
  if (!inferred) throw new Error("Choose an MP4, MOV, MKV, or WebM video.");
  return inferred;
}

function formatTime(timeUs: number): string {
  const totalSeconds = timeUs / 1_000_000;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds - minutes * 60;
  return `${minutes}:${seconds.toFixed(2).padStart(5, "0")}`;
}

function formatMicros(value: number): string {
  return `${new Intl.NumberFormat().format(value)} cost-µ`;
}

export default function Workspace() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [title, setTitle] = useState("");
  const [media, setMedia] = useState<Media | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [sourceDrafts, setSourceDrafts] = useState<Record<string, string>>({});
  const [tones, setTones] = useState<TonePreset[]>([]);
  const [selectedTone, setSelectedTone] = useState<TonePreset["id"]>("natural");
  const [estimate, setEstimate] = useState<TranslationEstimate | null>(null);
  const [confirmPaid, setConfirmPaid] = useState(false);
  const [translation, setTranslation] = useState<Translation | null>(null);
  const [translationDrafts, setTranslationDrafts] = useState<Record<string, string>>({});
  const [contextDraft, setContextDraft] = useState<ContextDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [transcriptBusy, setTranscriptBusy] = useState(false);
  const [translationBusy, setTranslationBusy] = useState(false);
  const [message, setMessage] = useState("Ready for a tailnet-only upload.");

  const refreshProjects = useCallback(async () => {
    try {
      const result = await api<Project[]>("/projects");
      setProjects(result);
      setSelectedProject((current) => current || result[0]?.id || "");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load projects");
    }
  }, []);

  const applyTranscript = useCallback((next: Transcript) => {
    setTranscript(next);
    setSourceDrafts(
      Object.fromEntries(next.segments.map((segment) => [segment.id, segment.source.text])),
    );
  }, []);

  const applyTranslation = useCallback((next: Translation) => {
    setTranslation(next);
    setTranslationDrafts(
      Object.fromEntries(
        next.segments.map((segment) => [segment.id, segment.translation?.text ?? ""]),
      ),
    );
    if (next.context) {
      setContextDraft({
        summary: next.context.summary,
        entities: next.context.entities.map((entity) => ({ ...entity })),
      });
    }
  }, []);

  useEffect(() => {
    void refreshProjects();
    void api<TonePreset[]>("/translation/tones")
      .then(setTones)
      .catch((error) =>
        setMessage(error instanceof Error ? error.message : "Could not load translation tones"),
      );
  }, [refreshProjects]);

  useEffect(() => {
    if (!media || !["object_received", "validating", "proxy_generating"].includes(media.status)) {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const next = await api<Media>(`/projects/${media.project_id}/media/${media.id}`);
        setMedia(next);
        setMessage(
          next.status === "ready"
            ? "Proxy ready. Start source transcript extraction."
            : `Processing: ${next.status}`,
        );
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Status refresh failed");
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [media]);

  useEffect(() => {
    if (!media || transcript?.status !== "processing") return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api<Transcript>(
          `/projects/${media.project_id}/media/${media.id}/transcript`,
        );
        applyTranscript(next);
        setMessage(
          next.status === "waiting_for_review"
            ? "OCR complete. Review and correct the Chinese transcript."
            : `Transcript processing: ${next.status}`,
        );
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Transcript refresh failed");
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [applyTranscript, media, transcript?.status]);

  useEffect(() => {
    if (
      !media ||
      !translation ||
      !["context_processing", "translating"].includes(translation.status)
    )
      return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api<Translation>(
          `/projects/${media.project_id}/media/${media.id}/translation`,
        );
        applyTranslation(next);
        if (next.status === "waiting_for_context_review") {
          setMessage(
            "Story context extracted. Review names, terms, and ambiguities before paid translation batches continue.",
          );
        } else if (next.status === "waiting_for_review") {
          setMessage(
            "Vietnamese translation complete. Review findings and edit any segment before approval.",
          );
        } else {
          setMessage(`Translation processing: ${next.status}`);
        }
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Translation refresh failed");
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [applyTranslation, media, translation]);

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      const project = await api<Project>("/projects", {
        method: "POST",
        headers: { "content-type": "application/json", "idempotency-key": crypto.randomUUID() },
        body: JSON.stringify({ title }),
      });
      setTitle("");
      setSelectedProject(project.id);
      await refreshProjects();
      setMessage("Project created. Choose a video to upload.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Project creation failed");
    } finally {
      setBusy(false);
    }
  }

  async function uploadVideo(file: File) {
    if (!selectedProject) return setMessage("Create or select a project first.");
    setBusy(true);
    setMedia(null);
    setTranscript(null);
    setTranslation(null);
    setEstimate(null);
    try {
      const contentType = mediaContentType(file);
      const intent = await api<UploadIntent>(`/projects/${selectedProject}/uploads`, {
        method: "POST",
        headers: { "content-type": "application/json", "idempotency-key": crypto.randomUUID() },
        body: JSON.stringify({
          file_name: file.name,
          content_type: contentType,
          byte_size: file.size,
        }),
      });
      setMessage("Uploading directly to local object storage…");
      const upload = await fetch(intent.upload.url, {
        method: intent.upload.method,
        headers: intent.upload.headers,
        body: file,
      });
      if (!upload.ok) throw new Error(`Object upload failed (${upload.status})`);
      const next = await api<Media>(`/projects/${selectedProject}/uploads/${intent.id}/complete`, {
        method: "POST",
      });
      setMedia(next);
      setMessage("Upload sealed. Starting validation and proxy generation…");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function startTranscript() {
    if (!media || media.status !== "ready") return;
    setTranscriptBusy(true);
    try {
      const next = await api<Transcript>(
        `/projects/${media.project_id}/media/${media.id}/transcript/start`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({}),
        },
      );
      applyTranscript(next);
      setMessage("Extracting the configured subtitle band and running local OCR…");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Transcript start failed");
    } finally {
      setTranscriptBusy(false);
    }
  }

  async function saveSourceSegment(segment: SubtitleSegment) {
    if (!media) return;
    const text = sourceDrafts[segment.id]?.trim();
    if (!text || text === segment.source.text) return;
    setTranscriptBusy(true);
    try {
      await api<SubtitleSegment>(
        `/projects/${media.project_id}/media/${media.id}/transcript/segments/${segment.id}/revisions`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ text, expected_version: segment.version }),
        },
      );
      applyTranscript(
        await api<Transcript>(`/projects/${media.project_id}/media/${media.id}/transcript`),
      );
      setMessage(`Saved source revision for segment ${segment.ordinal + 1}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Segment save failed");
    } finally {
      setTranscriptBusy(false);
    }
  }

  async function approveTranscript() {
    if (!media || transcript?.status !== "waiting_for_review") return;
    setTranscriptBusy(true);
    try {
      const next = await api<Transcript>(
        `/projects/${media.project_id}/media/${media.id}/transcript/approve`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ expected_version: transcript.version }),
        },
      );
      applyTranscript(next);
      setMessage("Source transcript approved. Choose a tone and estimate paid translation.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Transcript approval failed");
    } finally {
      setTranscriptBusy(false);
    }
  }

  async function cancelTranscript() {
    if (!media || !transcript) return;
    setTranscriptBusy(true);
    try {
      applyTranscript(
        await api<Transcript>(`/projects/${media.project_id}/media/${media.id}/transcript/cancel`, {
          method: "POST",
        }),
      );
      setMessage("Transcript processing cancelled safely.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Transcript cancellation failed");
    } finally {
      setTranscriptBusy(false);
    }
  }

  async function restartTranscript() {
    if (!media || !transcript) return;
    setTranscriptBusy(true);
    try {
      applyTranscript(
        await api<Transcript>(
          `/projects/${media.project_id}/media/${media.id}/transcript/restart`,
          { method: "POST" },
        ),
      );
      setMessage("Transcript processing restarted from reusable durable inputs.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Transcript restart failed");
    } finally {
      setTranscriptBusy(false);
    }
  }

  async function estimateTranslation() {
    if (!media || transcript?.status !== "approved") return;
    setTranslationBusy(true);
    try {
      const next = await api<TranslationEstimate>(
        `/projects/${media.project_id}/media/${media.id}/translation/estimate`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ preset: selectedTone }),
        },
      );
      setEstimate(next);
      setConfirmPaid(false);
      setMessage("Translation estimate ready. Confirm the paid operation to start.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Translation estimate failed");
    } finally {
      setTranslationBusy(false);
    }
  }

  async function startTranslation() {
    if (!media || !estimate || !confirmPaid) return;
    setTranslationBusy(true);
    try {
      const next = await api<Translation>(
        `/projects/${media.project_id}/media/${media.id}/translation/start`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            preset: selectedTone,
            confirm_paid: true,
            max_cost_micros: estimate.estimated_cost_micros,
          }),
        },
      );
      applyTranslation(next);
      setMessage("Paid context extraction started under the confirmed cost scope.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Translation start failed");
    } finally {
      setTranslationBusy(false);
    }
  }

  async function approveContext() {
    if (!media || !translation || !contextDraft) return;
    setTranslationBusy(true);
    try {
      const next = await api<Translation>(
        `/projects/${media.project_id}/media/${media.id}/translation/context/approve`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            expected_version: translation.version,
            summary: contextDraft.summary,
            entities: contextDraft.entities.map((entity) => ({
              ...entity,
              preferred_vietnamese: entity.preferred_vietnamese?.trim() || null,
            })),
          }),
        },
      );
      applyTranslation(next);
      setMessage("Context approved. Semantic translation batches are running.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Context approval failed");
    } finally {
      setTranslationBusy(false);
    }
  }

  async function saveTranslationSegment(segment: TranslationSegment) {
    if (!media || !segment.translation) return;
    const text = translationDrafts[segment.id]?.trim();
    if (!text || text === segment.translation.text) return;
    setTranslationBusy(true);
    try {
      const next = await api<Translation>(
        `/projects/${media.project_id}/media/${media.id}/translation/segments/${segment.id}/revisions`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ text, expected_version: segment.segment_version }),
        },
      );
      applyTranslation(next);
      setMessage(`Saved Vietnamese revision for segment ${segment.ordinal + 1}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Translation edit failed");
    } finally {
      setTranslationBusy(false);
    }
  }

  async function approveTranslation() {
    if (!media || translation?.status !== "waiting_for_review") return;
    setTranslationBusy(true);
    try {
      const next = await api<Translation>(
        `/projects/${media.project_id}/media/${media.id}/translation/approve`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ expected_version: translation.version }),
        },
      );
      applyTranslation(next);
      setMessage("Vietnamese translation approved. Phase 5 can consume these immutable revisions.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Translation approval failed");
    } finally {
      setTranslationBusy(false);
    }
  }

  async function cancelTranslation() {
    if (!media || !translation) return;
    setTranslationBusy(true);
    try {
      applyTranslation(
        await api<Translation>(
          `/projects/${media.project_id}/media/${media.id}/translation/cancel`,
          { method: "POST" },
        ),
      );
      setMessage("Translation workflow cancelled; committed history remains for audit.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Translation cancellation failed");
    } finally {
      setTranslationBusy(false);
    }
  }

  return (
    <main>
      <header className="masthead">
        <div>
          <p className="eyebrow">Private video localization workspace</p>
          <h1>Auto Video Sub</h1>
        </div>
        <p className="cost-note">Local processing · translation is the only paid provider</p>
      </header>

      <section className="workspace" aria-label="Project upload workspace">
        <aside className="panel controls">
          <div>
            <p className="step">01 · Project</p>
            <form onSubmit={createProject} className="stack">
              <label htmlFor="project-title">New project title</label>
              <div className="inline">
                <input
                  id="project-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  maxLength={160}
                  placeholder="Episode 01"
                />
                <button type="submit" disabled={busy || !title.trim()}>
                  Create
                </button>
              </div>
            </form>
          </div>

          <div>
            <p className="step">02 · Source</p>
            <label htmlFor="project">Project</label>
            <select
              id="project"
              value={selectedProject}
              onChange={(event) => setSelectedProject(event.target.value)}
            >
              <option value="">Select a project</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.title}
                </option>
              ))}
            </select>
            <label className={`upload-drop ${busy ? "disabled" : ""}`}>
              <span>Choose a Chinese-language video</span>
              <small>MP4, MOV, MKV, or WebM · configurable 2 GiB limit</small>
              <input
                type="file"
                accept="video/mp4,video/quicktime,video/x-matroska,video/webm"
                disabled={busy || !selectedProject}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void uploadVideo(file);
                }}
              />
            </label>
          </div>

          <div>
            <p className="step">04 · Source transcript</p>
            <p className="control-copy">
              Run local Chinese OCR, then review stable timestamped segments before translation.
            </p>
            {!transcript && (
              <button
                type="button"
                disabled={transcriptBusy || media?.status !== "ready"}
                onClick={() => void startTranscript()}
              >
                Extract transcript
              </button>
            )}
            {transcript?.status === "processing" && (
              <button
                type="button"
                disabled={transcriptBusy}
                onClick={() => void cancelTranscript()}
              >
                Cancel processing
              </button>
            )}
            {transcript && ["failed", "cancelled"].includes(transcript.status) && (
              <button
                type="button"
                disabled={transcriptBusy}
                onClick={() => void restartTranscript()}
              >
                Restart transcript
              </button>
            )}
            {transcript?.status === "waiting_for_review" && (
              <button
                type="button"
                disabled={transcriptBusy}
                onClick={() => void approveTranscript()}
              >
                Approve transcript
              </button>
            )}
          </div>

          <div className="translation-controls">
            <p className="step">06 · Translation</p>
            <p className="control-copy">
              Translation is paid and starts only after an estimate plus explicit confirmation.
            </p>
            <label htmlFor="tone">Vietnamese tone</label>
            <select
              id="tone"
              value={selectedTone}
              disabled={
                translationBusy || transcript?.status !== "approved" || Boolean(translation)
              }
              onChange={(event) => {
                setSelectedTone(event.target.value as TonePreset["id"]);
                setEstimate(null);
                setConfirmPaid(false);
              }}
            >
              {(tones.length ? tones : [{ id: "natural", label: "Natural" } as TonePreset]).map(
                (tone) => (
                  <option key={tone.id} value={tone.id}>
                    {tone.label}
                  </option>
                ),
              )}
            </select>
            {!translation && (
              <button
                type="button"
                className="secondary"
                disabled={translationBusy || transcript?.status !== "approved"}
                onClick={() => void estimateTranslation()}
              >
                Estimate translation
              </button>
            )}
            {estimate && !translation && (
              <div className="cost-box">
                <strong>{formatMicros(estimate.estimated_cost_micros)}</strong>
                <small>
                  {estimate.provider} · {estimate.model}
                </small>
                <small>
                  {estimate.estimated_input_tokens.toLocaleString()} input +{" "}
                  {estimate.estimated_output_tokens.toLocaleString()} output tokens estimated
                </small>
                <label className="confirm-row">
                  <input
                    type="checkbox"
                    checked={confirmPaid}
                    onChange={(event) => setConfirmPaid(event.target.checked)}
                  />{" "}
                  I confirm this paid translation scope.
                </label>
                <button
                  type="button"
                  disabled={!confirmPaid || translationBusy}
                  onClick={() => void startTranslation()}
                >
                  Start paid translation
                </button>
              </div>
            )}
            {translation && !["approved", "cancelled", "failed"].includes(translation.status) && (
              <button
                type="button"
                className="secondary"
                disabled={translationBusy}
                onClick={() => void cancelTranslation()}
              >
                Cancel translation
              </button>
            )}
          </div>
        </aside>

        <section className="panel preview" aria-live="polite">
          <div className="preview-heading">
            <div>
              <p className="step">03 · Proxy preview</p>
              <h2>{media?.display_name ?? "No media yet"}</h2>
            </div>
            <span className={`badge ${media?.status ?? "idle"}`}>{media?.status ?? "idle"}</span>
          </div>
          <div className="video-shell">
            {media?.proxy_url ? (
              <video src={media.proxy_url} controls preload="metadata">
                <track kind="captions" src="/empty.vtt" srcLang="zh" label="Subtitle review" />
              </video>
            ) : (
              <p>The validated browser proxy will appear here without re-encoding during edits.</p>
            )}
          </div>
          <p className="status-line">
            {media?.error_code ? `${message} (${media.error_code})` : message}
          </p>
        </section>
      </section>

      <section className="panel transcript-panel" aria-label="Source transcript editor">
        <div className="preview-heading">
          <div>
            <p className="step">05 · Review</p>
            <h2>Chinese source transcript</h2>
          </div>
          <span className={`badge ${transcript?.status ?? "idle"}`}>
            {transcript?.status ?? "not started"}
          </span>
        </div>
        {!transcript && (
          <p className="empty-copy">
            Once the proxy is ready, extract the source transcript. OCR output stays editable and
            every correction creates a new immutable revision.
          </p>
        )}
        {transcript && transcript.segments.length === 0 && (
          <p className="empty-copy">
            {transcript.status === "processing"
              ? "OCR is still processing sampled subtitle frames."
              : "No subtitle text was detected in the configured region."}
          </p>
        )}
        <div className="segment-list">
          {transcript?.segments.map((segment) => (
            <article className="segment-row" key={segment.id}>
              <div className="segment-time">
                <strong>#{segment.ordinal + 1}</strong>
                <span>
                  {formatTime(segment.start_us)} → {formatTime(segment.end_us)}
                </span>
                <small>
                  {segment.source.origin}
                  {segment.source.confidence === null
                    ? ""
                    : ` · ${(segment.source.confidence * 100).toFixed(0)}%`}
                </small>
              </div>
              <textarea
                aria-label={`Source segment ${segment.ordinal + 1}`}
                value={sourceDrafts[segment.id] ?? segment.source.text}
                disabled={transcript.status !== "waiting_for_review" || transcriptBusy}
                onChange={(event) =>
                  setSourceDrafts((current) => ({ ...current, [segment.id]: event.target.value }))
                }
                rows={2}
                maxLength={4000}
              />
              <button
                type="button"
                className="secondary"
                disabled={
                  transcript.status !== "waiting_for_review" ||
                  transcriptBusy ||
                  !sourceDrafts[segment.id]?.trim() ||
                  sourceDrafts[segment.id]?.trim() === segment.source.text
                }
                onClick={() => void saveSourceSegment(segment)}
              >
                Save correction
              </button>
            </article>
          ))}
        </div>
        {transcript?.error_code && (
          <p className="status-line">Transcript error: {transcript.error_code}</p>
        )}
      </section>

      {translation && (
        <section className="panel translation-panel" aria-label="Vietnamese translation workspace">
          <div className="preview-heading">
            <div>
              <p className="step">07 · Context + Vietnamese review</p>
              <h2>{translation.policy.preset} translation</h2>
            </div>
            <span className={`badge ${translation.status}`}>{translation.status}</span>
          </div>
          <div className="cost-summary">
            <span>Estimated {formatMicros(translation.estimated_cost_micros)}</span>
            <span>Reserved {formatMicros(translation.reserved_cost_micros)}</span>
            <span>Actual {formatMicros(translation.actual_cost_micros)}</span>
          </div>

          {translation.status === "waiting_for_context_review" && contextDraft && (
            <div className="context-review">
              <h3>Story context</h3>
              <label htmlFor="context-summary">Summary</label>
              <textarea
                id="context-summary"
                rows={5}
                value={contextDraft.summary}
                disabled={translationBusy}
                onChange={(event) =>
                  setContextDraft((current) =>
                    current ? { ...current, summary: event.target.value } : current,
                  )
                }
              />
              <div className="entity-list">
                {contextDraft.entities.map((entity, index) => (
                  <div className="entity-row" key={entity.id}>
                    <div>
                      <strong>{entity.source_forms.join(" / ")}</strong>
                      <small>
                        {entity.kind} · {(entity.confidence * 100).toFixed(0)}%
                        {entity.ambiguous ? " · ambiguous" : ""}
                      </small>
                    </div>
                    <input
                      aria-label={`Vietnamese rendering for ${entity.source_forms[0]}`}
                      value={entity.preferred_vietnamese ?? ""}
                      placeholder="Preferred Vietnamese rendering"
                      disabled={translationBusy}
                      onChange={(event) =>
                        setContextDraft((current) =>
                          current
                            ? {
                                ...current,
                                entities: current.entities.map((item, itemIndex) =>
                                  itemIndex === index
                                    ? { ...item, preferred_vietnamese: event.target.value }
                                    : item,
                                ),
                              }
                            : current,
                        )
                      }
                    />
                  </div>
                ))}
              </div>
              <button
                type="button"
                disabled={translationBusy || !contextDraft.summary.trim()}
                onClick={() => void approveContext()}
              >
                Approve context and continue
              </button>
            </div>
          )}

          {translation.findings.length > 0 && (
            <div className="findings">
              <h3>Review findings</h3>
              {translation.findings.map((finding, index) => (
                <p key={`${finding.code}-${finding.segment_id ?? index}`}>
                  <strong>{finding.code}</strong> · {finding.message}
                </p>
              ))}
            </div>
          )}

          <div className="translation-list">
            {translation.segments.map((segment) => (
              <article className="translation-row" key={segment.id}>
                <div className="segment-time">
                  <strong>#{segment.ordinal + 1}</strong>
                  <span>
                    {formatTime(segment.start_us)} → {formatTime(segment.end_us)}
                  </span>
                </div>
                <div className="source-card">
                  <small>Chinese source</small>
                  <p>{segment.source_text}</p>
                </div>
                <div className="translation-edit">
                  <small>Vietnamese</small>
                  <textarea
                    rows={2}
                    value={translationDrafts[segment.id] ?? segment.translation?.text ?? ""}
                    disabled={
                      translation.status !== "waiting_for_review" ||
                      translationBusy ||
                      !segment.translation
                    }
                    onChange={(event) =>
                      setTranslationDrafts((current) => ({
                        ...current,
                        [segment.id]: event.target.value,
                      }))
                    }
                  />
                  {segment.translation && (
                    <button
                      type="button"
                      className="secondary"
                      disabled={
                        translation.status !== "waiting_for_review" ||
                        translationBusy ||
                        !translationDrafts[segment.id]?.trim() ||
                        translationDrafts[segment.id]?.trim() === segment.translation.text
                      }
                      onClick={() => void saveTranslationSegment(segment)}
                    >
                      Save Vietnamese revision
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
          {translation.status === "waiting_for_review" && (
            <button
              type="button"
              className="approve-wide"
              disabled={
                translationBusy || translation.segments.some((segment) => !segment.translation)
              }
              onClick={() => void approveTranslation()}
            >
              Approve Vietnamese translation
            </button>
          )}
          <SubtitleStyleReview
            projectId={translation.project_id}
            mediaAssetId={translation.media_asset_id}
            proxyUrl={media?.proxy_url ?? null}
            segments={translation.segments}
            disabled={translationBusy}
            onMessage={setMessage}
          />
          {translation.error_code && (
            <p className="status-line">Translation error: {translation.error_code}</p>
          )}
        </section>
      )}
    </main>
  );
}
