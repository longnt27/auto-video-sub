"use client";

import { useEffect, useMemo, useState } from "react";

type TranslationSegment = {
  id: string;
  start_us: number;
  end_us: number;
  translation: { text: string } | null;
};

type SubtitleFont = {
  id: string;
  family: string;
  license: string;
};

type SubtitleStyle = {
  id: string;
  project_id: string;
  media_asset_id: string;
  version: number;
  font_id: string;
  font_family: string;
  font_license: string;
  font_size_pct: number;
  text_color: string;
  outline_color: string;
  background_color: string;
  background_opacity_pct: number;
  outline_px: number;
  shadow_px: number;
  alignment: "center";
  parent_version_id: string | null;
  created_by: string;
  created_at: string;
};

type Draft = Pick<
  SubtitleStyle,
  | "font_id"
  | "font_size_pct"
  | "text_color"
  | "outline_color"
  | "background_color"
  | "background_opacity_pct"
  | "outline_px"
  | "shadow_px"
  | "alignment"
>;

type Props = {
  projectId: string;
  mediaAssetId: string;
  proxyUrl: string | null;
  segments: TranslationSegment[];
  disabled?: boolean;
  onMessage?: (message: string) => void;
};

const API = "/api/backend/v1";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { cache: "no-store", ...init });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? "Request failed");
  return payload as T;
}

function rgba(hex: string, opacityPct: number): string {
  const normalized = hex.replace("#", "");
  const red = Number.parseInt(normalized.slice(0, 2), 16);
  const green = Number.parseInt(normalized.slice(2, 4), 16);
  const blue = Number.parseInt(normalized.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${opacityPct / 100})`;
}

function draftFromStyle(style: SubtitleStyle): Draft {
  return {
    font_id: style.font_id,
    font_size_pct: style.font_size_pct,
    text_color: style.text_color,
    outline_color: style.outline_color,
    background_color: style.background_color,
    background_opacity_pct: style.background_opacity_pct,
    outline_px: style.outline_px,
    shadow_px: style.shadow_px,
    alignment: style.alignment,
  };
}

export default function SubtitleStyleReview({
  projectId,
  mediaAssetId,
  proxyUrl,
  segments,
  disabled = false,
  onMessage,
}: Props) {
  const [fonts, setFonts] = useState<SubtitleFont[]>([]);
  const [style, setStyle] = useState<SubtitleStyle | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [currentTimeUs, setCurrentTimeUs] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      api<SubtitleFont[]>("/subtitle-styles/fonts"),
      api<SubtitleStyle>(`/projects/${projectId}/media/${mediaAssetId}/subtitle-style`),
    ])
      .then(([nextFonts, nextStyle]) => {
        if (cancelled) return;
        setFonts(nextFonts);
        setStyle(nextStyle);
        setDraft(draftFromStyle(nextStyle));
        setError(null);
      })
      .catch((reason) => {
        if (cancelled) return;
        setError(reason instanceof Error ? reason.message : "Could not load subtitle style");
      });
    return () => {
      cancelled = true;
    };
  }, [mediaAssetId, projectId]);

  const activeText = useMemo(() => {
    const active = segments.find(
      (segment) => currentTimeUs >= segment.start_us && currentTimeUs < segment.end_us,
    );
    return active?.translation?.text ?? "";
  }, [currentTimeUs, segments]);

  const selectedFont = fonts.find((font) => font.id === draft?.font_id);
  const dirty = Boolean(
    style && draft && JSON.stringify(draft) !== JSON.stringify(draftFromStyle(style)),
  );

  async function save() {
    if (!style || !draft || !dirty) return;
    setBusy(true);
    try {
      const next = await api<SubtitleStyle>(
        `/projects/${projectId}/media/${mediaAssetId}/subtitle-style/revisions`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ expected_version: style.version, ...draft }),
        },
      );
      setStyle(next);
      setDraft(draftFromStyle(next));
      setError(null);
      onMessage?.(`Subtitle style v${next.version} saved without translation or render work.`);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Subtitle style save failed";
      setError(message);
      onMessage?.(message);
    } finally {
      setBusy(false);
    }
  }

  if (!draft || !style) {
    return (
      <section aria-label="Subtitle appearance preview" style={{ marginTop: "1rem" }}>
        <h3>Subtitle appearance</h3>
        <p className="control-copy">{error ?? "Loading approved subtitle style…"}</p>
      </section>
    );
  }

  const outline = draft.outline_px;
  const shadow = draft.shadow_px;
  const textShadow = [
    `${outline}px 0 0 ${draft.outline_color}`,
    `${-outline}px 0 0 ${draft.outline_color}`,
    `0 ${outline}px 0 ${draft.outline_color}`,
    `0 ${-outline}px 0 ${draft.outline_color}`,
    `${shadow}px ${shadow}px ${Math.max(1, shadow)}px rgba(0, 0, 0, 0.75)`,
  ].join(", ");

  return (
    <section aria-label="Subtitle appearance preview" style={{ marginTop: "1.25rem" }}>
      <div className="preview-heading">
        <div>
          <p className="step">08 · Subtitle appearance</p>
          <h3>Versioned HTML overlay preview</h3>
        </div>
        <span className="badge approved">style v{style.version}</span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(20rem, 1.4fr) minmax(18rem, 0.8fr)",
          gap: "1rem",
        }}
      >
        <div
          style={{
            position: "relative",
            overflow: "hidden",
            border: "1px solid var(--line)",
            borderRadius: "0.85rem",
            background: "#020506",
            minHeight: "18rem",
          }}
        >
          {proxyUrl ? (
            <video
              src={proxyUrl}
              controls
              preload="metadata"
              onTimeUpdate={(event) =>
                setCurrentTimeUs(Math.round(event.currentTarget.currentTime * 1_000_000))
              }
              style={{ width: "100%", display: "block" }}
            >
              <track
                kind="captions"
                src="/empty.vtt"
                srcLang="vi"
                label="Vietnamese subtitle preview"
              />
            </video>
          ) : (
            <p className="empty-copy" style={{ padding: "2rem" }}>
              Proxy preview is unavailable.
            </p>
          )}
          {activeText && (
            <div
              aria-live="polite"
              style={{
                position: "absolute",
                left: "5%",
                right: "5%",
                bottom: "7%",
                display: "flex",
                justifyContent: "center",
                pointerEvents: "none",
                textAlign: "center",
              }}
            >
              <span
                style={{
                  maxWidth: "90%",
                  padding: draft.background_opacity_pct > 0 ? "0.18em 0.42em 0.24em" : undefined,
                  borderRadius: draft.background_opacity_pct > 0 ? "0.2em" : undefined,
                  background: rgba(draft.background_color, draft.background_opacity_pct),
                  color: draft.text_color,
                  fontFamily: `"${selectedFont?.family ?? style.font_family}", sans-serif`,
                  fontSize: `clamp(16px, ${draft.font_size_pct}vh, 48px)`,
                  fontWeight: 700,
                  lineHeight: 1.22,
                  textShadow,
                  whiteSpace: "pre-wrap",
                }}
              >
                {activeText}
              </span>
            </div>
          )}
        </div>

        <div className="cost-box" style={{ alignContent: "start" }}>
          <label htmlFor="subtitle-font">Approved font</label>
          <select
            id="subtitle-font"
            value={draft.font_id}
            disabled={disabled || busy}
            onChange={(event) =>
              setDraft((current) => current && { ...current, font_id: event.target.value })
            }
          >
            {fonts.map((font) => (
              <option key={font.id} value={font.id}>
                {font.family} · {font.license}
              </option>
            ))}
          </select>

          <label htmlFor="subtitle-size">
            Font size · {draft.font_size_pct.toFixed(1)}% height
          </label>
          <input
            id="subtitle-size"
            type="range"
            min="3"
            max="8"
            step="0.25"
            value={draft.font_size_pct}
            disabled={disabled || busy}
            onChange={(event) =>
              setDraft((current) =>
                current ? { ...current, font_size_pct: Number(event.target.value) } : current,
              )
            }
          />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
            <label>
              Text
              <input
                type="color"
                value={draft.text_color}
                disabled={disabled || busy}
                onChange={(event) =>
                  setDraft((current) => current && { ...current, text_color: event.target.value })
                }
              />
            </label>
            <label>
              Outline
              <input
                type="color"
                value={draft.outline_color}
                disabled={disabled || busy}
                onChange={(event) =>
                  setDraft(
                    (current) => current && { ...current, outline_color: event.target.value },
                  )
                }
              />
            </label>
            <label>
              Background
              <input
                type="color"
                value={draft.background_color}
                disabled={disabled || busy}
                onChange={(event) =>
                  setDraft(
                    (current) => current && { ...current, background_color: event.target.value },
                  )
                }
              />
            </label>
          </div>

          <label htmlFor="subtitle-bg-opacity">
            Background opacity · {draft.background_opacity_pct}%
          </label>
          <input
            id="subtitle-bg-opacity"
            type="range"
            min="0"
            max="90"
            step="5"
            value={draft.background_opacity_pct}
            disabled={disabled || busy}
            onChange={(event) =>
              setDraft((current) =>
                current
                  ? { ...current, background_opacity_pct: Number(event.target.value) }
                  : current,
              )
            }
          />

          <label htmlFor="subtitle-outline">Outline · {draft.outline_px.toFixed(1)}px</label>
          <input
            id="subtitle-outline"
            type="range"
            min="0"
            max="4"
            step="0.5"
            value={draft.outline_px}
            disabled={disabled || busy}
            onChange={(event) =>
              setDraft((current) =>
                current ? { ...current, outline_px: Number(event.target.value) } : current,
              )
            }
          />

          <label htmlFor="subtitle-shadow">Shadow · {draft.shadow_px.toFixed(1)}px</label>
          <input
            id="subtitle-shadow"
            type="range"
            min="0"
            max="4"
            step="0.5"
            value={draft.shadow_px}
            disabled={disabled || busy}
            onChange={(event) =>
              setDraft((current) =>
                current ? { ...current, shadow_px: Number(event.target.value) } : current,
              )
            }
          />

          <small>
            Center alignment only in MVP. HTML preview and Phase 6 ASS/libass render consume the
            same structured style version; saving here never calls translation or FFmpeg.
          </small>
          <button type="button" disabled={disabled || busy || !dirty} onClick={() => void save()}>
            Save subtitle style revision
          </button>
          {error && <p className="status-line">{error}</p>}
        </div>
      </div>
    </section>
  );
}
