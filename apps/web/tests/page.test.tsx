import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import Home from "../app/page";

describe("phase 2 project workspace", () => {
  it("renders the project, upload, and proxy-review flow", () => {
    const html = renderToStaticMarkup(<Home />);

    expect(html).toContain("Auto Video Sub");
    expect(html).toContain("translation is the only paid provider");
    expect(html).toContain("Choose a Chinese-language video");
    expect(html).toContain("Proxy preview");
  });
});
