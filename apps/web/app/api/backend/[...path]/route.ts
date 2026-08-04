import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ path: string[] }> };

async function forward(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  if (path[0] !== "v1" || path.some((segment) => !/^[A-Za-z0-9_-]+$/.test(segment))) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  const apiBase = process.env.API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000";
  const target = new URL(`/${path.join("/")}`, apiBase);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  for (const name of ["content-type", "idempotency-key", "x-request-id"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const tailscaleLogin = request.headers.get("tailscale-user-login");
  if (tailscaleLogin) headers.set("x-forwarded-tailscale-user-login", tailscaleLogin);
  headers.set(
    "x-internal-proxy-secret",
    process.env.INTERNAL_PROXY_SECRET ?? "local-development-proxy-secret",
  );

  const body =
    request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();
  const response = await fetch(target, {
    method: request.method,
    headers,
    body,
    cache: "no-store",
    redirect: "manual",
  });
  const outboundHeaders = new Headers();
  for (const name of ["content-type", "x-request-id"]) {
    const value = response.headers.get(name);
    if (value) outboundHeaders.set(name, value);
  }
  return new NextResponse(response.body, {
    status: response.status,
    headers: outboundHeaders,
  });
}

export const GET = forward;
export const POST = forward;
