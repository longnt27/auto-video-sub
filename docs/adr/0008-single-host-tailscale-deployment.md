# ADR-0008: Deploy on one local host through Tailscale

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

The personal MVP should have no recurring hosting, database, object-storage, workflow, authentication, or observability bill. The owner already uses Tailscale and can operate an Apple Silicon machine. Public internet availability and high availability are not requirements.

## Decision

Deploy the modular monolith and its infrastructure as non-root Compose containers on one always-on Apple Silicon Mac using Colima, or a compatible Linux host. Run PostgreSQL, Temporal, Garage, local OCR/TTS/rewrite, FFmpeg, and telemetry locally on persistent volumes. Run Tailscale on the host; use Tailscale Serve for tailnet-only HTTPS and identity headers, bind application ports to loopback/private networks, and keep Funnel disabled. Back up PostgreSQL and Garage to a physically independent encrypted target.

## Consequences

There is no recurring infrastructure/authentication fee for eligible personal Tailscale use, no public ingress, and deployment matches the owner's hardware. The host is a single failure, resource, thermal, and maintenance domain. Sleep, network loss, disk failure, or a broken update causes downtime. The owner is responsible for patches, capacity, backup, restoration, and Tailscale plan eligibility.

Direct signed browser uploads require a dedicated tailnet-only HTTPS listener for the Garage S3 endpoint. Administrative ports stay private. Only the translation worker receives outbound provider credentials/access.

## Alternatives considered

- AWS ECS/RDS/S3 with Temporal Cloud: stronger managed durability and scaling, but recurring cost across multiple services.
- Render/Fly.io/Railway: simple application hosting but still charge for persistent, media-heavy workloads and do not remove managed data/workflow costs.
- Public reverse proxy/port forwarding: avoids Tailscale dependency but expands the attack surface and requires public identity/TLS/rate-limit operations.
- Kubernetes: no present scaling or team requirement justifies it.

## Reversibility and review triggers

Medium. Containers, S3 contracts, PostgreSQL, and provider ports preserve a later move to managed hosting. Reconsider when commercial Tailscale terms apply, more than a few users need access, host downtime is unacceptable, queues exceed one host, backups cannot meet RPO/RTO, or storage/render workloads need separate machines.
