# Phase 2 API contract

All product routes are under `/v1`. The browser calls them through the same-origin `/api/backend/v1/...` gateway. JSON objects reject unknown fields. Errors use `{"error":{"code","message","request_id"}}`; raw exceptions and object keys are never returned.

## Identity and mutation rules

- Local development maps requests to `DEV_AUTH_LOGIN` only when tailnet authentication is disabled.
- A tailnet deployment accepts `Tailscale-User-Login` at the web gateway, forwards a normalized internal identity header plus a shared proxy secret, and the API accepts it only from an allowlisted proxy IP.
- Every repository query is scoped by the opaque internal owner ID. Cross-owner object IDs return `404`.
- `POST /v1/projects` and `POST /v1/projects/{project_id}/uploads` require `Idempotency-Key` matching `[A-Za-z0-9_-]{8,128}`. Reuse with a different payload returns `409`.

## Routes

| Method and route | Result |
|---|---|
| `POST /v1/projects` | Creates or returns an idempotent project from `{title}` |
| `GET /v1/projects` | Lists only the current owner's projects |
| `GET /v1/projects/{project_id}` | Returns one owned project |
| `POST /v1/projects/{project_id}/uploads` | Reserves quota and returns a short-lived signed PUT grant |
| `POST /v1/projects/{project_id}/uploads/{intent_id}/complete` | Verifies/seals object metadata and starts idempotent media ingest |
| `GET /v1/projects/{project_id}/media/{media_id}` | Returns current validation/proxy status and a signed proxy URL only when ready |

The browser PUTs bytes directly to the signed storage URL using exactly the returned headers. The signature binds content type and the browser-supplied `Content-Length`; Garage rejects a different length. Completion independently checks stored size/type; the worker then checks magic bytes, FFprobe structure, and configured duration/dimension/frame-rate/stream ceilings. Provider-owned metadata never becomes authoritative without backend validation.

## Phase 2 state projection

Media status is `upload_pending`, `object_received`, `validating`, `proxy_generating`, `ready`, `rejected`, or `failed`. `rejected` is a permanent input/policy result; `failed` is a processing failure eligible for a later explicit scoped-retry API. Phase 2 polling is authoritative and intentionally simple.
