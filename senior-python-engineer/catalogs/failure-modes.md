# Failure Modes — Reusable Review Model

## Contents

- [Usage rule](#usage-rule)
- [Core question bank](#core-question-bank)
- [Boundary: HTTP / external API](#boundary-http--external-api)
- [Boundary: database / transaction](#boundary-database--transaction)
- [Boundary: queue / worker](#boundary-queue--worker)
- [Boundary: file / disk](#boundary-file--disk)
- [Boundary: process lifecycle (startup / shutdown / crash)](#boundary-process-lifecycle-startup--shutdown--crash)
- [Boundary: config / secrets](#boundary-config--secrets)
- [Boundary: concurrency](#boundary-concurrency)
- [Boundary: deployment / schema evolution](#boundary-deployment--schema-evolution)
- [Mitigation pattern index](#mitigation-pattern-index)
- [Answers that are not answers](#answers-that-are-not-answers)
- [Cross-cutting semantics](#cross-cutting-semantics)
- [Worked mini-example (how to actually use this)](#worked-mini-example-how-to-actually-use-this)

The failure questions to ask at design and review time — and how to act on the answers. This is the
reusable form of the boundary analysis in [SKILL.md](../SKILL.md#working-sequence) and invariant
**I14** ([python-invariants](../core/python-invariants.md)): at every external boundary, the design
answers the relevant "what happens if…".

## Usage rule

**Ask only the relevant subset.** Mechanically dumping the whole checklist at a reviewer is itself a
failure mode — it buries the 3 questions that matter under 11 that don't. Select by boundary: a pure
CLI parser needs the disk and config questions, not the queue-drain questions. State which subset you
asked and what the answers were; unasked questions are fine, unasked-and-unowned boundaries are not.

Severity note: an unanswered failure question becomes a finding when it exposes a reachable
consequence in this system. Use [finding format](../templates/code-review.md); the MUST label alone
does not set severity.

## Core question bank

1. What happens if the **DB disappears** mid-operation?
2. What happens if this operation **runs twice**?
3. What happens if a **worker dies halfway** through a unit of work?
4. What happens if **shutdown happens right now**?
5. What happens if the **external API times out**?
6. What happens if it returns **malformed data**?
7. What happens if **two workers race** on the same item?
8. What happens if the **queue grows without bound**?
9. What happens if the **disk fills**?
10. What happens if the **schema / version changes** under us?
11. What happens after **partial success**?
12. What **state remains after cancellation**?
13. What gets **retried**?
14. What must **never** be retried?

Questions 2/13/14 are one cluster (idempotency, I8). Questions 3/4/12 are one cluster (lifecycle, I2/I6).
Ask the cluster, not just the line.

### Question selection by system type (starting points, not limits)

| System kind | First questions | Usually skip |
|---|---|---|
| HTTP service ([web-api](../playbooks/web-api.md)) | Q5, Q6, Q2 (writes), Q4 (deploy drain), Q13/14 | Q9 unless it writes files |
| Queue worker ([workers-jobs](../playbooks/workers-jobs.md)) | Q2, Q3, Q7, Q8, Q4, Q14 | Q5 unless it calls out |
| CLI / automation ([cli-automation](../playbooks/cli-automation.md)) | Q9, Q11 (partial run), Q6 (input), Q10 (its own version skew) | Q3, Q7, Q8 |
| Library ([library-package](../playbooks/library-package.md)) | Q6 (caller input), Q12 (cancellation contract), Q13 (what the *library* retries — usually: nothing) | operational questions; those belong to the host app |
| Data pipeline ([data-engineering](../playbooks/data-engineering.md)) | Q2 (re-run), Q11 (partial success), Q3 (crash mid-batch), Q10 (schema change) | Q5 unless it has online serving |

---

## Boundary: HTTP / external API

| Common failure | Typical symptom | Mitigation pattern |
|---|---|---|
| Upstream timeout / hang | Request threads pile up; cascade to callers | Timeout on **every** outbound call (connect + read); deadline propagation so the caller's budget bounds the callee (I6) |
| Upstream slow (not down) | Latency tail explodes; retries amplify load | Hedged requests only where idempotent; circuit breaker to fail fast; bulkhead (separate pool/limit per upstream) |
| Malformed / schema-violating response | `KeyError` deep in parsing; half-processed state | Validate at the boundary (I1); parse-then-act, never mutate state while parsing; reject and record the payload |
| Partial response / truncated body | Silent wrong results | Length/checksum checks where the protocol offers them; validate required fields present |
| Retry storm after outage | Upstream recovery fails under our load | Bounded retries with backoff + jitter (I8); shed load instead of queueing unboundedly |
| Upstream returns 429 / rate limit | Bursts of throttled calls | Respect `Retry-After`; client-side rate limiting; back off instead of hammering |
| Auth expiry mid-flow | 401s interleaved with successes | Refresh at the boundary; never retry auth failures blindly (may be authorization, not transient) |

- **Ask:** Q5, Q6, Q13, Q14, and Q2 for every call that changes upstream state.
- **Do not blindly retry:** non-idempotent calls (charge, send, create-without-key) without an
  effect-level idempotency or reconciliation path; authentication/authorization failures unless a
  defined credential-refresh flow can resolve them; 4xx that indicate our own bug.
- **Idempotency keys:** pass a stable key when the upstream honors it. A local dedupe row records intent
  but cannot alone make an external effect atomic with our transaction. Without upstream dedupe, treat
  timeouts as unknown outcomes and reconcile before retrying (I8).

## Boundary: database / transaction

| Common failure | Typical symptom | Mitigation pattern |
|---|---|---|
| Connection lost / DB restart | `OperationalError` bursts; stale pooled connections | Pool pre-ping/recycle; bound retries when the transaction is known not to have committed. If connection fails around `COMMIT`, reconcile the unknown outcome before repeating a non-idempotent write |
| Serialization failure (PostgreSQL) | Random `SerializationFailure` under concurrency | Retry the **whole transaction** with backoff [FRAMEWORK], not the failed statement (I8) |
| Deadlock | One transaction aborted | Keep transactions short and ordered; retry deadlock victims as whole transactions |
| Partial multi-step write | Half the records updated | One transaction = one visible unit-of-work boundary (I7); or compensating transaction with an explicit saga record |
| Two writers race (lost update) | Counter drift; last-write-wins data loss | Optimistic locking (version column) or `SELECT ... FOR UPDATE`; single-writer ownership where possible (I4) |
| Session shared across tasks | Intermittent `InterfaceError`, wrong rows | Session-per-thread / AsyncSession-per-task — never share (I7; [anti-patterns](anti-patterns.md) §12) |
| Long-running transaction blocks others | Lock waits, "the DB is slow" | Keep transactions short; avoid external calls inside them where possible, and bound/document any necessary exception; statement/lock timeouts; monitor blocking sessions |
| Connection pool exhausted | Requests queue in-app, latency cliff | Sum potential connections across all instances, worker pools, and other DB clients against the usable DB limit, leaving headroom; use a bounded pool wait |
| Migration runs while old code serves | Old code crashes on new schema | Expand-contract migration ([migration-plan](../templates/migration-plan.md)); compatibility window |

- **Ask:** Q1, Q2, Q7, Q11, Q10.
- **The unit-of-work question is usually the real one:** what commits or rolls back together? If the
  answer spans an HTTP call or a user-visible pause, the transaction boundary is wrong (I7).

## Boundary: queue / worker

| Common failure | Typical symptom | Mitigation pattern |
|---|---|---|
| Worker dies mid-job | Job half-applied; message lost or redelivered | Lease / visibility timeout: message returns to the queue if not acked; job must be safe to run twice (I8) |
| Poison message | One message retried forever; queue depth static | Max-receive count → dead-letter/quarantine queue with the failure recorded; alert on DLQ growth |
| Producer outruns consumer | Memory/disk creep; latency grows linearly | Bounded queue + admission control (reject or block at producer); scale consumers; monitor depth (I13 observability) |
| Duplicate delivery (at-least-once) | Double side effects | Effect-level idempotency or reconciliation (I8); a DB-local dedupe record protects only effects covered by its transaction. Check the broker contract |
| Redelivery after timeout but worker still running | Two workers on one item | Visibility timeout > worst-case job time, or lease renewal/heartbeat; or make concurrency safe (I4) |
| Broker unavailable | Enqueue path errors; work piles at producers | Fail fast to the caller or persist to a local buffer with bounds; never an unbounded in-memory stash |
| Shutdown with full queue | Work vanishes on deploy | Graceful drain: stop intake, finish/ack in-flight within a deadline, nack unprocessed (Q4) |

- **Ask:** Q2, Q3, Q8, Q7, Q4.
- **What must never be retried:** jobs that send external effects with no idempotency story; jobs that
  re-run destructive migrations; anything that would double-charge. Quarantine instead.

## Boundary: file / disk

| Common failure | Typical symptom | Mitigation pattern |
|---|---|---|
| Disk full | `ENOSPC` at the worst moment; partial files | Monitor disk; write via temp file + atomic rename so readers never see partial content; bounded log rotation |
| Partial write / crash mid-write | Corrupt artifact read later | Write-temp-then-rename [HEURISTIC]; checksum the artifact; validate on read (I1) |
| Concurrent writers to one file | Torn/lost writes | Single writer ownership (I4); lock file with stale-lock handling; write to per-writer files and merge |
| Path traversal / unsafe temp | Files outside intended dir; predictable temp names race | `tempfile` module (never hand-rolled temp paths); normalize + confine paths at the boundary (I1) |
| Symlink/permission surprises | Writable-by-others config read as trusted | Explicit permissions on created files; don't trust writable-directory contents |
| Read during rewrite | Consumer reads half-swapped file | Atomic rename swap [HEURISTIC]; readers tolerate both versions during the swap |

- **Ask:** Q9, Q11, Q3 (crash mid-write = the disk flavor of "worker dies halfway").
- **Cleanup is lifecycle work:** file handles, temp files, and locks need explicit owners and shutdown
  paths (I2) — GC timing is not a cleanup strategy [LANGUAGE].

## Boundary: process lifecycle (startup / shutdown / crash)

| Common failure | Typical symptom | Mitigation pattern |
|---|---|---|
| Shutdown now, work in flight | Requests cut mid-response; jobs half-done | Graceful shutdown sequence: stop accepting → drain in-flight with deadline → release resources → exit; signal handling per server docs [FRAMEWORK] |
| Liveness probe too aggressive under overload | Restart cascade | Readiness removes from traffic; liveness only for unrecoverable states [FRAMEWORK/K8s]; don't let overload look like death |
| Crash halfway through startup | Half-initialized global state | Fail fast at startup (validate config, check dependencies before serving) (I1); single composition root |
| SIGKILL arrives (no grace period) | Whatever graceful code existed never ran | Make the crash path safe on its own: leases expire, redelivery is idempotent, writes are atomic — graceful drain is an optimization, not the safety net |
| Background task orphaned at exit | Work continues/locks held after "shutdown" | Structured task lifetimes (`TaskGroup`), awaited at shutdown (I6); no fire-and-forget |
| Clock/timezone skew | "Impossible" ordering bugs | Store event instants in UTC; preserve the intended time zone and recurrence rule for local schedules (including DST); do not infer ordering from unsynchronized clocks |

- **Ask:** Q4, Q12, Q3.
- **Cancellation residue (Q12):** after `CancelledError`, what partial state remains and who owns
  cleanup? `finally`/context managers answer this (I2, I6); "the GC will handle it" does not.

## Boundary: config / secrets

| Common failure | Typical symptom | Mitigation pattern |
|---|---|---|
| Missing/wrong config in prod | Behavior differs per environment; silent defaults | Validate config at startup, fail fast on required values; explicit defaults documented as policy ([smells](smells.md) silent fallback) |
| Secret leaks into logs/diffs | Credentials in crash dumps, error messages | Secrets from a secret boundary; never interpolate into messages/exceptions; redact at logger (I15) |
| Config change mid-run | Mixed old/new behavior | Read config once at startup (or an explicit reload path with defined semantics); never sprinkle live reads |
| Secret rotated mid-run | Calls fail after rotation | Refresh-from-boundary with expiry handling; or restart-on-rotation as a documented policy |
| Dependency/provenance surprise | Compromised or broken package after update | Lockfiles ([STANDARD] `pylock.toml` interchange or tool lock); version policy; vulnerability response ([Dependency Review](../reviews/dependency-review.md)) — attestations improve provenance but do not prove code safe |

- **Ask:** Q10 (version skew includes config schema), Q6 (malformed config), and who validates when.

## Boundary: concurrency

| Common failure | Typical symptom | Mitigation pattern |
|---|---|---|
| Two tasks race on shared state | Counter drift, corrupted structures | One owner per mutable state; lock / queue / actor confinement / immutable snapshots (I4) |
| Check-then-act race | Both workers "claim" the same item | Atomic claim at the data store (conditional update/insert), not in application memory |
| Blocking call stalls the event loop | All requests slow together | I5: async-native call, bounded offload, or move the work out ([anti-patterns](anti-patterns.md) §9) |
| Lock held across await/external call | Latency cascades, deadlocks under load | Keep critical sections short and lock order clear; avoid unrelated or unbounded waits while holding a lock. An async lock may intentionally span an `await` when the protected operation requires it |
| Unbounded fan-out | Memory growth, lost tasks | Bound producer admission and backlog; own child lifetimes. A semaphore bounds holders and TaskGroup bounds lifetime, neither alone bounds pending task count (I6) |
| Free-threaded build assumed safe | Rare races in "thread-safe-looking" code | Removing the GIL does not remove data races [CPYTHON]; keep explicit ownership and synchronization, and check extension support and current [baseline](../references/modern-python-baseline.md) status |

- **Ask:** Q7, Q2, Q12, and "who owns this state?" for every mutable object with more than one reader.

## Boundary: deployment / schema evolution

| Common failure | Typical symptom | Mitigation pattern |
|---|---|---|
| New code + old schema (or vice versa) | Deploys break on rollback | Expand-contract: additive migration → deploy → backfill → switch reads → contract later ([migration-plan](../templates/migration-plan.md)) |
| Rolling deploy with mixed versions | Intermittent protocol errors between instances | Version-tolerant message/API contracts; compatibility window of at least one deploy |
| Config/flag flip mid-deploy | Old and new behavior simultaneously | Flip-after-deploy ordering; flags default to the old behavior until all instances are new |
| Rollback path untested | Rollback fails when needed | Rollback is part of the plan, rehearsed at least for the data step; each migration step reversible or explicitly flagged irreversible |
| Partial success in migration/backfill | Half the rows migrated, no marker | Resumable, idempotent backfill (I8) with progress checkpoints and per-batch verification |
| Feature flag left in limbo | Dead code paths, unknown behavior matrix | Flags get an owner and an expiry; measure before removing |

- **Ask:** Q10, Q11, Q2 (migrations re-run), Q4 (deploy mid-job).

---

## Mitigation pattern index

The patterns referenced above, named so designs can cite one instead of re-describing it:

- **Timeouts + deadline propagation** — bound potentially blocking remote calls and fit their budgets
  within the caller's deadline. For local disk work, use resource limits or an outer deadline where
  feasible; a per-call timeout is not always available. Cost: failures under legitimate slowness.
- **Idempotency key / dedupe record** — use a stable key per intended effect where the component that
  performs the effect honors it. A local dedupe row alone cannot make an external call atomic with a DB
  transaction; reconcile uncertain outcomes. Naturally idempotent operations need no extra record.
  Cost: key lifecycle, storage, and sometimes a reconciliation path.
- **Lease / visibility timeout** — a claimed job's lock expires unless renewed; a dead worker's work
  returns to the pool. Answers "worker dies halfway" (Q3). Cost: redelivery — which is why the job must
  be idempotent; the two patterns travel together.
- **Bounded queue + backpressure** — capacity limit plus an explicit overflow policy (block, reject,
  shed). Answers Q8 before it is asked. Cost: producers must handle rejection — an API design decision,
  made under less pressure if made now.
- **Graceful drain** — shutdown stops intake, finishes or nacks in-flight work within a deadline, then
  exits. Answers Q4. Cost: deploys take as long as the drain deadline; the deadline must fit the
  platform's kill grace.
- **Expand-contract migration** — additive change → backfill → switch reads → contract. Answers Q10/Q11
  for schema evolution ([migration-plan](../templates/migration-plan.md)). Cost: a compatibility window
  where both shapes live — with the contract step owed and scheduled.
- **Circuit breaking + bulkhead** — stop calling a failing upstream for a cool-down window; isolate its
  resource pool so its failure can't consume yours. Answers the "slow, not down" cascade. Cost: false
  trips during brownouts; needs sensible thresholds.
- **Poison-message quarantine (DLQ)** — after N failed receives, park the message with its failure
  context and move on; alert on queue growth. Answers "one bad item blocks the world". Cost: someone
  must own the DLQ — an unwatched DLQ is just a slower failure.

## Answers that are not answers

Call these out in review; each is a gap wearing a sentence:

- "The framework handles it." → name the mechanism (which timeout? which retry? where does the job go on failure?).
- "It's idempotent." → say what makes it so (key? natural idempotence? dedupe row?).
- "We'll add monitoring." → monitoring is detection, not recovery (Q3 still needs an answer).
- "We'll retry." → with what idempotency story, how many times, over what deadline (I8)?
- "It's a small service / it won't get that much traffic." → volume is a measurement, and the failure
  class doesn't care about team size.
- "That's never happened." → the question is what happens *if*, not what has happened.

---

## Cross-cutting semantics

- **"Exactly once" effects require an end-to-end mechanism.** Broker delivery alone does not provide
  them across an external side-effect boundary. At-least-once delivery plus effect-level idempotency or
  reconciliation is common; at-most-once accepts loss. Ask which component honors the dedupe key and
  what happens after a commit succeeds but its acknowledgement is lost.
- **Partial success needs an accounting model.** Either one unit-of-work (commit or rollback together,
  I7), or per-item results with a recorded state, or a compensating action with its own idempotency.
  "Some succeeded" without a record of which is the worst of the three.
- **Timeouts form a hierarchy.** Each inner operation and retry budget fits within the remaining outer
  deadline; an inherited deadline can serve multiple calls. Otherwise retries stack past the caller's
  patience exactly when it matters.
- **Detection is not recovery.** Every scenario needs both as separate answers: the alert that shows the
  failure (detection) and the mechanism or runbook that restores service (recovery).

## Worked mini-example (how to actually use this)

For a worker that processes payments from a queue, the *relevant* subset is: Q2 (runs twice → double
charge), Q3 (dies halfway → charge applied, job not acked), Q7 (two workers race → double charge),
Q8 (queue growth → backlog SLA), Q13/14 (retry policy). Q9 (disk full) barely matters; Q6 (malformed
data) matters at the JSON boundary only. Answering five questions well beats reciting fourteen:

> **Q2:** Each job has a stable key passed to a payment provider that honors idempotency for charges;
> `payment_dedupe` records local intent and the confirmed outcome. **Q3:** If the worker crashes after
> the charge but before recording success or acking, redelivery uses the same provider key or queries
> the provider to reconcile the unknown result. The local DB row alone cannot prove whether the charge
> happened. **Q7:** Claim is a conditional update on the job row; the provider key also protects against
> overlap after lease expiry. **Q14:** Retry only with that key and a bounded policy; send unresolved
> outcomes to reconciliation rather than issuing a fresh charge.

That is a failure review. The full checklist dump is not.

Record the answers using the [failure-review template](../templates/failure-review.md) — scenario →
trigger → detection → state at failure → recovery → residual risk — and feed unresolved gaps into
[production-readiness](../templates/production-readiness.md) as conditions.
