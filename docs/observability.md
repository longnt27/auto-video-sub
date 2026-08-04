# Observability

## Goals

Operators must be able to answer: what is happening, why is it waiting or failing, what did it cost, which inputs produced an artifact, and whether users/queues are being treated fairly. Product-visible job history is durable in PostgreSQL; telemetry is diagnostic and may have shorter retention.

## Correlation context

Propagate structured fields where applicable:

`request_id`, `user_id` (internal opaque ID), `project_id`, `workflow_id`, `stage_execution_id`, `artifact_id`, `attempt`, `worker_id`, `task_queue`, `provider`, `model`, `prompt_version`, `translation_policy_version_id`, `tone_preset_id`, `subtitle_style_version_id`, `code_version`, and `environment`.

Do not put subtitle text, tokens, signed URLs, provider keys, raw filenames, or high-cardinality payloads in normal logs or metric labels. IDs may be restricted from metrics labels and retained in traces/logs only.

## Logs, traces, and history

- Emit JSON logs with timestamp, severity, event name, correlation fields, duration, outcome, retryability, and structured error code.
- Instrument HTTP, database, object storage, provider calls, workflow/activity execution, and FFmpeg spans with OpenTelemetry.
- Propagate trace context through Temporal headers while accepting that replay requires deterministic instrumentation behavior.
- Persist workflow/stage attempts and artifact lineage independently of log availability.
- Store redacted raw provider request IDs and finish reasons for support; sensitive request/response bodies are controlled artifacts, not log lines.

## Metrics

| Area | Metrics |
|---|---|
| Outcomes | jobs/stages completed, failed, cancelled, needs-review; success rate by stage/error class |
| Latency | queue wait, stage duration, provider latency, end-to-end processing time, render realtime factor |
| Reliability | retry count, timeout count, heartbeat age, duplicate suppression, cancellation lag, cleanup backlog |
| Capacity | queue depth/oldest age, active workflows, per-queue concurrency, CPU, memory, temp-disk, object-store throughput |
| AI and cost | LLM input/output tokens, estimated cost, OCR units, TTS characters/audio seconds, provider errors/rate limits |
| Quality workflow | OCR review rate, translation validation findings, tone-review regressions, entity conflicts, duration-repair rate, subtitle-render validation failures, unresolved-review rate |

Use bounded labels such as stage, provider, model family, approved tone preset, error code, and environment. User/project/workflow/artifact/style/policy version IDs are not metric labels.

## Cost ledger

Record provider usage per stage execution with quantity, unit, provider/model, price-card version, currency, estimated cost, and provider request ID. Record render CPU time and generated audio duration even when no direct vendor price applies. Estimates are visibly labeled and reconciled against vendor invoices outside the critical workflow.

## Health and alerting

API readiness verifies required dependencies without causing excessive load. Workers expose liveness, readiness, current activity/resource use, and last successful poll/heartbeat. Alerts focus on user impact and exhaustion: queue oldest age, failure-rate/error-budget burn, stuck workflows, missing heartbeats, temp-disk pressure, provider throttling, cleanup backlog, cost spikes, and authorization anomalies.

Each actionable alert needs a runbook owner, severity, diagnostic queries, safe mitigation, and escalation path before production. Dashboards show end-to-end funnel, queue/capacity, provider health/cost, media resources, and review backlog.

## Sampling and retention

Keep errors and slow traces at higher sampling rates; sample routine successful spans. Configure retention by environment and data sensitivity. Redaction is tested.

The local deployment uses an OpenTelemetry Collector, Prometheus, Grafana, and Jaeger with persistent but bounded retention. Structured application/container logs initially use size- and time-rotated host files; add Loki only if cross-process log search proves worth its memory and disk cost. Dashboards are loopback-only by default and may be exposed temporarily through an operator-only Tailscale Serve listener. No paid telemetry backend is required.
