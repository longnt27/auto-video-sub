# Repository instructions

These instructions apply to the entire repository. A more specific `AGENTS.md` may narrow them for a subdirectory but must preserve the safety and domain invariants below.

## Approval gate

Until a human explicitly approves the initial architecture, change only planning documents, ADRs, governance files, and repository-scoped Codex skills. Do not create application source, package manifests, lockfiles, generated boilerplate, migrations, Dockerfiles, CI workflows, or infrastructure. Do not install dependencies or initialize external resources.

After approval, implement only the approved phase and acceptance criteria. Keep speculative work out of scope.

## Required reading

Before technical work, read `README.md`, `docs/product-overview.md`, `docs/architecture.md`, `docs/repository-structure.md`, and the documents relevant to the task. Read accepted ADRs before changing an architectural boundary. For workflows, translation, duration fitting, data, security, or operations, read the corresponding document in `docs/`.

## Invariants

- Keep a modular monolith in one monorepo unless an accepted ADR says otherwise.
- Keep domain logic independent from HTTP, persistence, Temporal, and external providers.
- Keep OCR, cloud LLM, local rewrite LLM, TTS, object storage, and workflow engines behind ports.
- Give every subtitle segment a stable backend-owned ID. Providers may return content keyed by IDs but never own timestamps or metadata.
- Treat translation tone as a versioned server-owned prompt policy. User content cannot supply or override system prompts.
- Treat subtitle appearance as validated structured data. Never execute user-supplied CSS, ASS override tags, FFmpeg fragments, or font paths.
- Store durable media and derived outputs as immutable, versioned object-storage artifacts with checksums and lineage.
- Make stage operations idempotent, bounded by timeouts, cancellable where safe, and retryable at the smallest useful scope.
- Never use container-local disk as the sole copy of a durable artifact.
- Surface uncertain entities and exhausted duration repairs for human review.
- Never expose one user's project or object keys to another user.

## Work safety

- Do not perform feature work directly on the default branch. Use one `dev/<feature-name>` branch per coherent feature, or an isolated worktree on such a branch, after confirming the current branch and worktree state.
- Never use destructive Git commands, overwrite unrelated changes, or discard work that you did not create.
- Do not add or upgrade dependencies without a documented need, alternatives considered, and compatibility/security checks.
- Do not refactor unrelated code while completing a scoped change.
- Understand requirements and acceptance criteria before implementing product behavior; request human review when ambiguity changes observable behavior, data compatibility, security, cost, or vendor commitment.
- Derive commands from checked-in repository files (`README`, task runner, manifests, and CI). Never invent a command or claim it ran.
- Run the smallest relevant checks while iterating and the documented required checks before completion. Report skipped or failed checks honestly with reasons.

## Change discipline

Plan non-trivial work. A branch represents one feature; split that feature into small, logically complete commits rather than one branch-sized commit. Keep commits and diffs reviewable. Every commit subject must use `<type>(<scope>): <message>`, with an allowed type from `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`, or `revert`; a lowercase kebab-case scope; and a concise imperative message that starts lowercase and has no trailing period. Record breaking-change details in the commit body or a `BREAKING CHANGE:` footer without changing the required subject shape. Update architecture, domain, API, operational, and decision documents when their contracts change. New significant decisions require an ADR using `docs/adr/README.md`.

A completion report must summarize behavior, files, tests with exact results, migrations or rollout implications, risks, follow-ups, and items requiring human review. Read `docs/subtitle-styling.md` before changing editor overlay or final subtitle rendering behavior.
