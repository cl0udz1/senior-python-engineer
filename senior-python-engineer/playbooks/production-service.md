# Production Service

## Contents

- [1. Typical system shape](#1-typical-system-shape)
- [2. Important constraints](#2-important-constraints)
- [3. Recommended discovery questions](#3-recommended-discovery-questions)
- [4. Common architecture choices](#4-common-architecture-choices)
- [5. What not to overengineer](#5-what-not-to-overengineer)
- [6. Failure modes](#6-failure-modes)
- [7. Performance considerations](#7-performance-considerations)
- [8. Testing strategy](#8-testing-strategy)
- [9. Security concerns](#9-security-concerns)
- [10. Deployment/lifecycle concerns](#10-deploymentlifecycle-concerns)
- [11. References for unresolved questions](#11-references-for-unresolved-questions)
- [12. Exit/readiness criteria](#12-exitreadiness-criteria)

**Modes:** DESIGN, IMPLEMENT, REVIEW · **Concerns:** DEPLOY, SHIP · **Domains:** BACKEND_APPLICATION, DEVOPS_INFRASTRUCTURE (when SHIP/DEPLOY)
Procedure for running long-lived Python services in production. Governing rule: correctness at runtime
is owned by **process topology, shutdown/drain, and observability** — not by code elegance
([Deployment](../references/deployment.md), [Reliability](../references/reliability.md)).

## 1. Typical system shape

- Shape: **stateless-ish service processes + managed state (DB/cache/queue) + observability**. In-process state (caches, pools) has a named owner and a warmup/shutdown story ([I2](../core/python-invariants.md), [I4](../core/python-invariants.md)).
- Process model explicit: N workers × M threads/loop per container, stated and measured ([Deployment](../references/deployment.md)); a container is a unit of capacity accounting.
- Three probes/paths defined: readiness (safe to receive traffic), liveness (worth restarting), startup (slow-boot protection) — they are different questions [FRAMEWORK/ECOSYSTEM].
- Calls that can stall a request or job have effective timeout/deadline bounds, and the service
  degrades visibly rather than silently ([I13](../core/python-invariants.md)).
- Resource limits (memory/CPU) set per container and matched to the process model; an unlimited container is a noisy-neighbor generator [ECOSYSTEM].

## 2. Important constraints

- **SLOs first**: latency/availability targets drive probes, capacity, and alerting; without an SLO, "production-ready" is undefined [HEURISTIC].
- **Graceful shutdown/drain**: on SIGTERM — stop accepting new work, finish or safely abandon in-flight work within a deadline, close pools, exit ([Reliability](../references/reliability.md)).
- **Probes are not interchangeable**: readiness removes an instance from traffic; liveness restarts it. Aggressive liveness under overload = cascading restarts ([Deployment](../references/deployment.md)).
- **Config/secret boundary**: config is validated at startup (fail fast on missing/invalid), secrets from a secret manager ([I15](../core/python-invariants.md)); config drift between instances is an incident class of its own.
- **Capacity is measured**: worker counts, pool sizes, memory limits against real load — formulas copied from docs are wrong for your workload [ECOSYSTEM].

## 3. Recommended discovery questions

Ask only what changes the operational design:
- What are the SLOs (latency percentile, availability, throughput)? (Everything downstream hangs on this.)
- What is the deploy cadence and rollout strategy (rolling, blue/green, canary)? (Drain windows, probe tuning.)
- What does a cold start cost — imports, pool warmup, cache fill? (Startup probe, pre-warming.)
- Which dependencies must be reachable for the service to be "ready"? (Readiness semantics, degraded modes.)
- What is the request concurrency profile and where do pools connect (DB, cache, external APIs)? (Pool sizing vs worker count.)
- What is the on-call failure surface — what pages a human at 3am? (Alert design, runbook.)
- Compliance/logging retention requirements? ([Observability](../references/observability.md) design.)
- What is the rollback path and how fast is it? (Deploys are reversible or not — state which.)
- Which single dependency is most likely to fail first? (Degradation design targets that path.)

## 4. Common architecture choices

- **Compute target** ([Decision Model](../core/decision-model.md) §8): IF steady, modest load with an ops platform → container on an orchestrator; VM is fine for a single well-understood service. IF spiky/event-shaped with real statelessness → serverless (cold start + timeout constraints accepted). Worker fleet only for queue-driven work ([workers-jobs.md](workers-jobs.md)). "Kubernetes by default" is platform preference, not architecture.
- **Worker counts measured** ([Deployment](../references/deployment.md)): benchmark p95 under target concurrency with realistic pool sizes; Uvicorn/Gunicorn worker/worker-class choice is workload-specific [FRAMEWORK]. IF handlers are CPU-bound → more processes; IF wait-bound with async stack → fewer processes, async loop.
- **Readiness ≠ liveness**: readiness = "can serve correctly now" (deps reachable, warmup done); liveness = "process is not unrecoverably stuck". Keep liveness conservative — restart is an outage hammer ([Deployment](../references/deployment.md)).
- **Graceful degradation**: IF a dependency is down → defined behavior (serve degraded, queue, or fail fast with clear errors) — chosen per endpoint criticality, not by accident.
- **State**: IF in-process caches → explicit invalidation/TTL + owner + warmup cost ([Decision Model](../core/decision-model.md) §4); cross-instance consistency is a design statement.
- **Connection pools**: sized for worker count × per-request need, with timeouts; a pool sized for a web default under a 64-worker config is an incident waiting ([Deployment](../references/deployment.md)).

## 5. What not to overengineer

- Service meshes, multi-region active-active, and autoscaling policies for steady, modest load with one service ([I11](../core/python-invariants.md)).
- Custom deployment machinery over the platform's rolling update + probes; elaborate sidecar architectures for logging when a stdout collector works [ECOSYSTEM].
- Circuit-breaker libraries everywhere before any dependency has failed in a way that needed one; chaos-engineering platforms before basic probes and alerts exist.
- Microservice extraction "for reliability" — distribution adds failure modes ([Decision Model](../core/decision-model.md) §3).
- Multi-language service rewrites for load one Python service handles comfortably — measured capacity beats architectural fashion ([Evidence Rules](../core/evidence-rules.md) §3).

## 6. Failure modes

Domain-relevant subset of [Failure Modes](../catalogs/failure-modes.md):
- **Cascading failure from aggressive liveness** — overload → slow health checks → restarts → less capacity → more overload (mitigate: conservative liveness, readiness shedding, load shedding).
- **Connection pool exhaustion** — pool smaller than concurrent demand; requests queue inside the app and time out together.
- **No drain on deploy** — SIGTERM kills in-flight requests; user-visible 5xx spikes every deploy (mitigate: preStop/drain + graceful shutdown).
- **Config drift** — instances running different config versions; behavior differs by instance, debugged for hours (mitigate: validated central config, versioned deploys).
- **Missing timeouts on outbound calls** — one slow dependency consumes all workers.
- **Unbounded in-process growth** (cache without TTL, queue without cap) — memory climbs until OOMKill ([Failure Modes](../catalogs/failure-modes.md) Q8; [Anti-Patterns](../catalogs/anti-patterns.md) §24).
- **Silent degradation** — errors logged at debug; the service is "up" but broken ([I13](../core/python-invariants.md)).

## 7. Performance considerations

- Evidence-first ([I9](../core/python-invariants.md), [Evidence Rules](../core/evidence-rules.md) §3, [Performance](../references/performance.md)): load-test or capacity-estimate before declaring readiness (§12).
- Attribute production latency correctly: app time vs dependency time vs queueing (pool waits) vs serialization ([Observability](../references/observability.md) traces).
- Scale order: fix the dominant cost (usually data access/external calls) → tune concurrency/pools → add instances → revisit architecture ([Decision Model](../core/decision-model.md) §6).
- GC/memory behavior is [CPYTHON]-specific — watch RSS and pause behavior under real load, don't theorize; optional free-threaded builds change trade-offs but not the need for measurement ([modern-python-baseline.md](../references/modern-python-baseline.md)).
- Verify runtime/JIT feature status for the selected build before changing production flags; choose
  profiling tools to collect workload evidence ([modern-python-baseline.md](../references/modern-python-baseline.md)).
- Tail latency is usually queueing (pool waits, thread contention), not average compute; fix the queue before the code [HEURISTIC].

## 8. Testing strategy

- Beyond unit tests ([Testing](../references/testing.md)):
  - **Load/soak tests** at target concurrency before launch; soak for leak/growth patterns (§7).
  - **Failure-injection checks**: dependency down/timeout → defined degradation behavior tested.
  - **Deploy rehearsal**: shutdown/drain verified in staging — in-flight requests complete, no error spike.
  - **Migration tests** for schema changes under rolling deploy (old + new code coexist) ([migration-plan](../templates/migration-plan.md)).
- [Production Readiness](../reviews/production-readiness.md) review is the release gate ([templates/production-readiness.md](../templates/production-readiness.md)).
- Regression/perf budget check: latency at target load does not regress beyond an agreed budget between releases.

## 9. Security concerns

- Production posture ([Security](../references/security.md), [Security Review](../reviews/security-review.md)):
  - Authn/authz enforced at the service boundary; network policy limits what the service can reach (least privilege includes network).
  - Secrets from a secret manager, rotated, never in images/env dumps/logs ([I15](../core/python-invariants.md)).
  - Supply chain: pinned, locked dependencies ([packaging](../references/packaging.md)); attestations improve provenance, not safety; vulnerability response process defined ([dependency-review](../reviews/dependency-review.md)).
  - Generated infrastructure/deploy code is untrusted proposed change — review before apply ([Code Review](../reviews/code-review.md)).

## 10. Deployment/lifecycle concerns

- Deploy sequence: versioned artifact → readiness gate → rollout with drain → post-deploy verification ([Deployment](../references/deployment.md)).
- Runbook basics per service: dependency list, common failure modes, restart/drain procedure, rollback command, escalation path ([Reliability](../references/reliability.md)).
- Probes: startup for slow boots, readiness gating traffic, liveness conservative; each documented with its check semantics.
- Observability: RED/USE-style metrics per service ([Observability](../references/observability.md)), structured logs with correlation, traces to dependencies; alerts map to runbook entries — an alert without an action is noise.
- Cost/capacity review cadence: reserved vs on-demand, per-instance memory fit — production cost drifts silently [HEURISTIC].

## 11. References for unresolved questions

Read only the section that answers an active question; this list is a menu, not a reading sequence.

- [references/deployment.md](../references/deployment.md) — process model, probes, drain, worker counts (core of this playbook).
- [references/reliability.md](../references/reliability.md) — timeouts, graceful shutdown, degradation, retry policy.
- [references/observability.md](../references/observability.md) — metrics/logs/traces design, alerting.
- [core/python-invariants.md](../core/python-invariants.md) — I2, I4, I6, I13, I15 at runtime.
- [core/decision-model.md](../core/decision-model.md) §8 — container/VM/serverless/worker-fleet frame.
- [references/packaging.md](../references/packaging.md) — reproducible builds, lockfiles for deployable artifacts.
- [references/security.md](../references/security.md) — secrets, supply chain, network posture.
- [reviews/production-readiness.md](../reviews/production-readiness.md), [templates/production-readiness.md](../templates/production-readiness.md) — the release gate.
- [templates/migration-plan.md](../templates/migration-plan.md) — schema/config migrations under rolling deploys.

## 12. Exit/readiness criteria

Apply the [mode-specific completion rules](../SKILL.md#task-modes) to the relevant criteria below.
Operational checks are release gates only when release readiness is in scope. Report actual evidence
and label proposed or unavailable checks.

Observable checklist:
- [ ] SLOs named (latency/availability/throughput) and alerts mapped to them ([Reliability](../references/reliability.md)).
- [ ] Runbook basics exist: deps, failure modes, drain/restart, rollback, escalation ([Reliability](../references/reliability.md)).
- [ ] Load test run or capacity estimate recorded; worker/pool counts justified by measurement ([Deployment](../references/deployment.md)).
- [ ] Readiness/liveness/startup probes defined with distinct semantics and documented checks.
- [ ] Graceful shutdown/drain verified (staging deploy rehearsal: no error spike, in-flight completes).
- [ ] Config/secret boundary validated at startup; secrets out of images/logs ([I15](../core/python-invariants.md)).
- [ ] [Production Readiness](../reviews/production-readiness.md) checklist passed and recorded ([templates/production-readiness.md](../templates/production-readiness.md)).
- [ ] Resource limits set per container and consistent with the process model; rollback path documented and fast.
- [ ] Alerts map 1:1 to runbook actions; on-call knows the failure surface.
