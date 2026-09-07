import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import RenderReview from "../app/render-review";

describe("render review", () => {
  it("requires an original-audio choice before final rendering", () => {
    const html = renderToStaticMarkup(
      <RenderReview
        projectId="00000000-0000-0000-0000-000000000001"
        mediaAssetId="00000000-0000-0000-0000-000000000002"
      />,
    );

    expect(html).toContain("Render + export");
    expect(html).toContain("Choose before rendering");
    expect(html).toContain("Reduce under Vietnamese speech");
    expect(html).toContain("Retain at full level");
    expect(html).toContain("Remove original audio");
    expect(html).toContain("Render final video");
  });
});
