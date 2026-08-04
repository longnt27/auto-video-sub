# Development workflow

## Current implementation phase

The owner approved the initial architecture on 2026-08-04. Phase 1 implementation is complete and awaiting its owner review gate. Do not implement Phase 2 product behavior until that exit evidence is accepted. Later unresolved choices in `docs/open-decisions.md` gate their affected phase rather than the skeleton.

## Future change workflow

1. Inspect repository status, current branch/worktrees, governing `AGENTS.md`, relevant docs/ADRs, and actual manifests/task runner.
2. Confirm requirements, acceptance criteria, security/operational impact, and whether an ADR or migration is required.
3. Create a task branch or isolated worktree; do not implement features on the default branch.
4. Write a concise plan with tests and rollout/rollback implications.
5. Implement the smallest coherent change through the defined module boundaries.
6. Run repository-defined formatting, lint, type, unit, integration, and task-specific checks. Never invent commands; discover them from checked-in files.
7. Review the complete diff for unrelated changes, secrets, generated files, compatibility, observability, and documentation.
8. Report changes, exact test outcomes, skipped tests/reasons, risks, migration/deployment notes, and human-review items.

## Branch and worktree safety

The default branch is protected. Never force-push it or do direct feature work there. Do not use `git reset --hard`, destructive clean/checkout operations, or delete branches/worktrees without explicit approval and verified targets. Treat pre-existing changes as belonging to someone else. Stop and ask if they overlap the intended edit and cannot be preserved.

## Decision and dependency discipline

Create an ADR for choices that alter persistence, public contracts, process/deployment boundaries, workflow semantics, security boundaries, or difficult-to-reverse providers. Dependency additions require a concrete need, maintenance/security/license review, viable alternatives, size/runtime impact, and architecture fit. Regenerate and review both lockfiles whenever approved dependency constraints change.

## Database and workflow compatibility

Schema changes use expand/migrate/contract and support the currently deployed application during rollout. Temporal workflow code must remain replay-compatible for open histories; use versioning/patch mechanisms and replay tests. Provider/prompt/model changes create new versions and canary/evaluation evidence rather than overwriting history.

## Definition of done

A change is done when acceptance criteria are met; affected tests pass; errors, telemetry, authorization, idempotency, and cancellation are considered; docs/contracts are updated; rollout and rollback are safe; no unrelated changes remain; and required human decisions are explicit.

## Supported tools and commands

Phase 1 pins Node.js in `.nvmrc`, Python in `.python-version`, pnpm in `package.json`, and uv in CI/container definitions. `uv.lock` and `pnpm-lock.yaml` are the reproducibility boundary. Do not hand-edit lockfiles.

From a clean checkout:

```sh
cp .env.example .env
make bootstrap
make check
make stack-config
make stack-up
make stack-smoke
```

`make format`, `make format-check`, `make lint`, `make typecheck`, `make test`, and `make build` are the supported quality commands. `make stack-smoke` verifies both HTTP endpoints after startup. `make web`, `make api`, and `make worker` run individual composition roots. `make stack-down` stops the local stack without deleting volumes. The disk preflight requires 6 GiB free before a stack start; model assets in later phases will require a separately measured and substantially larger allowance.

The Python environment uses `.cache/uv` by default through the `Makefile`; CI uses the runner cache. pnpm permits lifecycle scripts only for the explicitly reviewed `sharp` package. Adding another build script requires source and purpose review plus an explicit `allowBuilds` entry.

All default checks are deterministic and local. `RUN_TRANSLATION_LLM_SMOKE` stays `0`; no ordinary setup, test, build, or CI command may invoke the paid provider.
