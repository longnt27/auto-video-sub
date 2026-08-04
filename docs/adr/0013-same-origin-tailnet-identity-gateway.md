# ADR-0013: Use the web server as the same-origin tailnet identity gateway

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

The browser needs authenticated JSON access and direct signed object transfers through a private Tailscale deployment. Exposing web and API as independent browser origins complicates CORS, identity-header trust, and deployment rules. A caller can spoof Tailscale-looking headers unless the API can distinguish its trusted reverse proxy.

## Decision

Expose the Next.js web server as the single browser application origin. Route `/api/backend/v1/...` through a small server-side gateway that accepts the Tailscale Serve identity header, forwards only reviewed headers, and adds a private `X-Internal-Proxy-Secret`. Keep the FastAPI listener on loopback/private container networking. FastAPI accepts forwarded identity only when both the immediate source IP is allowlisted and the proxy secret matches, then maps the normalized login to an opaque internal user ID and exact login allowlist.

Continue to expose the Garage S3 data endpoint through a separate tailnet-only HTTPS listener because large media bytes must not traverse Next.js or FastAPI. Signed URLs remain short-lived and scoped; Garage administrative endpoints remain private.

## Consequences

Browser JSON is same-origin, identity trust has one explicit gateway, and large uploads stay direct. The web server becomes security-sensitive and the internal secret must be independently generated, mounted, rotated, and kept out of client bundles. Proxy-IP configuration must match the actual container topology; a misconfiguration fails closed. Path and header allowlists require tests.

## Alternatives considered

- Route Serve directly to FastAPI under `/api`: viable, but makes proxy-source validation and a single browser origin more deployment-specific and splits ingress behavior across two backends.
- Trust `Tailscale-User-Login` from any caller: rejected because direct/spoofed requests could select another identity.
- Add OIDC/session infrastructure now: stronger for multi-user/public deployments, but unnecessary operating surface for the single-owner tailnet MVP.
- Proxy video uploads through Next.js/FastAPI: rejected because it wastes memory/bandwidth and violates the direct object-storage upload principle.

## Reversibility and review triggers

Medium. API authorization remains based on opaque internal user IDs, so an OIDC/session gateway can replace this edge without changing project ownership. Reconsider for public ingress, collaboration, non-Tailscale clients, multiple ingress replicas, or inability to secure/rotate the private proxy credential.
