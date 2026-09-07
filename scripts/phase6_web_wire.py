from pathlib import Path

path = Path("apps/web/app/workspace.tsx")
text = path.read_text(encoding="utf-8")

old_import = 'import SubtitleStyleReview from "./subtitle-style-review";\n'
new_import = (
    'import RenderReview from "./render-review";\n'
    'import SpeechReview from "./speech-review";\n'
    'import SubtitleStyleReview from "./subtitle-style-review";\n'
)
if old_import not in text:
    raise SystemExit("workspace import anchor not found")
text = text.replace(old_import, new_import, 1)

old_block = '''          <SubtitleStyleReview
            projectId={translation.project_id}
            mediaAssetId={translation.media_asset_id}
            proxyUrl={media?.proxy_url ?? null}
            segments={translation.segments}
            disabled={translationBusy}
            onMessage={setMessage}
          />
'''
new_block = old_block + '''          {translation.status === "approved" && (
            <>
              <SpeechReview
                projectId={translation.project_id}
                mediaAssetId={translation.media_asset_id}
                disabled={translationBusy}
                onMessage={setMessage}
              />
              <RenderReview
                projectId={translation.project_id}
                mediaAssetId={translation.media_asset_id}
                disabled={translationBusy}
                onMessage={setMessage}
              />
            </>
          )}
'''
if old_block not in text:
    raise SystemExit("workspace subtitle-style anchor not found")
text = text.replace(old_block, new_block, 1)
path.write_text(text, encoding="utf-8")
