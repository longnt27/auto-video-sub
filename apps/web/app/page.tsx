"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

type Project = {
  id: string;
  title: string;
  lifecycle: string;
};

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
  upload: {
    url: string;
    method: string;
    headers: Record<string, string>;
  };
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

const API = "/api/backend/v1";
const ACCEPTED_MEDIA_TYPES = new Set([
  "video/mp4",
  "video/quicktime",
  "video/x-matroska",
  "video/webm",
]);

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

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { cache: "no-store", ...init });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.error?.message ?? "Request failed");
  }
  return payload as T;
}

function formatTime(timeUs: number): string {
  const totalSeconds = timeUs / 1_000_000;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds - minutes * 60;
  return `${minutes}:${seconds.toFixed(2).padStart(5, "0")}`;
}

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [title, setTitle] = useState("");
  const [media, setMedia] = useState<Media | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [transcriptBusy, setTranscriptBusy] = useState(false);
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
    setDrafts(
      Object.fromEntries(next.segments.map((segment) => [segment.id, segment.source.text])),
    );
  }, []);

  useEffect(() => {
    void refreshProjects();
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
    if (!selectedProject) {
      setMessage("Create or select a project first.");
      return;
    }
    setBusy(true);
    setMedia(null);
    setTranscript(null);
    setDrafts({});
    try {
      const contentType = mediaContentType(file);
      setMessage("Creating a scoped upload intent…");
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
      setMessage("Upload sealed. Starting validation and proxy generation…");
      const next = await api<Media>(`/projects/${selectedProject}/uploads/${intent.id}/complete`, {
        method: "POST",
      });
      setMedia(next);
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
      setMessage("Extracting the configured bottom subtitle band and running local OCR…");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Transcript start failed");
    } finally {
      setTranscriptBusy(false);
    }
  }

  async function saveSegment(segment: SubtitleSegment) {
    if (!media) return;
    const text = drafts[segment.id]?.trim();
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
      const next = await api<Transcript>(
        `/projects/${media.project_id}/media/${media.id}/transcript`,
      );
      applyTranscript(next);
      setMessage(`Saved source revision for segment ${segment.ordinal + 1}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Segment save failed");
    } finally {
      setTranscriptBusy(false);
    }
  }

  async function approveTranscript() {
    if (!media || !transcript || transcript.status !== "waiting_for_review") return;
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
      setMessage("Source transcript approved. Phase 4 can consume this exact revision set.");
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
      const next = await api<Transcript>(
        `/projects/${media.project_id}/media/${media.id}/transcript/cancel`,
        { method: "POST" },
      );
      applyTranscript(next);
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
      const next = await api<Transcript>(
        `/projects/${media.project_id}/media/${media.id}/transcript/restart`,
        { method: "POST" },
      );
      applyTranscript(next);
      setMessage("Transcript processing restarted from reusable durable inputs.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Transcript restart failed");
    } finally {
      setTranscriptBusy(false);
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
              Sample the lower subtitle band, run local Chinese OCR, then review stable timestamped
              segments before translation.
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
              <button type="button" disabled={transcriptBusy} onClick={() => void cancelTranscript()}>
                Cancel processing
              </button>
            )}
            {transcript && ["failed", "cancelled"].includes(transcript.status) && (
              <button type="button" disabled={transcriptBusy} onClick={() => void restartTranscript()}>
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
                <track
                  kind="captions"
                  src="/empty.vtt"
                  srcLang="zh"
                  label="Source transcript review"
                />
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
                value={drafts[segment.id] ?? segment.source.text}
                disabled={transcript.status !== "waiting_for_review" || transcriptBusy}
                onChange={(event) =>
                  setDrafts((current) => ({ ...current, [segment.id]: event.target.value }))
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
                  !drafts[segment.id]?.trim() ||
                  drafts[segment.id]?.trim() === segment.source.text
                }
                onClick={() => void saveSegment(segment)}
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
    </main>
  );
}
