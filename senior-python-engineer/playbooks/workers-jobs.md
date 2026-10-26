# Workers & Jobs

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

**Modes:** DESIGN, IMPLEMENT, REVIEW · **Concerns:** DEPLOY · **Domains:** WORKERS_JOBS
Procedure for queue consumers, background workers, and scheduled jobs. Governing rule: assume
**at-least-once delivery and crash-mid-job**; every job type gets an idempotency answer
([I8](../core/python-invariants.md), [Decision Model](../core/decision-model.md) §4).

## 1. Typical system shape

- Unit shape: **fetch job → process → ack/commit**, with the processing unit small enough to reason about ("what happens if we die exactly here?").
- Idempotent units by design: jobs are replays of intent ("send invoice #42"), not of effects ("increment counter") [HEURISTIC].
- Worker = long-running process: loop with explicit lifecycle (startup check, bounded loop, graceful drain on shutdown) ([Reliability](../references/reliability.md)).
- Scheduled jobs = the same unit shape triggered by time; the scheduler (cron/Airflow-like/orchestrator) is replaceable, the job function is not.
- Job payloads are data, versioned with a schema or at least a version field; two code versions run concurrently during deploys [HEURISTIC].
- IF work fits a direct call in the request that produced it → a queue is not owed yet ([Decision Model](../core/decision-model.md) §4).

## 2. Important constraints

- **Delivery semantics**: broker guarantees are usually at-least-once [ECOSYSTEM]; assume duplicates and reordering unless the broker contract says otherwise. Design for them; don't hope.
- **Crash mid-job**: the window between "work done" and "ack/commit" always exists; the design's answer is idempotent re-execution or a dedupe record ([I8](../core/python-invariants.md)).
- **Poison messages**: one malformed job must not wedge the queue — bounded retries then dead-letter/park with the payload preserved.
- **Backpressure**: queue depth is a health signal; unbounded queue growth means producers outrun consumers — define limits and behavior at the limit ([Failure Modes](../catalogs/failure-modes.md) Q8).
- **Shutdown drain**: deploys kill workers; in-flight jobs need a bounded drain window before hard exit ([Deployment](../references/deployment.md)).

## 3. Recommended discovery questions

Ask only what changes the design:
- What is the cost of this job running twice? (Idempotency mechanism per job type, [I8](../core/python-invariants.md).)
- What is the cost of running zero times, or late? (Delivery guarantees, alerting, backlog SLO.)
- Can one job's failure block others? (Per-message ack, dead-letter policy.)
- What is the expected rate and job duration? (Concurrency, prefetch, pool sizing — measured, not formulaic.)
- What does "done" mean — external effect visible, or local commit? (Where the ack boundary sits.)
- Does job order matter anywhere? (Partitioning/keyed queues; most work does not need global order [HEURISTIC].)
- What state does a job touch, and who else touches it? (Locking/contention, [I4](../core/python-invariants.md).)
- What must be visible when something goes wrong? (Logging fields, retry state, queue-depth metrics.)
- Are there consumers of "done" state downstream that assume uniqueness? (Dedupe requirement surfaces elsewhere.)

## 4. Common architecture choices

- **Queue vs direct call** ([Decision Model](../core/decision-model.md) §4): IF work needs buffering, retries independent of the request, decoupled scheduling, or fan-out → queue + workers. BUT IF the call is synchronous, small, and its failure semantics are simpler inline → direct call; a queue "for reliability" without an idempotency answer is less reliable, not more.
- **Retry policy** ([I8](../core/python-invariants.md)): IF the effect is naturally idempotent (read, keyed upsert) → bounded retries, with backoff when load warrants it. BUT IF not idempotent → use a key honored where the effect occurs, reconcile uncertain outcomes, or avoid automatic retry. A local dedupe record alone cannot make an external effect atomic with the job transaction. Serialization failures: retry the whole database transaction [FRAMEWORK].
- **Structured tasks** ([I6](../core/python-invariants.md)): IF async workers → `TaskGroup`/bounded task sets with deadlines and preserved cancellation; unbounded `create_task` is a defect. BUT IF sequential sync workers → the loop is the structure; don't add asyncio for sequential processing ([Decision Model](../core/decision-model.md) §1).
- **Concurrency**: threads for wait-bound job bodies, processes for CPU-bound ([Decision Model](../core/decision-model.md) §1); prefetch/batch size tuned to job duration and memory, measured.
- **Ack boundary**: ack after the effect is durable or its uncertain outcome has a recovery path. For an
  external non-transactional effect, use provider idempotency or reconciliation; the local job record
  tracks intent but does not guarantee one effect ([I8](../core/python-invariants.md)).
- **Visibility/lease timeout**: cover expected job duration or renew the lease; expiry can create
  overlapping workers, so the effect must remain safe to repeat. Set this deliberately.

## 5. What not to overengineer

- Event sourcing, CQRS, saga orchestration for a simple queue consumer with one store ([I11](../core/python-invariants.md)).
- Multiple brokers/queues for one workload class; priority queues before measurement shows FIFO hurts.
- Workflow engines for what is a for-loop; job frameworks with ten config knobs for three job types.
- Exactly-once marketing: design idempotency instead of chasing broker feature myths [HEURISTIC].
- Per-job microservices; distributed tracing before basic logs with job IDs exist.
- Exactly-once infrastructure claims accepted without reading the broker's actual contract [FRAMEWORK].

## 6. Failure modes

Domain-relevant subset of [Failure Modes](../catalogs/failure-modes.md):
- **Double-processing** — ack lost/late + visibility timeout expiry → job runs twice; non-idempotent body double-charges ([I8](../core/python-invariants.md) violated).
- **Unbounded queue growth** — producer outpaces consumer or consumer is dead; no depth alert, backlog discovered by customers ([Failure Modes](../catalogs/failure-modes.md) Q8).
- **Lost jobs on deploy** — shutdown signal kills in-flight work without drain; jobs acked-then-lost or requeued forever ([Deployment](../references/deployment.md)).
- **Poison message wedging** — same job retried infinitely, blocking a partition/shard.
- **No visibility timeout / lease design** — long jobs exceed default lease and duplicate under load.
- **Silent failure** ([I13](../core/python-invariants.md)) — broad `except` + log at debug; failures invisible until data loss is noticed.
- **Shared session/state across concurrent job executions** ([I4](../core/python-invariants.md), [I7](../core/python-invariants.md)).

## 7. Performance considerations

- Evidence-first ([I9](../core/python-invariants.md), [Evidence Rules](../core/evidence-rules.md) §3, [Performance](../references/performance.md)): measure throughput per worker, job-duration distribution, and queue depth under representative load before scaling workers.
- Scaling knobs in order: fix the job body's dominant cost (batch I/O, N+1, per-item calls) → tune concurrency/prefetch (measured against CPU/memory/DB pool) → add workers/instances → only then revisit architecture.
- Connection pools sized for worker concurrency, not for a web default ([Deployment](../references/deployment.md)).
- Batch dequeue/bulk commit where the broker and idempotency design allow; per-message transaction overhead is a common hidden throughput cap.
- "Python is too slow for our workers" claims get profiles first ([Evidence Rules](../core/evidence-rules.md) §3); worker CPU cost is often DB/external I/O in disguise.
- Retries multiply load during incidents: retry storms amplify outages; backoff + jitter + bounded concurrency on retry paths ([Reliability](../references/reliability.md)).

## 8. Testing strategy

- Follow [Testing](../references/testing.md):
  - **Idempotency tests per job type**: run the same job twice; assert one effect. This is the highest-value test in this domain.
  - **Crash-mid-job simulation**: kill between effect and ack; assert re-delivery converges to correct state.
  - **Poison-message path**: malformed payload reaches dead-letter within bounded retries.
  - **Drain test**: shutdown signal → in-flight job finishes or is safely requeued within the deadline.
- Integration tests against the real broker semantics where possible (at-least-once behavior is broker-specific [FRAMEWORK]); fakes for the broker contract only after the contract is documented ([Testing Review](../reviews/testing-review.md)).
- Scheduled-job tests assert overlap behavior (second start while first runs).

## 9. Security concerns

- Proportional to risk ([Security](../references/security.md)):
  - Job payloads cross trust boundaries — validate on receive ([I1](../core/python-invariants.md)); never `pickle`/unsafe-deserialize queue payloads ([Security](../references/security.md)).
  - Worker credentials are least-privilege and scoped to the job's needs; a compromised queue must not become full infra compromise.
  - Secrets in env/secret boundary, redacted from job logs and dead-letter storage ([I15](../core/python-invariants.md)) — dead-letter queues accumulate sensitive payloads; treat storage as sensitive.
- Generated worker code crossing these boundaries is untrusted proposed change ([Code Review](../reviews/code-review.md)).

## 10. Deployment/lifecycle concerns

- Graceful shutdown: stop fetching → finish/commit or requeue in-flight within a deadline → close pools → exit ([Reliability](../references/reliability.md), [Deployment](../references/deployment.md)).
- Overlap policy for scheduled jobs (lock/skip-if-running); double-cron is a duplicate-effect generator ([I8](../core/python-invariants.md)).
- Observability: job ID correlation across logs; metrics per job type — success/failure/retry counts, duration, queue depth, oldest-message age ([Observability](../references/observability.md)).
- Alerting on failure rate and depth/age thresholds; workers that fail silently are invisible for weeks ([I13](../core/python-invariants.md)).

## 11. References for unresolved questions

Read only the section that answers an active question; this list is a menu, not a reading sequence.

- [core/python-invariants.md](../core/python-invariants.md) — I4, I6, I7, I8, I13 dominate this domain.
- [core/decision-model.md](../core/decision-model.md) §1, §4 — queue-vs-call, threads/processes, structured tasks.
- [references/reliability.md](../references/reliability.md) — retry/deadline/drain patterns in depth.
- [references/asyncio-concurrency.md](../references/asyncio-concurrency.md) — only if async workers (TaskGroup, cancellation).
- [references/persistence.md](../references/persistence.md) — transaction boundaries in job bodies ([I7](../core/python-invariants.md)).
- [references/testing.md](../references/testing.md) — idempotency and crash-simulation testing.
- [references/security.md](../references/security.md) — payload deserialization and credential scope.
- [references/deployment.md](../references/deployment.md), [references/observability.md](../references/observability.md) — drain behavior, metrics/alerts.
- [catalogs/failure-modes.md](../catalogs/failure-modes.md) — the duplicate/drain/backlog question set.

## 12. Exit/readiness criteria

Apply the [mode-specific completion rules](../SKILL.md#task-modes) to the relevant criteria below.
Operational checks are release gates only when release readiness is in scope. Report actual evidence
and label proposed or unavailable checks.

Observable checklist:
- [ ] Idempotency answer recorded per job type ("safe to repeat" / dedupe key / no auto-retry) and tested.
- [ ] Drain behavior defined and tested: shutdown within deadline, no lost or permanently-stuck jobs.
- [ ] Poison-message path defined: bounded retries → dead-letter with payload preserved and access controlled.
- [ ] Visibility/lease timeout set against measured worst-case job duration.
- [ ] Backpressure behavior stated: queue depth limits and what happens at the limit.
- [ ] Alerts defined on failure rate and backlog depth/age; logs correlate by job ID.
- [ ] Worker credentials least-privilege; payloads validated at receive ([I1](../core/python-invariants.md)).
- [ ] Payload schema versioning defined (two code versions coexist during rolling deploys).
- [ ] Retry storms bounded: backoff + jitter + concurrency caps on retry paths ([Reliability](../references/reliability.md)).
