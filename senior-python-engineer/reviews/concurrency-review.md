# Concurrency Review

## Contents

- [Scope & trigger](#scope--trigger)
- [Review contract](#review-contract)
- [Procedure](#procedure)
- [Checklist](#checklist)
- [Questions to ask](#questions-to-ask)
- [Finding format](#finding-format)
- [False positives / legitimate exceptions](#false-positives--legitimate-exceptions)
- [Output expectations](#output-expectations)

Review of threads, processes, and shared state: who owns what, what synchronizes it, and what races
when two workers act at once. Asyncio-specific structure is covered in
[async-review.md](async-review.md); shared-state questions in ordinary diffs land in
[code-review.md](code-review.md).

## Scope & trigger

Use when: code uses `threading`, `concurrent.futures`, `multiprocessing`, process pools, worker pools,
shared caches/globals, queues, locks, or shared memory; a bug smells like intermittent duplication or
lost updates ("works in tests, fails in prod"); free-threaded builds are proposed or in use
(optional supported CPython build with maturing extension support — check [modern-python-baseline.md](../references/modern-python-baseline.md));
or a design moves work between threads/processes ([architecture-review](architecture-review.md) for the
design decision itself).

## Review contract

Follow the shared [review contract](code-review.md#review-contract) for task scope,
priority, severity, evidence, finding format, and a valid clean-review outcome.

## Procedure

1. **Inventory shared mutable state.** Objects accessed concurrently by more than one thread/task, or
   connected across processes through shared memory/IPC: module
   globals, class attributes, caches, session objects, file handles, counters, config. For each, name
   the owner and the allowed mutators ([principles §4](../core/engineering-principles.md), I4).
2. **Identify the synchronization strategy per object**: lock, queue hand-off, single-writer thread,
   actor-style confinement, immutable snapshots, or a primitive whose library documents thread safety.
   "The GIL protects it" is not a strategy.
3. **Find compound operations and reachable interleavings.** Read-modify-write, check-then-act,
   get-or-create, and shared counter updates need an ownership argument (I4). Inspect thread access,
   actual async suspension, callbacks, and reentrancy. A loop-confined sequence with none of those
   interleavings does not require a lock simply because it contains several statements.
4. **Audit lock discipline.** Consistent acquisition order (deadlock), short scope, no unbounded or
   unrelated wait while locked, no lock-in-lock inversion, correct lock per object. An async lock may
   intentionally span an `await` when the protected operation requires it; check cancellation and latency.
5. **Check task/queue bounds.** Worker pools, thread spawns per request, unbounded queues feeding slow
   consumers ([failure-modes](../catalogs/failure-modes.md): "queue grows unbounded").
6. **Check shutdown and cancellation interleaving.** Worker loops exit mid-job; join with timeout;
   daemon-thread reliance; poison-pill protocols; what happens when the process is stopped during work.
7. **Check process/IPC boundaries.** What crosses them (pickle!), what a worker's death does to the
   job in flight, and whether the boundary is also a trust boundary.
8. **Report** in the standard format; route blocking-I/O-only issues to [code-review.md](code-review.md)
   depth and pure-async structure to [async-review.md](async-review.md).

## Checklist

| Check | Mechanism | Evidence to look for |
|---|---|---|
| Shared-state ownership (I4) | Each mutable shared object has an owner or coordinated access policy | Globals/caches mutated from workers without lock or confinement; conflicting writers with no safe strategy |
| Lock discipline | Consistent order, bounded scope, no inversion | Nested locks in varying orders; lock held across slow I/O or awaits without a named invariant and latency bound |
| Race windows | Check-then-act and read-modify-write gaps | `if not in` + insert; `counter += 1` in workers; TOCTOU on files (`exists()` then `open`) |
| Atomicity assumptions | Compound ops assumed atomic | `d[k] = d.get(k, 0) + 1`, multi-step list/dict updates relied on to be atomic; `list.append` atomicity is [CPYTHON], not [LANGUAGE] |
| GIL misconceptions | GIL ⇒ thread safety claimed | Safety arguments resting on the GIL; compound operations "safe because only one thread runs bytecode at a time" — I/O switches happen anyway [CPYTHON] |
| Free-threading claims | Free-threading ⇒ race-free claimed | Code or docs saying no-GIL removes data races; per PEP 779 the optional supported build removes the GIL, not races; incompatible native extensions can re-enable it [CPYTHON] |
| Process/IPC safety | Object payloads sent through `multiprocessing` pipes/queues are pickled; `recv()` auto-unpickles (`send_bytes`/`recv_bytes` use raw bytes) | `Connection.recv()`, `Queue.get()` on data influenced by untrusted input = trust boundary (→ [security-review.md](security-review.md)) |
| Unbounded spawning | Thread/task/queue creation without a bound | `Thread(...).start()` per request/item; unbounded `Queue()` feeding fixed workers |
| Shutdown/cancellation interleaving | Jobs in flight when the worker stops | `while True` loops without a stop condition; `daemon=True` masking shutdown work; no drain step (→ [production-readiness.md](production-readiness.md)) |
| Failure visibility (I13) | Worker exceptions recorded, not dropped | `Future.result()` never read; thread body with bare `except: pass`; pool worker death silently losing a job |
| Retry under concurrency (I8) | Two workers can retry the same unit of work | Retry logic without effect-level idempotency or reconciliation while multiple consumers exist; grade by reachable harm |

## Questions to ask

Ask the subset relevant to this code — do not dump the list:

- What happens if two workers pick up the same job / hit the same key at the same instant?
- Who owns this mutable object, and which thread is allowed to touch it?
- What is the lock acquisition order, and can it ever invert?
- What happens to an in-flight job when the worker dies or shutdown begins?
- Can this queue grow without bound if the consumer slows down?
- What state does this system have that is NOT behind a single owner?

## Finding format

Per [templates/code-review.md](../templates/code-review.md):
`Severity:` `Evidence:` `Why it matters:` `Recommended change:` `Trade-off:` `Verification:`.

Grade by reachable consequence, not the invariant's MUST/SHOULD label
([invariants](../core/python-invariants.md#using-these-in-reviews)). `Evidence:` names the specific interleaving ("two workers pass
the `if not exists` check before either inserts") — a race finding without a concrete interleaving is
an assumption, not a finding.

### Example finding (shape only)

- **Severity:** High
- **Evidence:** `cache/registry.py:22-29` does `if name not in self._entries: self._entries[name] = build(name)`
  from `ThreadPoolExecutor` workers (call sites `api/handlers.py:44`, `worker/pool.py:61`); no lock.
- **Why it matters:** two workers can pass the `not in` check and both call `build()`, publishing
  duplicate entries and double side effects (I4) — the check-then-act window is the race.
- **Recommended change:** guard the get-or-create with a per-name `threading.Lock` (or move creation
  to a single owner thread fed by a queue).
- **Trade-off:** a lock adds contention on the (cold) creation path only; queue hand-off removes the
  race entirely but adds a component.
- **Verification:** a stress test running 32 workers for the same name asserts `build()` runs once
  (counted via a test double) and one entry exists.

## False positives / legitimate exceptions

- **Genuinely immutable values** shared across threads need no synchronization (I4 exception).
- **Per-request/task confined state** that never escapes its worker is not shared state.
- **State confined to one event-loop thread** can be updated without an async lock when the relevant
  operation cannot suspend or re-enter and no outside thread touches it. Verify those assumptions;
  an `await` can introduce a race if it actually suspends.
- **Queue-based hand-off** (`queue.Queue`, `multiprocessing.Queue`) is a documented-safe primitive; do
  not flag it — but do flag unbounded queue growth.
- **Single built-in operations in conventional CPython** may be safe for a narrow access pattern, but
  this is implementation-specific [CPYTHON]. Flag a concrete lost-update/interleaving risk, especially
  for read-modify-write sequences or a free-threaded/portable target; do not demand locks by reflex.
- **Worker pools sized for bounded finite workloads** (a one-shot batch of N items) are fine.
- **Daemon threads for genuinely best-effort telemetry** are acceptable if their loss is acceptable and
  documented.
- **Processes for CPU parallelism** are not a finding for "using pickle internally" when all crossing
  data is self-produced and trusted; the finding starts where untrusted data can reach `recv()`.

## Output expectations

- Lead with the concrete failure the code can produce (lost update, deadlock, unbounded growth), then
  the mechanism, then the fix.
- "No significant issue found." is a valid result — say what was inventoried (which shared state, which
  locks) and what was out of scope. Never invent races to appear thorough.
- Fixes prefer the simplest sufficient mechanism: single-writer confinement or queue hand-off before a
  lock zoo; bounded pools before admission-control architecture.
- Verification of a race fix names how to exercise it (stress test, `pytest -x --count`, targeted
  interleaving test) rather than "reviewed as correct".
