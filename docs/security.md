# Security design

## Trust boundaries and threat model

Untrusted inputs include browsers, uploaded files, filenames, object metadata, media containers/codecs, provider responses, webhook/callback payloads, and user-authored subtitle text. API, workers, database, object storage, and external providers are separate trust boundaries. Media parsing and FFmpeg are high-risk workloads.

Primary threats are cross-tenant access, signed URL abuse, resource-exhaustion uploads, media parser exploits, prompt/provider data leakage, injection into logs or commands, stolen credentials, and incomplete deletion.

## Identity and authorization

- Expose the application only through Tailscale Serve with HTTPS enabled and Funnel disabled. Tailnet grants/ACLs restrict which users can reach the listeners.
- Use Serve's injected `Tailscale-User-Login` header for the single-owner MVP, compare it to an explicit allowlist, and map it to an opaque internal user ID. Email/login is an external identity mapping, never the project authorization key.
- Route browser JSON through the web application's same-origin gateway. It copies only an allowlisted set of headers, translates the Tailscale login to an internal header, and authenticates its private hop with a distinct shared proxy secret.
- The API trusts that identity only when both the source IP belongs to an allowlisted web-proxy IP/CIDR and the proxy secret matches. It refuses to start tailnet authentication with an empty allowlist, empty proxy range, or default/short secret. API and web containers otherwise bind to loopback/private networks; the browser cannot select an internal owner ID.
- Require project ownership in every project, revision, workflow, review, artifact, and signed URL query. Never authorize from an object key supplied by a client.
- Use opaque IDs and deny by default. If multiple users or conventional sessions are needed, adopt Tailscale `tsidp` OIDC or another reviewed identity provider rather than extending header logic ad hoc.
- Protect state-changing endpoints with same-site cookies/CSRF defenses where browser sessions are introduced.

## Secure upload and download

1. Authenticate, authorize, check quota, and create a short-lived upload intent with an opaque server-generated key.
2. Constrain expected byte size and supported content type where the storage signing mechanism permits it.
3. After upload, compare declared size/type with object metadata, fetch a bounded prefix for magic-byte detection, and run isolated ffprobe validation.
4. Reject MIME/magic mismatch, malformed containers, unsupported codecs, excessive duration, extreme dimensions/frame rate/stream count, decompression/resource bombs, or missing required streams.
5. Do not trust filenames; store display names separately and sanitize them for response headers.
6. Issue short-lived signed downloads only after ownership and artifact-state checks. Use attachment headers and least-privilege object permissions.

Object storage is private, host and backup disks are encrypted at rest, and public ACLs are blocked. Browser CORS permits only approved origins and methods.

The S3-compatible data endpoint may be exposed on a dedicated Tailscale HTTPS port solely for short-lived signed uploads/downloads. Garage administrative/RPC/metrics ports remain loopback/container-private. A tailnet identity does not replace signature, project ownership, expiry, size, or content validation.

## Media isolation

Run FFmpeg/ffprobe as a non-root process in a minimal, patched container with read-only root filesystem where practical, no cloud metadata access, no inbound network, restricted outbound network, dropped Linux capabilities, seccomp/AppArmor profile, bounded CPU/memory/processes/temp disk, and hard timeouts. Pass arguments as an array without a shell. Use unique temp directories and never interpolate filenames into commands.

Separate media worker credentials from API and AI worker credentials. Media workers can access only scoped input/output prefixes needed for activities. Treat crashes and resource-limit exits as structured failures.

## Limits and abuse prevention

Enforce upload byte size, media duration, dimensions, frame rate, streams, project count, concurrent workflows, daily/monthly processing units, provider spend, and signed-URL creation rate. Reserve quota before admission and reconcile actual cost. Apply per-user/API rate limits and global backpressure; return actionable retry information without exposing internal capacity.

Phase 2 uses configurable provisional ceilings of 2 GiB per upload, three hours, 3840×2160, 60 fps, and 16 streams, plus ten projects, one active upload, and 4 GiB stored bytes per user in local Compose. These are conservative development admission limits, not production capacity claims; production promotion still requires benchmark and policy approval.

## Secrets and credentials

Local deployment secrets live outside the repository in owner-readable files with restrictive permissions or an OS keychain/age-encrypted store and are mounted/injected at runtime. Never place secrets in Git, images, client bundles, Compose files, logs, traces, artifacts, or Temporal search attributes. Rotate the translation key and Garage credentials, and give each process separate least-privilege storage/database credentials.

## Provider and model safety

Send providers only required transcript/context. Provider output is untrusted data and passes strict schemas and domain validation. Prompts cannot grant access to tools, storage, or secrets. Document provider data retention/training controls. Redact authorization headers, signed URLs, raw tokens, and sensitive subtitle content from normal logs.

At runtime, only the dedicated translation worker profile receives the LLM credential and outbound access to the approved provider endpoint. Its paid calls cover global context extraction, translation batches, and optional consistency proposals. OCR, VieNeu-TTS, llama.cpp, media workers, database, Temporal, Garage, and telemetry remain local. Container image/model acquisition and security updates are controlled maintenance operations, not implicit runtime dependencies.

Translation tone is chosen from server-owned preset IDs. Prompt templates, shared fidelity rules, and provider instructions are not editable fields. Transcript text, glossary notes, and other user content are delimited and passed only as data; they cannot select models, tools, URLs, or system instructions. Tone changes require normal project authorization, optimistic concurrency, quota reservation, and explicit confirmation before paid work.

Subtitle styles are typed and allowlisted. Reject raw CSS, HTML, ASS headers/override tags, FFmpeg/filter fragments, font paths, remote font URLs, and unknown fields. Escape subtitle text for both HTML and generated ASS contexts. Fonts are read-only, checksummed release assets from a license-reviewed catalog; arbitrary font uploads remain disabled. Renderer processes receive only backend-generated subtitle documents and resolved asset paths.

The MVP uses only a reviewed built-in VieNeu-TTS preset voice. Voice cloning, user-supplied reference audio, and arbitrary voice embeddings remain disabled. Before promotion, record the exact code/model revisions, checksums, complete license chain, preset-voice provenance, and intended-use review; an Apache-2.0 label does not itself prove rights in every training sample or voice identity. Model files are controlled executable inputs: acquire them during an explicit maintenance step, verify checksums, prefer safe tensor/ONNX formats, and never allow a project upload to select or replace a runtime model path.

## Supply chain and containers

Pin direct tool/runtime versions and lock transitive dependencies. Current CI runs deterministic formatting, lint, type, unit/media, PostgreSQL/Garage integration, migration, and web-build checks plus monthly dependency update proposals; secret, license, static-analysis, and container vulnerability scanning must be added before the pilot. Generate an SBOM for release images, sign images/artifacts where supported, use reviewed base images, and rebuild for security patches. Run containers as non-root and support amd64/arm64 where dependencies permit; document exceptions.

## Retention, deletion, and incident handling

Assign retention classes to originals, intermediates, provider envelopes, logs, and final outputs. Project deletion immediately revokes API/download access, records a tombstone, cancels work, then purges objects and metadata through an auditable workflow subject to legal/backup policy. Lifecycle rules are a safety net, not the only deletion mechanism.

Temporary files and abandoned multipart uploads have sweepers and maximum age. Logs use bounded retention and redaction. Security reports follow [SECURITY.md](../SECURITY.md); suspected cross-tenant access or credential leakage requires incident escalation and credential/URL revocation.

Phase 2 expires stale pending intents and releases their database quota reservation when the owner next requests an upload. A scheduled staging-object sweeper and user-facing deletion workflow are still required before production; until then, abandoned staging bytes may remain in Garage even though they are never authorized as artifacts.

Encrypted backups must leave the physical deployment host. Protect backup credentials separately, test restoration, and document that deletion from the live project may persist in backups until the declared expiry window.
