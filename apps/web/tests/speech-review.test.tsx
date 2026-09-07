import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import SpeechReview from "../app/speech-review";

describe("speech review", () => {
  it("renders the local speech start surface before client hydration", () => {
    const html = renderToStaticMarkup(
      <SpeechReview
        projectId="00000000-0000-0000-0000-000000000001"
        mediaAssetId="00000000-0000-0000-0000-000000000002"
      />,
    );

    expect(html).toContain("Vietnamese speech");
    expect(html).toContain("Start Vietnamese speech");
    expect(html).toContain("local-AI");
  });
});
