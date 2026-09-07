import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import Home from "../app/page";

describe("phase 4 localization workspace", () => {
  it("renders upload, transcript review, and paid translation controls", () => {
    const html = renderToStaticMarkup(<Home />);

    expect(html).toContain("Auto Video Sub");
    expect(html).toContain("translation is the only paid provider");
    expect(html).toContain("Choose a Chinese-language video");
    expect(html).toContain("Proxy preview");
    expect(html).toContain("Source transcript");
    expect(html).toContain("Extract transcript");
    expect(html).toContain("Chinese source transcript");
    expect(html).toContain("every correction creates a new immutable revision");
    expect(html).toContain("06 · Translation");
    expect(html).toContain("Estimate translation");
    expect(html).toContain("explicit confirmation");
  });
});
