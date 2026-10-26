# Production Readiness — Ship Gate

## Contents

- [Fill-in structure](#fill-in-structure)
- [Verdict](#verdict)
- [Service & SLOs](#service--slos)
- [Load & capacity evidence](#load--capacity-evidence)
- [Correctness & data integrity checks](#correctness--data-integrity-checks)
- [Concurrency & idempotency answers](#concurrency--idempotency-answers)
- [Timeouts / retries / shutdown (I6, I8)](#timeouts--retries--shutdown-i6-i8)
- [Observability & alerts](#observability--alerts)
- [Security & dependency review status](#security--dependency-review-status)
- [Deployment](#deployment)
- [Rollback plan](#rollback-plan)
- [Runbook essentials](#runbook-essentials)
- [Filled fragment](#filled-fragment)

Purpose: the decision document for work with SHIP/DEPLOY concerns: evidence that this service is ready to carry
production traffic, and a GO / GO-with-conditions / NO-GO verdict with named conditions. A gate with
no evidence is theater; a gate with no verdict is a memo.

When to use: before a first production deploy, before a materially new path carries real traffic, or
after a significant architecture change. Pair with a [Failure Review](failure-review.md) for the paths
that carry consequences. Operational detail: [Deployment](../references/deployment.md),
[Reliability](../references/reliability.md), [Observability](../references/observability.md).

Follow [task modes](../SKILL.md#task-modes): a readiness REVIEW reports the evidence and verdict; it
does not itself deploy or change the service. A DESIGN request specifies future gates without
claiming they passed. Execute release actions only within the requested implementation scope.

Scale rule: a low-risk internal tool needs only the sections relevant to its failure cost; an
internet-facing money path needs deeper evidence. Empty sections are honest —
"not applicable, here's why" beats filler.

---

## Fill-in structure

# Production readiness: <service> — <date> — <version/commit>

## Verdict
**GO | GO-with-conditions | NO-GO**
*Conditions are numbered, named, and each has an owner, deadline, and verification. A NO-GO names
exactly what would flip it to GO.*

## Service & SLOs
*What the service does, who calls it, traffic shape. SLOs as numbers (availability, p95/p99 latency,
throughput) — with the error budget policy in one line. If no SLO: state what "healthy" means instead.*

## Load & capacity evidence
*Measured load or, before a system exists, an explicit estimate with a test and review trigger. State
max sustained rate and saturation point when known, and what is expected to break first (CPU? pool?
DB?). Worker/process/thread counts are checked against CPU, memory, and connection pools as evidence
becomes available; do not copy a generic formula [ECOSYSTEM].*

## Correctness & data integrity checks
*What proves outputs are right: test tiers run (list commands + results), data invariants checked,
migration integrity verified. Known data risks and their mitigations.*

## Concurrency & idempotency answers
*Shared state owners (I4); session/transaction scope visible (I7); every retried write has an
idempotency answer (I8); race scenarios from the failure review resolved or accepted with rationale.*

## Timeouts / retries / shutdown (I6, I8)
*Table: calls that can stall the use case → effective timeout/deadline → retry policy (what, budget,
backoff where useful) → what never retries. Shutdown/drain sequence with its deadline; what happens to
in-flight work on SIGTERM and on SIGKILL. Cancellation residue is identified and recoverable (Q12 in
[failure-modes](../catalogs/failure-modes.md) terms).*

## Observability & alerts
*SLIs → dashboards → alert thresholds, each alert tied to a symptom an operator can act on. Logs carry
correlation IDs across boundaries; what you cannot see in production is what you'll debug by guesswork.*

## Security & dependency review status
*Trust boundaries validated (I1); secrets handling (I15); authn/authz checked at the edge; dependency
vulnerability status and lockfile state ([Dependency Review](../reviews/dependency-review.md)).
AI-generated code crossing trust boundaries re-checked as untrusted proposed change
([Code Review](code-review.md)). Note residual accepted risks.*

## Deployment
*Liveness vs readiness probes and their criteria (readiness removes from traffic; liveness restarts —
aggressive liveness under overload causes cascading failure). Resource limits. Migration plan link
([Migration Plan](migration-plan.md)) if schema changes ship with this. Rollout strategy (rolling?
canary?) and what's observed between stages.*

## Rollback plan
*Exact steps to the previous version, time estimate, who can execute. Data compatibility: does rollback
need the previous schema to still work (expand-contract window)? Rehearsed? State rehearsed/not.*

## Runbook essentials
*Top 3–5 failure scenarios from [failure-review](failure-review.md): symptom → first diagnostic step →
mitigation. Link to dashboards. A runbook nobody can follow at 3am is decoration.*

---

## Filled fragment

*Illustrative example only: replace its names, values, and reported outcomes with project evidence.*

```markdown
## Verdict
GO-with-conditions:
- C1: SLO p99 latency is projected, not measured — run the load test before 10% canary.
  Owner: @ravi. Verify: attached k6 report ≥ 200 rps at p99 < 400ms.
- C2: no alert on queue depth (gap G2 of failure-review). Owner: @ops, deadline: ship+24h.
  Verify: alert rule fires in staging.

## Load & capacity evidence
k6 replay of last week's traffic: 150 rps sustained, p95 180ms, CPU 45% with 4 Uvicorn worker processes.
The app separately owns a bounded executor for its blocking integration (2 threads per worker);
this is an application setting, not a Uvicorn threads option. In this illustrative run, 8 workers
performed worse because of pool contention; DB pool size was 20 per process.

## Timeouts / retries / shutdown (I6, I8)
| Call | Timeout | Retries | Never retried |
|---|---|---|---|
| gateway.charge | 10s | 3×, exp backoff+jitter, provider-honored key=charge_id | 4xx, auth failures |
| db (per tx) | 5s stmt / 30s tx | serialization retries = whole tx [FRAMEWORK] | — |
SIGTERM: stop intake → drain in-flight 25s (K8s grace 30s) → close pools. SIGKILL path: leases expire,
jobs redeliver idempotently.
```
