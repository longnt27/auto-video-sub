import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import SubtitleStyleReview from "../app/subtitle-style-review";

describe("subtitle style review", () => {
  it("renders a bounded appearance-review surface before client hydration", () => {
    const html = renderToStaticMarkup(
      <SubtitleStyleReview
        projectId="00000000-0000-0000-0000-000000000001"
        mediaAssetId="00000000-0000-0000-0000-000000000002"
        proxyUrl={null}
        segments={[]}
      />,
    );

    expect(html).toContain("Subtitle appearance");
    expect(html).toContain("Loading approved subtitle style");
  });
});
