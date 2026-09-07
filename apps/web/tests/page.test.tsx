import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import Home from "../app/page";

describe("phase 3 source transcript workspace", () => {
  it("renders upload, proxy, extraction, and transcript review surfaces", () => {
    const html = renderToStaticMarkup(<Home />);

    expect(html).toContain("Auto Video Sub");
    expect(html).toContain("translation is the only paid provider");
    expect(html).toContain("Choose a Chinese-language video");
    expect(html).toContain("Proxy preview");
    expect(html).toContain("Source transcript");
    expect(html).toContain("Extract transcript");
    expect(html).toContain("Chinese source transcript");
    expect(html).toContain("Save correction");
  });
});
