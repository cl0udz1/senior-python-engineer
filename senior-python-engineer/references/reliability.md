# Reliability

## Contents

- [Timeouts and effective bounds](#timeouts-and-effective-bounds)
- [Deadlines end-to-end](#deadlines-end-to-end)
- [Cancellation (I6)](#cancellation-i6)
- [Graceful shutdown and queue draining](#graceful-shutdown-and-queue-draining)
- [Partial success semantics](#partial-success-semantics)
- [Retries and idempotency (I8)](#retries-and-idempotency-i8)
- [Backpressure](#backpressure)
- [Health checks: readiness vs liveness ECOSYSTEM](#health-checks-readiness-vs-liveness-ecosystem)
- [Worker crash mid-job](#worker-crash-mid-job)
- [Schema / version compatibility](#schema--version-compatibility)
- [Degradation patterns](#degradation-patterns)
- [Checklist for a new external boundary](#checklist-for-a-new-external-boundary)

Operational reference for production failure behavior. Failure questions live in
[catalogs/failure-modes.md](../catalogs/failure-modes.md); review gates in
[production-readiness.md](../reviews/production-readiness.md). Invariants I2, I6, I8, I13, I14 in
[python-invariants.md](../core/python-invariants.md). Version-sensitive facts live only in
[modern-python-baseline.md](modern-python-baseline.md).

## Timeouts and effective bounds

- Calls that can stall a request or job need an effective bound: a per-call timeout, inherited deadline,
  broker visibility timeout, or controlled shutdown limit as appropriate. A missing bound leaves the
  wait to the caller's patience or the OS's.
- Timeout taxonomy: **connect** (reach the peer), **read/write** (transfer), **pool acquisition**
  ([persistence.md](persistence.md)), **total** (whole operation). Set each deliberately; a read
  timeout without a total bound still allows slow-drip failures.
- Library defaults are not automatically a suitable policy: inspect the pinned client/driver behavior.
  State the effective bound at the use-case boundary even when a framework provides it.

## Deadlines end-to-end

- A **deadline** bounds a whole use case (request, job) and **shrinks as it propagates**: if the request
  has 2s left, downstream calls get ≤2s minus margin. Propagate via context (`contextvars` for async/threads,
  explicit parameter otherwise) so deep code can respect it ([asyncio-concurrency.md](asyncio-concurrency.md)).
- When the deadline passes: stop starting new work, cancel what can be cancelled (I6), and return a
  partial result or a clear timeout error — never silently continue.

## Cancellation (I6)

- Cancellation must reach the actual I/O and not be swallowed (I6). Cleanup in `finally`; re-raise
  `CancelledError` after cleanup. Swallowing it breaks TaskGroup/timeouts and leaves orphaned work.
- On shutdown, tasks are cancelled and given bounded drain time; cancellation residue (half-written
  rows, unsent messages) is designed for — idempotent writes (I8) and transaction rollback make
  cancellation safe ([persistence.md](persistence.md)).

## Graceful shutdown and queue draining

- Shutdown sequence [ECOSYSTEM]: stop accepting new work (readiness off → removed from traffic,
  [deployment.md](deployment.md)) → finish/cancel in-flight within a bounded grace period → close
  resources in LIFO order (I2) → exit. The grace period is explicit config, not the kill timeout guess.
- Queue consumers: on shutdown, **stop fetching** new messages, finish processing current, and let
  unprocessed messages return to the queue (visibility timeout semantics, below). A consumer that dies
  mid-message must not lose the message (at-least-once + idempotent handling, I8).

## Partial success semantics

- Multi-step operations state what partial completion means: does the caller see "all", "none", or
  "some with a report"? Design choices: transaction for atomicity (I7), two-phase with idempotent
  compensation where a transaction can't span systems, or explicit partial-result reporting.
- Never report success on partial completion without saying so; ambiguous success corrupts caller
  state silently (I13). "Half the emails sent" is a result type, not an exception log.

## Retries and idempotency (I8)

- Before ANY retry: "can this operation safely happen twice?" Non-idempotent writes need idempotency
  keys/dedupe/compensation — or no automatic retry (I8).
- Retry policy parts: **classification** (retry only transient: timeouts on idempotent calls,
  connection resets, 502/503; NOT: 400s, 401s, 409s, serialization violations without re-running the
  transaction), **backoff** (exponential + jitter — synchronized retries are a stampede), **budget**
  (max attempts AND total retry time within the deadline), **scope** (whole transaction where atomicity
  matters — PostgreSQL serialization failure retries the transaction, [persistence.md](persistence.md)).
- Retries amplify load on an already-struggling dependency: circuit breakers/admission limits cap the
  damage ([failure-modes.md](../catalogs/failure-modes.md)).

## Backpressure

- Unbounded queues convert dependency slowness into memory exhaustion, then OOM, then data loss. Every
  queue/buffer/fan-out point has a **bound** and a policy when full: block producers (natural
  backpressure), drop oldest (telemetry), shed load (reject requests fast), or spill to disk.
- Admission control at the entry: semaphores/max-in-flight limits per dependency; worker pools with
  bounded concurrency; `asyncio.Semaphore` for async fan-out ([asyncio-concurrency.md](asyncio-concurrency.md)).
- Signals of missing backpressure: growing queue depth, memory creep under load, latency scaling with
  arrival rate instead of service time. Monitor queue depth ([observability.md](observability.md)).

## Health checks: readiness vs liveness [ECOSYSTEM]

- **Readiness** (Kubernetes): "can this instance take traffic now?" Failing readiness **removes from
  traffic** without restart. Use it for instance-specific inability to serve or essential warmup;
  if every instance depends on the same failed service, failing all readiness checks can remove the
  entire fleet. Define degraded behavior and traffic policy for shared outages.
- **Liveness**: "should this instance be restarted?" Failing liveness **restarts the process** — correct
  for deadlock/leak/hung states, wrong for "the DB is slow."
- **Aggressive liveness under overload causes cascading failure**: DB slows → requests back up →
  liveness times out → all pods restart simultaneously → cold caches + reconnect storm → full outage.
  Liveness checks must be cheap and check the *process*, not its dependencies; essential per-instance
  dependency state may inform readiness [ECOSYSTEM]. Startup probes separate slow-start from dead.
- Health endpoints are part of the API surface: cheap, unauthenticated-or-restricted, and free of secrets
  (I15). A simple liveness response can be enough; readiness must reflect the instance's stated ability
  to serve rather than returning 200 regardless of essential startup or local failure.

## Worker crash mid-job

- For **at-least-once** delivery, message visibility timeouts return unacknowledged work to the queue;
  redelivery is normal. Handlers need idempotent effects (I8), dedupe, or reconciliation, and partial
  work must be resumable or transactional. If the broker is at-most-once, name the loss trade-off.
- Poison messages (messages that crash/skip the handler forever): bounded retries then a dead-letter
  queue with alerting — infinite redelivery of a bad message blocks the queue behind it.
- Crash invariants: work state (processed/not/unknown) must be derivable after crash; leases/visibility
  timeouts cover expected processing or are renewed. Redelivery may overlap even then, so effects need
  idempotency or reconciliation. Acknowledge after the effect is durable or its uncertain outcome has a
  defined recovery path ([failure-modes.md](../catalogs/failure-modes.md)).

## Schema / version compatibility

- When rolling deploys run old and new code against the same data/messages simultaneously
  ([deployment.md](deployment.md)), use **expand/contract** for incompatible schema changes: additive
  first (new optional fields), consumers tolerate unknown fields, producers switch later, removal last
  ([persistence.md](persistence.md) migrations).
- API compatibility follows consumer contracts: additive changes may still break strict consumers;
  breaking changes need a coordinated migration, deprecation window, or versioned interface. Contracts
  with external parties benefit from contract tests ([testing.md](testing.md)).

## Degradation patterns

- When a dependency fails, choose the degraded behavior deliberately: serve stale cache (staleness
  budget named), disable non-critical features, queue-and-retry later, or fail fast with a clear error.
  Silent wrong answers are worse than errors (I13).
- Feature flags/config kill-switches for risky paths; timeout budgets prioritized per call path
  (critical path gets the budget first). Degraded modes get tested ([testing.md](testing.md) failure-path)
  — untested degradation paths fail when needed.

## Checklist for a new external boundary

1. Effective bounds on calls that can stall? 2. Deadline propagation? 3. Retry classification + idempotency (I8)?
4. Bounded queue/fan-out? 5. Failure visible (I13)? 6. Degraded behavior defined? 7. Health signal
(ready/live)? 8. Shutdown drain path? ([templates/production-readiness.md](../templates/production-readiness.md))
