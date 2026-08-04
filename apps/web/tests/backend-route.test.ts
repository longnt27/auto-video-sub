import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { POST } from "../app/api/backend/[...path]/route";

afterEach(() => {
  vi.unstubAllGlobals();
  delete process.env.API_INTERNAL_BASE_URL;
  delete process.env.INTERNAL_PROXY_SECRET;
});

describe("same-origin API gateway", () => {
  it("forwards only allowlisted headers and adds trusted identity credentials", async () => {
    process.env.API_INTERNAL_BASE_URL = "http://api.internal:8000";
    process.env.INTERNAL_PROXY_SECRET = "private-proxy-secret";
    const backend = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "project" }), {
        status: 201,
        headers: { "content-type": "application/json", "x-request-id": "request-1" },
      }),
    );
    vi.stubGlobal("fetch", backend);
    const request = new NextRequest("http://local.test/api/backend/v1/projects", {
      method: "POST",
      headers: {
        authorization: "Bearer must-not-forward",
        "content-type": "application/json",
        "idempotency-key": "project-0001",
        "tailscale-user-login": "owner@example.com",
      },
      body: JSON.stringify({ title: "Project" }),
    });

    const response = await POST(request, {
      params: Promise.resolve({ path: ["v1", "projects"] }),
    });

    expect(response.status).toBe(201);
    expect(backend).toHaveBeenCalledOnce();
    const [target, init] = backend.mock.calls[0] as [URL, RequestInit];
    expect(target.toString()).toBe("http://api.internal:8000/v1/projects");
    const headers = new Headers(init.headers);
    expect(headers.get("authorization")).toBeNull();
    expect(headers.get("idempotency-key")).toBe("project-0001");
    expect(headers.get("x-forwarded-tailscale-user-login")).toBe("owner@example.com");
    expect(headers.get("x-internal-proxy-secret")).toBe("private-proxy-secret");
  });

  it("rejects paths outside the versioned product API", async () => {
    const backend = vi.fn();
    vi.stubGlobal("fetch", backend);
    const response = await POST(
      new NextRequest("http://local.test/api/backend/health", { method: "POST", body: "{}" }),
      { params: Promise.resolve({ path: ["health"] }) },
    );

    expect(response.status).toBe(404);
    expect(backend).not.toHaveBeenCalled();
  });

  it("rejects path-normalization segments before constructing the backend URL", async () => {
    const backend = vi.fn();
    vi.stubGlobal("fetch", backend);
    const response = await POST(
      new NextRequest("http://local.test/api/backend/v1/../health", {
        method: "POST",
        body: "{}",
      }),
      { params: Promise.resolve({ path: ["v1", "..", "health"] }) },
    );

    expect(response.status).toBe(404);
    expect(backend).not.toHaveBeenCalled();
  });
});
