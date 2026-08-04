import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import Home from "../app/page";

describe("foundation page", () => {
  it("describes the local-first cost boundary", () => {
    const html = renderToStaticMarkup(<Home />);

    expect(html).toContain("Auto Video Sub");
    expect(html).toContain("Translation is the only paid runtime provider");
    expect(html).toContain("Product workflows begin only after this foundation passes review");
  });
});
