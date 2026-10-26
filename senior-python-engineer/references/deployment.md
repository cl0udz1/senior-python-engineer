# Deployment

## Contents

- [Process topology basics](#process-topology-basics)
- [Uvicorn FRAMEWORK](#uvicorn-framework)
- [Gunicorn FRAMEWORK](#gunicorn-framework)
- [Worker counts: measured, not formulaic](#worker-counts-measured-not-formulaic)
- [Containers](#containers)
- [Kubernetes (container orchestration) ECOSYSTEM](#kubernetes-container-orchestration-ecosystem)
- [VM / systemd](#vm--systemd)
- [Serverless / functions ECOSYSTEM](#serverless--functions-ecosystem)
- [Scheduled jobs / cron](#scheduled-jobs--cron)
- [Configuration: environment at the boundary](#configuration-environment-at-the-boundary)
- [Release and rollback](#release-and-rollback)

Operational reference for runtime topology and release mechanics. Version-sensitive facts live only in
[modern-python-baseline.md](modern-python-baseline.md). Cross-refs: [reliability.md](reliability.md)
(failure behavior), [observability.md](observability.md) (signals), [packaging.md](packaging.md)
(artifacts). Server claims tagged [FRAMEWORK]; operational conventions [ECOSYSTEM].

## Process topology basics

- One Python process does one thing at a time per thread ([asyncio-concurrency.md](asyncio-concurrency.md));
  production capacity comes from **process topology** (how many processes, how supervised) more than
  from code micro-optimizations. Topology answers: how many processes, who restarts them, how they
  drain on shutdown, and what limits they run under.

## Uvicorn [FRAMEWORK]

- ASGI server: runs one app in one process; `--workers N` spawns N worker processes (each with its own
  event loop). Graceful-shutdown controls: `--timeout-graceful-shutdown` sets drain time for in-flight
  requests/connections before force-exit [FRAMEWORK].
- Signals: SIGTERM initiates graceful shutdown (stop accepting, drain, exit); SIGINT for local dev.
  Container stop timeouts (`terminationGracePeriodSeconds`, `docker stop -t`) must exceed the app's
  grace period or draining is cut short ([reliability.md](reliability.md) shutdown sequence).

## Gunicorn [FRAMEWORK]

- Supervisor/worker model: a master process manages worker processes (spawn/replace on crash/timeout),
  with pluggable **worker classes** (sync workers; async worker classes for ASGI apps like uvicorn's).
  WSGI apps typically run under sync workers; ASGI apps under an async worker class [FRAMEWORK].
- Gunicorn-as-master + uvicorn-workers is a common ASGI topology [ECOSYSTEM]; plain uvicorn
  multi-worker is the simpler alternative. Choose by supervision needs (worker recycling, hot config
  reload, graceful restart semantics) — both are mature.
- **`--preload` and connection pool fork hazard (I7)**: Gunicorn's `--preload` flag imports code in the
  master process before forking workers. If database connection pools, HTTP clients, or threads are initialized
  at import time or during master setup, child workers inherit identical socket file descriptors, resulting in
  interleaved query traffic, corrupted TLS/SSL streams, and mysterious crashes. When using `--preload`,
  dispose connection pools (`engine.dispose(close=False)`) in Gunicorn's `post_fork` hook or defer connection
  creation to worker startup ([persistence.md](persistence.md)).
- Worker timeout config is a liveness tool: a hung worker gets recycled — but too-aggressive timeouts
  kill slow-but-alive workers ([reliability.md](reliability.md) liveness caution).

## Worker counts: measured, not formulaic

- Banned: magic formulas ("2 × CPU + 1"). The right count is measured against:
  - **CPU**: CPU-bound work (serialization, template rendering) needs cores; wait-bound async can
    multiplex many requests in one worker ([asyncio-concurrency.md](asyncio-concurrency.md)).
  - **Memory**: each worker is a full Python process — RSS × workers must fit the container limit
    (with headroom for spikes) or OOM kills follow.
  - **Connection pools**: sum possible connections across all instances, workers, pools, and other DB
    clients; keep headroom below the database's usable connection limit ([persistence.md](persistence.md)).
    A single worker's pool setting is not the deployment total.
  - **Latency under load**: load-test the actual topology; add workers until p95 stops improving or
    memory/DB limits bind. Latency SLOs ([reliability.md](reliability.md)) define "good enough".
- Per-container **small process counts** is an operational convention [ECOSYSTEM] (clearer resource
  accounting, horizontal scaling over vertical) — not a Python rule. Big containers with many workers
  are legitimate when the workload and ops model support them.

## Containers

- Image size: slim base + wheels-only install ([packaging.md](packaging.md)); exclude build toolchain
  and dev deps from runtime images (multi-stage builds). Smaller image = faster pulls, smaller attack
  surface ([security.md](security.md)).
- Startup: import-time work (I3) is paid per container start — slow starts delay readiness and extend
  crash-recovery time. Lazy-init heavy connections where honest, but keep readiness truthful.
- **Signals**: containers must receive and honor SIGTERM. A Python app running as PID 1 receives it;
  a shell/init/supervisor that launches child workers must forward signals and reap them (use a proper
  init or `--init` when needed). If the app does not drain within the grace period, it can be killed
  mid-write ([reliability.md](reliability.md) drain).
- **Non-root**: run as non-root user; read-only filesystem where possible; no secrets baked into
  image layers (I15).

## Kubernetes (container orchestration) [ECOSYSTEM]

- **Probes** ([reliability.md](reliability.md) for semantics): readiness = remove from traffic;
  liveness = restart; startup = slow-start protection. Misconfigured aggressive liveness under overload
  cascades (restart storms). Readiness should reflect whether this instance can serve its required
  traffic; gate on essential warmup, not an optional cache or every shared downstream outage.
- **Resource requests/limits**: requests = scheduling floor, limits = kill ceiling. Set limits
  (memory OOM-kill is the failure mode; CPU throttling is the latency mode); size from measurement
  (worker math above), not defaults. `terminationGracePeriodSeconds` ≥ app drain time + margin.
- Graceful drain on rollout: preStop sleep/hook gives LB deregistration lag before SIGTERM; app drains
  in-flight; new pods pass readiness before old pods terminate (rolling update surge settings control
  overlap).
- Horizontal scaling signals: CPU (bad for wait-bound — scales too late), RPS/queue-depth/custom
  metrics ([observability.md](observability.md)) are better for async/queue workloads.

## VM / systemd

- VM deployments: systemd units with `Restart=on-failure`, `RestartSec` backoff, proper `Type` and
  stop timeout; logs to journald/stdout. Same lifecycle rules (graceful stop on SIGTERM) apply without
  container orchestration — systemd is the supervisor.
- Simple and boring for single-node or low-scale services; containers earn their cost at
  multi-node orchestration needs ([Decision Model §8](../core/decision-model.md)).

## Serverless / functions [ECOSYSTEM]

- Trade-offs: **cold starts** (import-time cost (I3) directly adds latency), **execution timeouts**
  (bound job size; long work → containers/queues), **statelessness** (no local durable state; external
  store required). Fits spiky/event-driven workloads with short stateless handlers; poor fit for
  long-running jobs, WebSocket fan-in, or warm-pool latency requirements.
- Local dev parity: run the same handler in-process; the platform's event shape is the boundary to test
  ([testing.md](testing.md) integration).

## Scheduled jobs / cron

- Platform cron (K8s CronJob, systemd timers, cloud schedulers) vs in-app schedulers (APScheduler-class
  [ECOSYSTEM]): platform cron is observable and survives process restarts; in-app schedulers couple
  scheduling to app lifecycle — fine for simple periodic work in one process, risky across replicas.
- **Overlap controls**: a long job can overlap its next tick. A scheduler concurrency policy (K8s
  `concurrencyPolicy: Forbid`) or lock/lease reduces overlap, but lease expiry and failover can still
  allow two workers. Use fencing or idempotent effects where overlap would cause harm (I8).
- Alerting: job failure/misfire/overlap events must alert ([observability.md](observability.md)); silent
  cron failure is the slowest kind of outage. Idempotent, resumable jobs make missed ticks recoverable
  ([reliability.md](reliability.md)).

## Configuration: environment at the boundary

- Config enters via environment variables (or mounted files/secret managers) read **once** at a
  settings boundary ([architecture.md](architecture.md) composition root), validated at startup
  (fail fast on missing/invalid config), then passed explicitly. Scattered `os.environ` reads deep in
  code = hidden coupling to deployment ([catalogs/smells.md](../catalogs/smells.md) scattered-config).
- Config precedence and defaults documented; secrets via secret manager/env, never in the repo or
  image (I15). Feature flags for behavior toggles that change faster than deploys.

## Release and rollback

- Artifacts are immutable and versioned (commit SHA or semver baked in, visible in `/version` endpoint
  and logs ([observability.md](observability.md))).
- **Rollback plan exists before rollout**: DB schema changes are expand/contract
  ([persistence.md](persistence.md) migrations) so old code runs against new schema (rolling deploys
  run both versions briefly). Migrations that can't be backward-compatible get a two-release plan
  (deploy tolerant code first).
- Deploy strategy: rolling (default), blue-green or canary for risky changes (observe canary metrics
  before full rollout — RED metrics gate promotion ([observability.md](observability.md))).
- Release gating: CI tests + lint/type ([tooling.md](tooling.md)) — keep gates
  fast and reliable; a flaky gate trains humans to re-run instead of investigate
  ([testing.md](testing.md) determinism).
