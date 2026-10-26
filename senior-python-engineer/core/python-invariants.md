# Python Invariants

## Contents

- [Validation and trust boundaries](#validation-and-trust-boundaries)
- [Lifecycle and resources](#lifecycle-and-resources)
- [Concurrency and state](#concurrency-and-state)
- [Data and persistence](#data-and-persistence)
- [Performance](#performance)
- [Architecture](#architecture)
- [Failure behavior](#failure-behavior)
- [Secrets and generated code](#secrets-and-generated-code)
- [Using these in reviews](#using-these-in-reviews)

Guardrails, not commandments. Each invariant states its strength (**MUST** / **SHOULD** / **CONSIDER**),
its rationale, and its legitimate exceptions. MUST means a correctness or safety requirement when its
preconditions apply; SHOULD is a default with escape conditions; CONSIDER is a judgment call. These
labels do not determine a review finding's severity.

These are engineering invariants derived from Python semantics, CPython behavior, specifications, and
production experience. Where an invariant is engineering judgment rather than a language rule, it says so.
Layer tags: [LANGUAGE] [CPYTHON] [STANDARD] [FRAMEWORK] [ECOSYSTEM] [HEURISTIC] — see
[SKILL.md](../SKILL.md#knowledge-classification).

## Validation and trust boundaries

### I1 — External data crosses an explicit validation boundary · **MUST**
Data from network, storage, files, user input, or inter-service calls crosses a validation/normalization
boundary appropriate to its contract and risk; downstream code consumes known shapes. This can be a
schema, parser, database constraint, or explicit check rather than a second validation library.
- **Rationale:** static annotations are not runtime validation [STANDARD]; type hints are metadata for
  static tooling. Unvalidated data corrupts state silently and is a security surface.
- **Exceptions:** internal data already guaranteed by the same contract; throwaway scripts where a
  malformed input can only fail that run. Do not duplicate checks already enforced at the boundary.
- See [typing.md](../references/typing.md), [security.md](../references/security.md).

## Lifecycle and resources

### I2 — Resource lifetimes are explicit · **MUST**
Files, sockets, connections, locks, transactions, subprocesses, and sessions are released by explicit
lifecycle constructs (context managers, `aclose`, `finally`, structured scopes), not by garbage-collection
timing.
- **Rationale:** Python does not guarantee deterministic collection [LANGUAGE]; CPython's refcounting +
  cyclic GC is [CPYTHON] behavior. Relying on `__del__` or prompt close-on-GC is implementation-dependent.
- **Exceptions:** process-lifetime singletons released at shutdown via registered handlers; memory-only
  objects with no external resource.

### I3 — Import-time behavior stays cheap and predictable · **SHOULD**
Module import executes top-level code [LANGUAGE]; importing must not open network connections, read
large data, mutate global hardware/env state, or perform environment-dependent work beyond declaring
constants, types, and registration that is itself cheap and side-effect-controlled.
- **Rationale:** imports are application initialization; unpredictable import side effects break testing,
  multiprocessing, tooling, and startup reliability.
- **Exceptions:** deliberate lazy caches initialized on first use; plugin registries that are pure
  registration; `__main__`-guarded scripts.

## Concurrency and state

### I4 — Shared mutable state has explicit ownership and synchronization · **MUST**
Mutable state accessed concurrently across threads/tasks/processes has an owner and a synchronization
or confinement strategy where conflicting access is possible (lock, queue, single writer, immutable
snapshot). Separate process memory is not shared state unless an IPC/shared-memory mechanism connects it.
- **Rationale:** optional free-threaded CPython removes a lock, not data races [CPYTHON]. Do not infer
  compound-operation atomicity from individual container operations or from the GIL. A state transition
  confined to one event loop, with no suspension, re-entrant callback, or external-thread access, cannot
  interleave with another task on that loop; verify those conditions before calling it a race.
- **Exceptions:** genuinely immutable values; per-request/task confined state; state behind a concurrency-
  safe primitive whose guarantees are documented by its library.

### I5 — No blocking operation on an asyncio event loop · **MUST**
Blocking calls (sync I/O, `time.sleep`, CPU-heavy loops, sync drivers) never run directly in async
coroutines on the request path; use async-native APIs, bounded thread offload, or another execution model.
- **Rationale:** one blocking call stalls every coroutine on the loop [FRAMEWORK] (FastAPI/Starlette and
  every ASGI server share this model).
- **Exceptions:** tiny nonblocking CPU work (constant-time-ish) with a measured upper bound; startup-time
  blocking work before the loop serves traffic.

### I6 — Cancellation and deadlines propagate · **MUST**
Timeouts and cancellation reach the actual I/O and are not swallowed (for example by bare `except`,
`except BaseException`, or converting `CancelledError` into a normal result). On supported Python,
`asyncio.CancelledError` is a `BaseException`; `except Exception` does not catch it, although it can
hide the caller-facing `TimeoutError` or other failures. Tasks have an owner, an admission/capacity policy
where work can grow, and a completion or shutdown path. `TaskGroup` owns child lifetimes and usually
groups ordinary failures; it does not bound task count. Use `except*` to handle matching group members,
or handle/propagate the group as a whole. A semaphore limits holders, not tasks waiting to acquire it.
Default `gather` propagates an early child exception without cancelling siblings. Retain and finish or
cancel-and-await those siblings according to the required result contract; a timeout wrapper alone does
not supply that ownership. See [asyncio semantics](../references/asyncio-concurrency.md).
- **Rationale:** swallowing `CancelledError` breaks asyncio timeout and task-group semantics [FRAMEWORK];
  unowned or unmanaged background tasks leak execution, memory, and database connections.
- **Exceptions:** deliberate bounded shutdown/cleanup that preserves the caller's cancellation intent;
  owned long-lived workers can outlive a request when their shutdown and failure reporting are defined.

## Data and persistence

### I7 — Transaction/session scope is visible at the use-case boundary · **MUST**
The unit-of-work boundary (what commits or rolls back together) is visible to the use case. For
SQLAlchemy specifically, a `Session` must not be shared across concurrent threads and an
`AsyncSession` must not be shared across concurrent tasks [FRAMEWORK]. Furthermore, connection pools
or initialized `Engine` objects must never be shared across process `fork()` boundaries without
re-creation or `engine.dispose(close=False)` [CPYTHON/FRAMEWORK].
- **Rationale:** hidden transaction scope produces phantom commits, partial writes, and connection leaks;
  SQLAlchemy's unit-of-work model explicitly forbids concurrent sharing; forked connection pools duplicate
  underlying socket file descriptors, causing corrupted protocol streams and race conditions.
- **Exceptions:** transaction scope can live in a called unit-of-work abstraction when the caller can
  see which operations commit together; nested/reduced scopes are fine when named. No exception for
  concurrent sharing of a SQLAlchemy session or un-disposed forked connection pools.

### I8 — Retries require idempotency analysis · **MUST**
Before any retry: answer "can this operation safely happen twice?" Non-idempotent operations need an
idempotency mechanism honored where the effect occurs, a reconciliation/compensation design, or no
automatic retry. Retries have a bound (attempts, elapsed time, or enclosing deadline); use backoff and
jitter when immediate retries would worsen contention or load. In PostgreSQL, a statement error aborts
the transaction block (`25P02`) until rollback. Retry serialization (`40001`) or deadlock (`40P01`) by
re-running the whole unit of work after rollback, never the failed statement [STANDARD]
([persistence](../references/persistence.md)).
- **Rationale:** naive retry converts timeouts into double charges, double emails, corrupted counters.
  Statement-level retries inside an aborted PostgreSQL transaction always fail.
- **Exceptions:** naturally idempotent reads/PUT-style calls with bounded retry budgets.

## Performance

### I9 — Optimization follows measurement · **SHOULD**
Performance changes follow the evidence ladder (workload → measure when possible → classify →
algorithm/data access → batch/vectorize/cache → runtime/native boundary). Language rewrites and native
extensions proposed for speed require representative evidence and a stated target.
- **Rationale:** dominant cost in Python systems is frequently not the interpreter (I/O, DB, serialization,
  native kernels); premature native/rewrite work adds build/ABI/maintenance cost with unknown payoff.
- **Exceptions:** an obvious local algorithmic improvement may be justified by complexity analysis and
  a representative test; before a system exists, use workload estimates and a review trigger instead of
  inventing a profile. See [evidence-rules.md](evidence-rules.md).

## Architecture

### I10 — Framework conventions remain local · **MUST**
Framework lifecycle rules ([FRAMEWORK] — Django ORM async caveats, Flask worker-tied async, FastAPI
dependency model, SQLAlchemy session rules) are applied where that framework runs, and are never
generalized into universal Python architecture rules or imposed on framework-free code.

### I11 — Indirection pays rent · **SHOULD**
Every abstraction layer (repository, service, DI container, plugin, event bus) names the problem it
solves and the cost it adds; removing a layer must create a named problem.
- **Rationale:** indirection without a consumer is ceremony; it taxes every future reader
  ([anti-patterns](../catalogs/anti-patterns.md)). Conversely, refusing a service or domain boundary
  when multiple entrypoints (e.g. HTTP endpoint, background worker, CLI script) execute identical
  multi-step transactional workflows is under-engineering, creating split-brain logic and transaction leaks.
- **Exceptions:** a forward-looking boundary can pay rent when a concrete near-term consumer, enforced
  contract, or high-cost future change justifies the present indirection; record why
  ([ADR](../templates/architecture-decision-record.md)).

### I12 — Dependency additions justify themselves · **SHOULD**
New dependencies state: what they replace, maintenance/health, license, transitive weight, security
surface. The repo's existing stack is preferred absent a concrete gap.
- **Rationale:** dependency surface is attack surface and upgrade debt ([dependency-review](../reviews/dependency-review.md)).

## Failure behavior

### I13 — Failure behavior is visible · **MUST**
Exceptions are caught where the caller can recover, translate, retry, record, or deliberately isolate.
Silent broad exception handling (`except Exception: pass`-style) is a defect; top-level job boundaries
that record failure and isolate a unit of work are correct.
- **Rationale:** swallowed errors convert defects into silent corruption.
- **Exceptions:** best-effort telemetry/cleanup paths that must not mask the primary error (and that log).

### I14 — Failure questions get answered at boundaries · **SHOULD**
At every external boundary (DB, API, queue, disk, process), the design answers the relevant "what happens
if…" questions: disappearance, duplicate execution, mid-task death, timeout, malformed response, race,
unbounded growth, full disk, schema change, partial success, cancellation residue
([failure-modes.md](../catalogs/failure-modes.md)). Ask the relevant subset; do not dump the list.

## Secrets and generated code

### I15 — Secrets never enter code, logs, or diffs · **MUST**
Credentials come from a configuration/secret boundary; they are not hardcoded, logged, serialized into
artifacts, or echoed in errors. Generated code touching auth, secrets, subprocesses, serialization, or
SQL is reviewed as untrusted proposed code ([principles §5](engineering-principles.md)). Compare tokens,
MACs, and digests with `secrets.compare_digest` or `hmac.compare_digest` [STANDARD] so equality does not
short-circuit on content; different lengths can still leak length, and password checks belong to the
hasher's verify API. Subprocesses avoid shell injection. Dynamic SQL binds parameters at runtime;
`typing.LiteralString` (PEP 675) only checks statically that query text came from literals
[STANDARD].

### I16 — "Pythonic" means readable and predictable · **CONSIDER**
Clever compression (nested comprehensions doing real work, metaprogramming, import tricks) needs a
readability payoff. Readability is not a style preference — it is the maintenance interface of the code.
PEP 8/PEP 20 are informational [STANDARD]; local repo style outranks personal preference.

---

## Using these in reviews

Grade findings by plausible impact and reachability in this system, with evidence; rule strength is a
reason to investigate, not a severity score. A reachable double charge may be High or Critical, while
a harmless validation omission in a disposable script may not be a finding. SHOULD and CONSIDER items
likewise need a concrete consequence before becoming findings. Use the finding format in
[templates/code-review.md](../templates/code-review.md); "No significant issue found." stays valid —
do not invent violations.
