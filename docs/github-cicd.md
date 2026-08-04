# GitHub CI/CD

## Delivery boundary

The public repository uses one `CI/CD` workflow. Pull requests run deterministic quality gates on isolated GitHub-hosted runners. A push to protected `main` publishes API, web, and worker images only after every gate succeeds. It does not contact the paid translation provider and does not connect to the production tailnet.

Published image names are:

- `ghcr.io/longnt27/auto_video_sub-api`;
- `ghcr.io/longnt27/auto_video_sub-web`;
- `ghcr.io/longnt27/auto_video_sub-worker`.

Each successful main commit produces `linux/amd64` and `linux/arm64` manifests. `sha-<full-commit-sha>` is the immutable deployment selector; `main` is only a convenience pointer. Builds include OCI source/revision labels, BuildKit provenance, and an SBOM.

## Required GitHub settings

The repository owner must configure these settings in GitHub before treating delivery as protected:

1. Protect `main`; require a pull request and the `Python quality`, `Web quality`, and `Compose definition` checks.
2. Disallow force pushes and branch deletion on `main`; require conversation resolution.
3. Keep workflow token permissions read-only by default. The publish matrix receives only `contents: read` and `packages: write` at job scope.
4. Permit the reviewed actions used in `.github/workflows/ci.yml`; Dependabot reviews their updates monthly.
5. After the first publication, verify all three GHCR packages inherit public repository visibility and anonymous pull access.
6. Set GitHub Actions/package budgets to zero or blocking alerts if repository visibility or GitHub pricing changes.

Do not enable `pull_request_target` for build/test code. Do not attach a persistent repository self-hosted runner to the production Mac. GitHub warns that public pull-request workflows can compromise such a runner and its surrounding network.

## Local production promotion

Image publication is continuous delivery, not automatic deployment. Until the production deployment gate is approved, promotion is an operator action:

1. select the exact reviewed `sha-<full-commit-sha>` image set;
2. confirm all three images resolve for `linux/arm64` and record their digests;
3. back up PostgreSQL, Garage metadata/data, and production configuration;
4. verify free disk, Tailscale Serve state, secrets, and the rollback image digests;
5. run the separately reviewed production Compose migration and replacement procedure;
6. run health, signed-object, identity, and synthetic workflow checks;
7. roll back application images—not the database—if validation fails and migrations remain backward compatible.

The production Compose override and remote deployment workflow must not be invented from the development topology. They require explicit approval after host runtime, volume paths, secrets, backup destination, and Tailscale listeners are chosen.

## Cost and retention

At the time of ADR-0014, standard GitHub-hosted runners are free for public repositories, self-hosted runner execution has no GitHub Actions charge, and public GHCR packages are free. The owner still pays for hardware, power, storage, network, and operator time. Avoid uploading redundant Actions artifacts; BuildKit caches are disposable and may be evicted.

If the repository becomes private, hosted-runner minutes and package storage/transfer move onto plan quotas. Re-evaluate the workflow before changing visibility rather than silently accepting charges.
