# ADR-0014: Use GitHub Actions and GHCR for continuous delivery

- Status: Accepted
- Date: 2026-08-04
- Owners: project maintainers

## Context

The public GitHub repository needs cost-controlled CI/CD while production remains an owner-operated Mac reachable only through Tailscale. Pull-request code is untrusted. A persistent self-hosted GitHub Actions runner on the production host would give workflow code access to the host, its durable data, and its tailnet. Direct deployment also depends on production secrets, backups, Tailscale Serve rules, and rollback procedures that are not approved yet.

## Decision

Run deterministic CI on isolated standard GitHub-hosted Linux runners. On a push to protected `main`, publish the API, web, and worker images only after Python, web, integration, and Compose gates succeed. Publish OCI images to GHCR for both `linux/amd64` and `linux/arm64`, tagged with the full source commit SHA plus a movable `main` convenience tag. Include BuildKit provenance and an SBOM; ordinary workflows never call the paid translation provider.

Treat publication as continuous delivery, not unattended production deployment. Do not register the production Mac as a repository self-hosted runner. The host will later pull an explicitly selected SHA image after an operator-approved backup, migration, health-check, and rollback procedure is implemented. Deployments must pin the SHA tag or digest, never the movable `main` tag.

## Consequences

Every delivered application image is traceable to a main-branch commit that passed the defined gates, and both target architectures are available without exposing the local host to pull-request execution. Public-repository standard Actions runners and public GHCR packages currently have no usage charge, but GitHub may change that policy; billing alerts and package visibility still require owner verification.

The pipeline does not yet deploy the local production stack. This is intentional: production Compose overrides, real secret injection, backup/restore, Tailscale exposure, and rollback automation remain gated. Multi-architecture builds take longer than native-only builds and QEMU does not replace smoke tests on the actual Apple Silicon host.

## Alternatives considered

- Persistent self-hosted runner on the Mac: rejected for the public repository because workflow code would execute inside the production trust boundary.
- GitHub-hosted runner joining the tailnet and deploying over SSH: deferred until production host commands, Tailscale ACLs, secrets, backups, and rollback are approved; safer than a persistent runner but still expands the deployment credential boundary.
- Build directly on the host from Git: free and simple, but lacks a reviewed immutable delivery artifact and couples deployment to toolchains on the host.
- Docker Hub: workable, but GHCR provides repository-linked permissions and delivery with the existing GitHub token.

## Reversibility and review triggers

Easy to medium. OCI images and Compose keep the registry replaceable. Reconsider when the repository becomes private, GitHub pricing changes, package visibility cannot remain public, image size exceeds practical limits, or production deployment automation has an approved threat model and rollback design.
