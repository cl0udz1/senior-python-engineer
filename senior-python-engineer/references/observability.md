# Observability

## Contents

- [stdlib logging fundamentals](#stdlib-logging-fundamentals)
- [Structured logging](#structured-logging)
- [What to measure: RED / USE heuristics](#what-to-measure-red--use-heuristics)
- [OpenTelemetry ECOSYSTEM/FRAMEWORK](#opentelemetry-ecosystemframework)
- [Correlation IDs and context propagation](#correlation-ids-and-context-propagation)
- [Metrics cardinality and cost](#metrics-cardinality-and-cost)
- [Error tracking](#error-tracking)
- [Audit vs debug logging](#audit-vs-debug-logging)
- [Health/readiness signals](#healthreadiness-signals)
- [Observability proportional to risk](#observability-proportional-to-risk)
- [What NOT to log (I15)](#what-not-to-log-i15)
- [Operational checklist](#operational-checklist)

Operational reference for logs, metrics, traces, and operational signals. Version-sensitive facts
live only in [modern-python-baseline.md](modern-python-baseline.md). Cross-refs:
[reliability.md](reliability.md) (health probes), [deployment.md](deployment.md) (topology),
[security.md](security.md) (secrets/PII). Invariants I13 (failure visibility), I15 (no secrets in logs).

## stdlib logging fundamentals

- `logging` module [LANGUAGE]: loggers (named, hierarchical by dot-path), handlers (stream/file/
  socket/HTTP), formatters, levels (DEBUG/INFO/WARNING/ERROR/CRITICAL). Use `logging.getLogger(__name__)`
  per module — hierarchy makes per-package level control possible.
- Library code logs to its own logger at module name, never configures root handlers or calls
  `basicConfig` — application code owns configuration. This separation is what makes libraries usable
  in someone else's process.
- Levels as contracts: DEBUG = diagnostics for developers (verbose, may include payload fragments —
  still not secrets, I15), INFO = lifecycle events worth keeping (started, connected, job completed),
  WARNING = unexpected but handled, ERROR = failed operation needing attention, CRITICAL = process
  integrity threatened. If everything is INFO, nothing is.

## Structured logging

- Log **events as data**, not strings: JSON (or key=value) with stable fields — `event`, `timestamp`,
  `level`, `logger`, `trace_id`, `span_id`, `service`, `version`, plus domain fields. String-only logs
  force regex parsing at query time; structured logs are queryable ([ECOSYSTEM] practice).
- Message text is for humans; fields are for machines. Keep field names stable (schema discipline) so
  dashboards/alerts don't break silently.

## What to measure: RED / USE heuristics

- **RED** (per request/endpoint): Rate (requests/sec), Errors (failed/sec), Duration (latency
  distribution — p50/p95/p99, not just mean) [ECOSYSTEM].
- **USE** (per resource/worker): Utilization (% busy), Saturation (queue depth/backlog — how close to
  limit), Errors (failed operations) [ECOSYSTEM]. Saturation is the early-warning signal: utilization
  hits 100% only after saturation has been climbing ([reliability.md](reliability.md) backpressure).
- Business metrics where correctness matters: job success/failure counts, queue lag, idempotency-key
  collisions (I8), retry counts (retry rate = dependency health signal).
- Connect measurements to **SLIs/SLOs** ([reliability.md](reliability.md)): an alert should reference
  the SLO it threatens (error budget burn, latency threshold), not a raw metric crossing a guessed
  number. Dashboards answer the incident questions (is it us? which dependency? since when?),
  so organize them by those questions, not by metric name.

## OpenTelemetry [ECOSYSTEM/FRAMEWORK]

- OpenTelemetry (OTel) provides vendor-neutral **traces, metrics, logs** with context propagation; Python
  SDK supports manual instrumentation + library/framework instrumentation (HTTP clients/servers, DB
  drivers, async frameworks). Exporters route to any backend (Jaeger, Prometheus, cloud vendors).
- Traces answer "where did the time go across services"; spans around DB queries, external calls,
  and queue publish/consume make request paths visible without guessing ([performance.md](performance.md)
  attribution).
- Instrumentation choice: auto-instrumentation gets coverage fast; manual spans on business-critical
  paths (payment, job boundaries) carry domain context auto-instrumentation can't know. Do not double
  instrument (auto + manual on same call = noisy traces).

## Correlation IDs and context propagation

- For workflows crossing components, carry a correlation/trace ID through HTTP handlers, service
  calls, queue messages, background tasks, and logs. DB spans can link query activity to the request;
  SQL comments/tags are optional where their diagnostic value outweighs cost and data exposure.
- **asyncio**: `contextvars` propagate context across awaits automatically (same task); explicit
  capture when spawning tasks (`create_task` copies context) and when crossing process/queue
  boundaries ([asyncio-concurrency.md](asyncio-concurrency.md)). **Threads**: contextvars do not
  auto-propagate to `ThreadPoolExecutor` workers in older patterns — capture/attach explicitly.
- Queue/async job propagation: put the correlation ID in the message envelope; consumer continues the
  trace or starts a child span linked to it. Losing IDs at queue boundaries is the common gap.

## Metrics cardinality and cost

- Metric labels (dimensions) explode cardinality: `user_id`, `request_id`, raw URLs as labels = one
  time series per value → storage and query cost, dashboard collapse. Labels are for **bounded**
  dimensions (endpoint template, status class, service, region); everything else belongs in logs/traces
  where it's high-cardinality-safe [ECOSYSTEM].
- Histograms/percentiles beat averages for latency (averages hide tail); bucket boundaries set at
  SLO-relevant values ([reliability.md](reliability.md) deadlines). Emit metrics at the right
  granularity: per-request on hot paths, per-job on batch work — not per-loop-iteration.

## Error tracking

- Exceptions captured with full context (trace_id, user/request metadata, stack) to error-tracking
  systems (Sentry-class [ECOSYSTEM]) grouped by fingerprint; alert on **new** error classes and error
  **rate**, not individual occurrences (noise → alert fatigue → ignored outages).
- Unhandled exceptions at boundaries: web framework error handlers ([web-frameworks.md](web-frameworks.md)),
  worker top-level catch (I13: record and isolate the job). Never `except Exception: pass` — silent
  failures are invisible to every tool in this file.

## Audit vs debug logging

- **Audit log** (who did what to which resource when): append-only, security-relevant, retained per
  compliance — separate stream from debug logs ([security.md](security.md)). Login, permission change,
  data export, payment. Mutations to audit records are a security property, not a logging preference.
- **Debug logging**: developer diagnostics, verbose, short retention, may be sampled or disabled in
  prod except on demand (dynamic level adjustment [ECOSYSTEM] — flag-gated, not per-deploy rebuilds).

## Health/readiness signals

- Health endpoints feed the platform ([reliability.md](reliability.md) readiness vs liveness;
  [deployment.md](deployment.md) probes). Emit metrics on probe failures — a silent readiness flap is
  an outage before anyone notices. Metrics for: dependency health (DB pool, cache hit rate), queue
  depth, in-flight requests, graceful-shutdown state.

## Observability proportional to risk

- Internal script: clear stderr + exit codes may suffice [HEURISTIC]. For a customer-facing service,
  choose metrics, traces, error tracking, and audit records according to its risk and diagnostic needs;
  audit records matter most for security-sensitive or regulated actions. Proportionality applies to cost too —
  trace sampling (head/tail) keeps volume sane at high QPS [ECOSYSTEM]; retain enough error traces to
  diagnose failures within privacy, retention, and cost limits.

## What NOT to log (I15)

- Secrets, tokens, passwords, full auth headers, connection strings (I15). PII: log minimum necessary
  (IDs over names/emails), or pseudonymize; know retention/GDPR-class obligations
  ([security.md](security.md)). Full request/response bodies: log selectively (error paths, sampled),
  redact sensitive fields at the logger layer, not per-call-site discipline alone.
- Crash dumps and core files can contain secrets in memory — treat their storage as credential-adjacent.

## Operational checklist

1. Correlation ID on every request/job path? 2. RED metrics on entrypoints, USE on resources?
3. Structured logs with stable fields? 4. Error tracking grouped and alerting on rate/new classes?
5. Queue depth/lag monitored? 6. Audit stream separate and tamper-evident where required?
7. No secrets/PII in any of the above (I15)? 8. Dashboards/alerts tied to SLOs and deadlines
([reliability.md](reliability.md)), not vanity graphs.
