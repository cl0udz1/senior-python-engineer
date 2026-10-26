# Anti-Pattern Catalog

## Contents

- [State and lifecycle](#state-and-lifecycle)
- [Failure handling](#failure-handling)
- [Async and concurrency](#async-and-concurrency)
- [Data access](#data-access)
- [Testing](#testing)
- [Architecture](#architecture)
- [Caching and performance](#caching-and-performance)
- [Fast triage](#fast-triage)

Implementation-level smells with detection and remediation. **A smell is not automatically a defect.**
Each entry gives you the mechanism so you can decide whether the risk is real in *this* codebase; the
"acceptable exceptions" line exists precisely because most of these patterns have legitimate uses.

Usage rules:

- Detect → verify the mechanism is actually reachable/harmful here → then decide. A catalog hit is a
  question, not a finding.
- Findings follow the priority order from [SKILL.md](../SKILL.md): correctness → security → data integrity
  → concurrency/state ownership → resource lifecycle → failure behavior → performance → maintainability →
  readability/style. An anti-pattern hit at "readability" never outranks a correctness problem.
- Invariants identify what to inspect; severity follows reachable impact and evidence
  ([core/python-invariants.md](../core/python-invariants.md#using-these-in-reviews)). A smell without a
  concrete consequence can remain advisory or go unreported.
- Remediation options are ordered **cheap → structural**. Do the cheapest step that removes the mechanism.
- Generic vs domain-specific procedure: [Code Review](../reviews/code-review.md), [Failure Modes](failure-modes.md).

---

## State and lifecycle

### 1. Mutable default argument
- **Detection clues:** `def f(x=[])`, `def f(cfg={})`, any `def f(x=<mutable literal>)`; state persists across calls.
- **Mechanism:** the default object is evaluated once at function-definition time [LANGUAGE]; every call that omits the argument shares that one object.
- **Why it matters:** cross-call state leaks are intermittent, order-dependent bugs; tests "randomly" pollute each other.
- **False positives:** immutable defaults (`None`, ints, strings, tuples of immutables) are fine; a `None` sentinel pattern is the fix, not the smell.
- **Acceptable exceptions:** deliberate shared state (memo tables, registries) — but then make it an explicit module-level name, not a hidden default.
- **Remediation (cheap → structural):** 1) sentinel: `def f(x=None): x = [] if x is None else x`; 2) linter rule (ruff `B006`) in CI; 3) if shared state was intended, name it and give it an owner.

### 2. Hidden mutable global
- **Detection clues:** module-level `list`/`dict` mutated by functions; `global x`; singleton with `initialize()` that must be called "somewhere"; tests that must reset global state between cases.
- **Mechanism:** module state is process-wide [LANGUAGE]; every caller shares it, and its lifecycle is implicit (import order, worker fork, test ordering).
- **Why it matters:** hidden ownership of mutable state breaks under concurrency (I4) and makes behavior depend on call history and test order.
- **False positives:** true constants (immutable values), read-only lookup tables built at import.
- **Acceptable exceptions:** caches/registries with a documented single writer and reset path; process-lifetime singletons with explicit init and shutdown hooks.
- **Remediation (cheap → structural):** 1) make the state an argument and return values; 2) encapsulate in a small object/class with a named owner; 3) application factory / composition root that constructs state once and injects it.

### 3. Import side effects
- **Detection clues:** importing a module opens network connections, reads env/config, starts threads, mutates other modules, prints; test collection is slow; `import` in one place changes behavior elsewhere.
- **Mechanism:** imports execute module top-level code [LANGUAGE] — import is application initialization, not declaration (I3).
- **Why it matters:** breaks multiprocessing spawn, test isolation, tooling (linters/importers execute your code), and startup reliability.
- **False positives:** cheap constant/type/class definitions; deliberate registry registration that is pure and fast; `__main__`-guarded scripts.
- **Acceptable exceptions:** lazy caches initialized on first use; plugin entry-point registration that is side-effect-controlled; heavyweight work explicitly moved behind a `create_app()`/`main()` call.
- **Remediation (cheap → structural):** 1) move work into functions called by an explicit entry point; 2) defer with lazy init (`functools.cache` + accessor); 3) composition root that wires dependencies at startup (see [Blueprint](../templates/blueprint.md)).

### 4. Circular imports
- **Detection clues:** `ImportError: cannot import name`; import works only in some orders; local/late imports sprinkled to "fix" it; `import x` at the bottom of a module.
- **Mechanism:** modules execute once and cache [LANGUAGE]; A→B→A means one side runs against a half-initialized module. Symptom of bidirectional domain dependency or too much import-time work.
- **Why it matters:** fragile initialization order; masks a real dependency-direction problem that will keep producing bugs.
- **False positives:** type-checking-only imports (`if TYPE_CHECKING:`) are not runtime cycles; string annotations/forward refs are fine.
- **Acceptable exceptions:** a single localized late import inside a function, commented, where restructuring would cost more than the smell (often plugin/host boundaries).
- **Remediation (cheap → structural):** 1) move the shared names into a third module both can import (extract the contract); 2) invert the dependency (caller passes the dependency); 3) restructure domain modules so dependencies point one way.

### 5. Leaked connections / resources
- **Detection clues:** `open()`/`connect()`/`cursor()`/`Popen()`/`session()` without `with`/`finally`; connection-pool exhaustion warnings; fd counts climbing under load; resource cleanup only in `__del__` or "GC will handle it".
- **Mechanism:** Python does not guarantee deterministic collection [LANGUAGE]; CPython refcounting + cyclic GC is [CPYTHON] behavior. Relying on destruction timing leaks on cycles, tracebacks holding references, and other interpreters (I2).
- **Why it matters:** leaked sockets/connections/locks exhaust pools and deadlock under load — a production outage class, not a style issue.
- **False positives:** process-lifetime resources deliberately held until shutdown (a module-level engine/pool with a shutdown hook).
- **Acceptable exceptions:** memory-only objects with no external resource; singletons released via registered shutdown handlers.
- **Remediation (cheap → structural):** 1) wrap in `with`/`contextlib.closing`/`async with`; 2) `try/finally` where a context manager doesn't fit; 3) make the owning object itself a context manager; 4) leak-detection test (fd/pool counts) at the boundary that matters.

### 6. Swallowed cancellation / unsafe cancellation
- **Detection clues:** bare `except:` or `except BaseException: ... return` around `await`; explicit `CancelledError` converted to a normal result; tasks spawned without an owner or shutdown path.
- **Mechanism:** asyncio cancellation arrives as `CancelledError`, a `BaseException`; `except Exception` does not catch it on supported Python. Suppressing it breaks `TaskGroup`/timeout semantics and leaves half-completed state (I6).
- **Why it matters:** timeouts stop working, shutdown hangs or leaks tasks, and partial writes survive cancellation with no owner.
- **False positives:** a top-level worker boundary that records the failure and isolates one job (I13) — provided it re-raises or exits, not silently continues the cancelled scope.
- **Acceptable exceptions:** deliberate shutdown drain paths with a bounded deadline that record-and-complete; `finally` blocks that clean up and re-raise.
- **Remediation (cheap → structural):** 1) re-raise `CancelledError` if deliberately caught; distinguish `TimeoutError` at the caller from ordinary failures; 2) give tasks an owner (`TaskGroup` or owned worker); 3) define shutdown with a deadline ([Failure Modes](failure-modes.md) §process lifecycle).

## Failure handling

### 7. Broad exception swallowing
- **Detection clues:** `except Exception: pass`; `except: ...`; catching at a layer that cannot recover; log message without the exception (`log("failed")` instead of `log.exception`); error return values ignored.
- **Mechanism:** the handler converts a detectable defect into a silent continuation, often with partially updated state (I13).
- **Why it matters:** corruption propagates; incidents become un-debuggable ("it just stopped working"); masks the original failure class.
- **False positives:** legitimate translation layers (`except KeyError: raise ValueError(...) from e`); per-item isolation in batch jobs where the loop must continue.
- **Acceptable exceptions:** top-level job/request boundaries that record the failure with full context and isolate a unit of work; best-effort cleanup/telemetry paths that log and do not mask the primary error.
- **Remediation (cheap → structural):** 1) catch the specific exceptions you can handle; 2) log with context (`exc_info`/`exception`) or re-raise with `raise X from e`; 3) if you truly can't decide locally, let it propagate to a boundary that can (I13).

### 8. Retry-everything
- **Detection clues:** `while True: try: ... except Exception: continue`; retry decorators on non-idempotent writes; no retry cap/backoff/deadline; retries around code that also queues jobs.
- **Mechanism:** "transient error handling" applied without classifying the error or the operation duplicates side effects (double charge, double email, corrupted counters) (I8).
- **Why it matters:** retries convert timeouts into correctness bugs and amplify overload (retry storms).
- **False positives:** naturally idempotent reads/PUTs with a bounded budget; database-level serialization-failure retry of the *whole transaction* [FRAMEWORK].
- **Acceptable exceptions:** operations whose effects are idempotent at the effect boundary or safely reconciled, with a retry budget; use backoff/jitter when repeated attempts would add load.
- **Remediation (cheap → structural):** 1) classify retryable failures; 2) add effect-level idempotency or reconciliation for writes; 3) bound attempts or elapsed time and back off when useful; 4) quarantine poison items instead of retrying indefinitely ([Failure Modes](failure-modes.md)).

## Async and concurrency

### 9. Blocking call in async handler
- **Detection clues:** sync DB driver / `requests` / `time.sleep` / file I/O / CPU loop inside `async def`; latency of all endpoints rises together; event-loop lag metrics spike.
- **Mechanism:** one blocking call stalls every coroutine on the loop [FRAMEWORK] — the async-sandwich problem (I5).
- **Why it matters:** an "async" service performs worse than sync under load; failures look like random timeouts.
- **False positives:** tiny constant-time CPU work with a measured upper bound; blocking work at startup before the loop serves traffic.
- **Acceptable exceptions:** bounded `run_in_executor`/`to_thread` offload for genuinely short blocking calls, with the pool size treated as a capacity limit.
- **Remediation (cheap → structural):** 1) swap in the async-native client/driver; 2) bounded thread offload; 3) move the work to a worker/queue outside the request path; 4) if the stack is mostly blocking, reconsider async entirely ([Decision Model](../core/decision-model.md) §1).

### 10. Unbounded task spawning
- **Detection clues:** A growing producer creates tasks faster than they finish; pending tasks, buffered items, or resource holders have no bound. Check admission separately from the presence of `gather`, `TaskGroup`, or a semaphore.
- **Mechanism:** task creation rate exceeds completion rate → memory growth, race on shared state, tasks lost at shutdown (I4, I6).
- **Why it matters:** the classic asyncio production failure: throughput optimism with no backpressure; work silently vanishes on crash.
- **False positives:** a fixed small number of long-lived tasks created at startup and awaited at shutdown; truly bounded finite fan-out (e.g. 5 known tasks).
- **Acceptable exceptions:** A small, explicitly bounded input set; or bounded producer admission plus owned tasks and a resource limit sized to capacity. A semaphore inside arbitrarily many created tasks does not bound the waiting-task population.
- **Remediation (cheap → structural):** Own and await task lifetimes; bound creation with a producer window or bounded queue and fixed consumers; use a semaphore for scarce-resource holders when needed. Move to external workers only when durability or independent scaling justifies them, with admission and backpressure still defined.

### 11. Unbounded queue
- **Detection clues:** `asyncio.Queue()` / `queue.Queue()` with no `maxsize`; producer rate metric but no queue-depth metric; "buffering" with no admission policy.
- **Mechanism:** without a bound, latency hides failure: the queue absorbs overload until memory dies, then everything dies together.
- **Why it matters:** unbounded buffering converts a spike into an outage and destroys any latency SLO; every queue needs an answer for "producer faster than consumer" ([Failure Modes](failure-modes.md)).
- **False positives:** queues bounded by a finite upstream input or a real admission limit (for example, explicit `maxsize`); batch pipelines whose total input is finite and known. One item per request is unbounded if requests are unbounded.
- **Acceptable exceptions:** offline batch ingestion where growth is monitored and disk-backed, with a documented capacity story.
- **Remediation (cheap → structural):** 1) set `maxsize` and decide the overflow policy (block, reject, drop-oldest); 2) monitor queue depth; 3) admission control at the producer; 4) scale consumers or shed load.

### 12. Shared SQLAlchemy Session across threads/tasks
- **Detection clues:** module-level `Session()`/`session` passed into threads or `asyncio.gather` blocks; `AsyncSession` used from concurrent tasks; intermittent `InterfaceError`/weird identity-map results under load.
- **Mechanism:** a Session is a unit-of-work/identity-map object, not a connection handle; SQLAlchemy's model is Session-per-thread, AsyncSession-per-task, and concurrent sharing is explicitly unsupported [FRAMEWORK] (I7).
- **Why it matters:** interleaved transactions, corrupted identity maps, connection-level errors under concurrency — no legitimate use.
- **False positives:** a single-threaded worker owning one session per job; `scoped_session` used as designed (still per-thread).
- **Acceptable exceptions:** none for concurrent sharing (per SQLAlchemy's own model). Sequential reuse within one thread/task/unit of work is normal.
- **Remediation (cheap → structural):** 1) create a session per request/task/unit of work and close it in the boundary; 2) move session ownership to the use-case boundary where the transaction is visible (I7); 3) for concurrency, fan out with per-task sessions and merge results outside the ORM.

## Data access

### 13. ORM-in-loops (N+1)
- **Detection clues:** attribute access on relationships inside `for` loops; query log grows linearly with row count; endpoints that slow down as data grows; "the ORM is slow" complaints with no query count.
- **Mechanism:** lazy loading emits one query per access [FRAMEWORK]; object traversal hides SQL round trips.
- **Why it matters:** latency scales with N; database load multiplies; often misdiagnosed as "Python is slow".
- **False positives:** deliberate small bounded relationship fetch (e.g. at most 3 related rows) where a join would obscure the query; N=1 cases.
- **Acceptable exceptions:** admin scripts over tiny fixed datasets; one-off migrations where runtime is irrelevant.
- **Remediation (cheap → structural):** 1) count the queries first (echo/`sqlalchemy` event logging) — prove the N+1; 2) eager/select-in loading or explicit join for the access pattern; 3) bulk query + manual mapping for reporting paths; 4) pagination so N is bounded.

## Testing

### 14. Excessive mocking
- **Detection clues:** test file has more mock configuration than assertions; `MagicMock()` return values re-specify implementation internals; tests pass while integration is broken; renaming a private method breaks dozens of tests.
- **Mechanism:** the test asserts the mock arrangement, not behavior — it verifies the code does what the test author already believed (see [smells](smells.md) "tests as specification of implementation").
- **Why it matters:** high maintenance cost, low confidence; the actual risk (DB queries, serialization, migrations, external contracts) stays untested.
- **False positives:** isolating genuinely unreachable error paths (timeouts, disk-full); boundary doubles for slow/unstable third parties; fast unit tests for complex pure logic.
- **Acceptable exceptions:** testing failure injection at stable boundaries (a port/protocol with a fake); subprocess/network exclusion in unit-tier tests where an integration tier covers the real boundary.
- **Remediation (cheap → structural):** 1) prefer fakes at stable boundaries over mocks of internals; 2) add integration/contract tests for the risky boundaries and delete redundant mock tests; 3) cap mocking to the boundary line (mock the network, not your own service layer).

## Architecture

### 15. Excessive dependency injection
- **Detection clues:** DI container/configuration for a system with one implementation per interface; constructor parameter explosion of abstractions; "for testability" where tests never swap implementations; indirection spend in reviews.
- **Mechanism:** object-graph variability is assumed rather than observed; every call site pays navigation cost (I11).
- **Why it matters:** slows every future change; newcomers can't find actual behavior; the pattern is imported from ecosystems with different constraints (Java/C#) [HEURISTIC].
- **False positives:** plugin systems; genuinely interchangeable infrastructure (two stores, two transports); multi-tenant wiring; large teams with ownership boundaries.
- **Acceptable exceptions:** DI framework already established in the repo and paying for itself (respect local conventions); a small explicit constructor-injection convention without a container.
- **Remediation (cheap → structural):** 1) plain parameters — pass the concrete collaborator; 2) default arguments for the common case; 3) construct at the composition root and pass down; reserve interfaces for the second real implementation.

### 16. Unjustified repository/service layers
- **Detection clues:** `Repository` class that wraps exactly one ORM model with no added logic; `Service` that forwards to one repository call; three files where one function would do; "Clean Architecture" cited as the reason.
- **Mechanism:** layering around an already-clean ORM/API adds indirection without isolation (I11); the layer has no second consumer and no policy of its own.
- **Why it matters:** every change touches 4 files; the abstraction hides transaction boundaries (violating I7's spirit) and invites cargo-cult layering.
- **False positives:** a service that genuinely orchestrates multiple collaborators with transaction/permission boundaries; a repository adding query logic, caching with semantics, or a second backend.
- **Acceptable exceptions:** team-ownership boundaries with a real second consumer (contract signed); test strategy that needs the seam and names it.
- **Remediation (cheap → structural):** 1) inline pass-through layers into the caller; 2) keep the module split (files) without the class ceremony; 3) if a boundary is planned, record why in an [ADR](../templates/architecture-decision-record.md) with a review trigger.

### 17. Premature microservices
- **Detection clues:** service split with shared database; synchronous call chains across 3+ services for one request; distributed tracing needed to debug a monolith-sized domain; team of one deploying five services.
- **Mechanism:** a module-boundary problem is converted into a distributed-systems problem: partial failure, network partitions, dual writes, version skew enter for free.
- **Why it matters:** reliability, latency, and operational cost multiply while the promised independence (separate deploy/scale/ownership) doesn't exist ([Decision Model](../core/decision-model.md) §3).
- **False positives:** real independent ownership/deploy/scale/fault domains; a team that genuinely ships on different cadences; a component with a different runtime/SLA.
- **Acceptable exceptions:** hard security/isolation boundary; genuinely different scaling profile measured; regulatory separation.
- **Remediation (cheap → structural):** 1) module boundaries inside a modular monolith with a shared deploy; 2) extract one service only where the constraint is named and measured; 3) if already split, consolidate where failure semantics dominate ([migration-plan](../templates/migration-plan.md)).

### 18. False abstraction
- **Detection clues:** base class with one subclass; interface with one implementation "for the future"; `AbstractThingFactoryBuilder`; wrapper functions that add nothing; generics used once.
- **Mechanism:** abstraction is added before the variation it abstracts exists; the cost is paid now, the benefit is hypothetical (I11).
- **Why it matters:** navigation tax on every reader; the wrong axis of variation is usually chosen (future-proofing guesses wrong).
- **False positives:** typing-only `Protocol` for a third-party type you don't control (cheap); abstraction with a concrete near-term second consumer that's committed.
- **Acceptable exceptions:** public library API stability requirements; shared contract module preventing a known circular dependency.
- **Remediation (cheap → structural):** 1) inline to the single concrete implementation; 2) wait for the second use, then abstract *from* the two real cases; 3) keep the contract as a Protocol if typing value remains.

### 19. Excessive inheritance
- **Detection clues:** hierarchy >2 levels deep; overriding that must know parent internals; `super()` chains that need a diagram; "template method" used for reuse, not substitution.
- **Mechanism:** inheritance couples the child to parent implementation [LANGUAGE]; C3 MRO is deterministic but doesn't make deep hierarchies comprehensible. Reuse-via-inheritance is the wrong axis (composition is).
- **Why it matters:** fragile base class problem — parent changes break distant children; LSP quietly violated.
- **False positives:** genuine substitutable subtypes (LSP holds, "is-a" survives scrutiny); framework-mandated base classes (Django views, `unittest.TestCase`) [FRAMEWORK].
- **Acceptable exceptions:** shallow (1-level) inheritance of true variants; mixin use where the MRO stays trivial and documented.
- **Remediation (cheap → structural):** 1) extract shared behavior into functions/composed helpers; 2) replace is-a-reuse with has-a composition; 3) flatten to a strategy/Protocol where call sites need polymorphism ([Decision Model](../core/decision-model.md) §2).

### 20. God module / god class
- **Detection clues:** one module >1k lines owning unrelated concerns; a class with many unrelated public methods; every change routes through it; `utils.py`/`helpers.py`/`common.py` accretion.
- **Mechanism:** no ownership boundary was ever drawn; coupling accumulates around the convenient dumping ground.
- **Why it matters:** merge conflicts, unclear transaction/state ownership, untestable surface; it *is* the architecture debt (see also [smells](smells.md)).
- **False positives:** a generated module; a cohesive domain aggregate that is legitimately large (e.g. a well-tested parser); `utils` that is genuinely one concern.
- **Acceptable exceptions:** single-file utilities and scripts where splitting adds navigation cost with no reuse.
- **Remediation (cheap → structural):** 1) extract by change-cause (things that change together live together); 2) split by domain concept, not by technical layer; 3) shrink the public surface first — private helpers can wait.

### 21. Scattered configuration
- **Detection clues:** `os.environ[...]` / `os.getenv` sprinkled across modules; config read at call time with different defaults per site; tests monkeypatching env vars globally; behavior depends on import order.
- **Mechanism:** configuration becomes an implicit, distributed, mutable global — environment reads *are* behavior.
- **Why it matters:** no single place answers "how is this configured?"; prod/dev drift; validation happens late (or never) (I1).
- **False positives:** small single-file utilities (a couple of `getenv` calls are fine); libraries reading well-known env vars at their documented boundary.
- **Acceptable exceptions:** lazy read at a documented boundary for library settings; per-function overrides that default to a central settings object.
- **Remediation (cheap → structural):** 1) central settings object (validated at startup — [Blueprint](../templates/blueprint.md) observability/config step); 2) pass settings as parameters; 3) fail fast on missing/invalid config instead of silent defaults (see [smells](smells.md) "silent fallback defaults").

### 22. Unsafe pickle / deserialization
- **Detection clues:** `pickle.load(s)` / `pickle.loads`, unsafe YAML loaders, `multiprocessing.Connection.recv()` on untrusted peers, cache/queue payloads unpickled at read; separately, `marshal` on untrusted bytes.
- **Mechanism:** pickle and unsafe object constructors can execute code while loading attacker-controlled data [STANDARD]. `marshal` is also unsafe for untrusted data but is not equivalent to pickle's arbitrary-code execution during loading (I1).
- **Why it matters:** remote code execution for unsafe object deserialization; malformed or untrusted `marshal` data has its own safety risks. Queue/cache files are trust boundaries even when "internal".
- **False positives:** reading a pickle file written by the same code with controlled provenance (internal cache with private permissions); process-internal memoization.
- **Acceptable exceptions:** trusted internal artifacts with controlled provenance *and* file permissions — documented as trusted; joblib-style model caches with checksummed sources.
- **Remediation (cheap → structural):** 1) switch to a data format + schema validation (JSON/msgpack/protobuf + explicit fields); 2) sign/checksum artifacts and verify before load; 3) treat `Connection.recv()` peers as a trust boundary; 4) security review if untrusted data already flowed here ([Security Review](../reviews/security-review.md)).

### 23. Unsafe subprocess / shell usage
- **Detection clues:** `shell=True`; f-strings/`%`-format building command strings; `os.system`; user/config data inside command strings; `Popen` without timeouts; passing `input` without size limits.
- **Mechanism:** shell metacharacter parsing turns data into commands; even without injection, string-built commands break on quoting/whitespace.
- **Why it matters:** command injection (arbitrary execution), plus flaky behavior on filenames with spaces.
- **False positives:** `shell=False` with a proper argument list; static command strings with no data interpolation; deliberate pipeline composition from trusted config reviewed as code.
- **Acceptable exceptions:** genuinely needed shell features (pipes, globbing) over fully trusted, non-interpolated strings — pinned in review, not assembled from data.
- **Remediation (cheap → structural):** 1) argument vector: `subprocess.run(["prog", "--flag", arg], timeout=...)`; 2) allowlist the subcommand/args when input is user-influenced; 3) add `timeout` and bounded output capture (I2); 4) review the call as a trust boundary ([Security Review](../reviews/security-review.md)).

## Caching and performance

### 24. Cache without invalidation semantics
- **Detection clues:** `@lru_cache` on functions with changing results; "we'll add a cache" with no key/TTL/eviction answer; stale-data bugs appearing after caching merges; cache hit ratio never measured.
- **Mechanism:** caching duplicates state; without an explicit invalidation/TTL/ownership model the duplicate diverges from the source of truth.
- **Why it matters:** stale reads are correctness bugs; cache invalidation is a distributed-consistency problem wearing a decorator.
- **False positives:** caching immutable/reference data with a versioned key; disposable derived data where staleness cost is explicitly ~zero.
- **Acceptable exceptions:** best-effort derived data (e.g. UI hint counts) with documented staleness window; memoization of pure functions over immutable inputs.
- **Remediation (cheap → structural):** 1) answer "what is the cost of stale?" and write the TTL/invalidation next to the cache; 2) versioned keys / explicit invalidation hooks; 3) recompute instead if invalidation costs more than recomputation ([Decision Model](../core/decision-model.md) §4).

### 25. Premature native optimization
- **Detection clues:** "rewrite in Rust/Cython/Numba" as the first performance idea; no profile; hot path not yet measured; JIT flags flipped on hope; extension added for a workload that is wait-bound.
- **Mechanism:** the dominant cost in most Python systems is I/O, DB, serialization, or already-native kernels — moving Python to native buys nothing if the interpreter isn't the bottleneck (I9).
- **Why it matters:** native boundaries add build/ABI/CI/debugging/maintenance cost permanently; rewrites are low-reversibility.
- **False positives:** measured interpreter-bound hot loop with a stable boundary and a stated target; numeric loop replaced by vectorization first (that step is cheap and often sufficient).
- **Acceptable exceptions:** profile-proven hot path; latency-critical kernel with a benchmark harness; existing native dependency doing 90% of the work where the last 10% is Python-loop bound.
- **Remediation (cheap → structural):** 1) run the evidence ladder ([Evidence Rules](../core/evidence-rules.md) §3); 2) fix algorithm/data-access/N+1 first; 3) batch/vectorize/cache; 4) only then the native boundary — with before/after numbers and a revert plan ([performance-investigation](../templates/performance-investigation.md)).

### 26. eval/exec on untrusted data
- **Detection clues:** `eval(...)`/`exec(...)` on strings that could carry input; `__import__(user_str)`; `compile()`+`exec` on generated config; `eval` used "just to parse literals".
- **Mechanism:** `eval`/`exec` execute arbitrary Python [LANGUAGE] — input becomes code, the same injection class as `shell=True` (I1).
- **Why it matters:** remote-code-execution surface wherever an external string reaches it; behavior becomes unanalyzable for tooling and reviewers.
- **False positives:** `ast.literal_eval` on bounded, trusted input does not execute arbitrary expressions; codegen over trusted, review-controlled literals. `literal_eval` can still exhaust memory or the C stack on hostile input.
- **Acceptable exceptions:** products whose purpose is code execution (notebooks, expression languages) with an explicit, documented trust boundary and sandboxing proportional to the exposure.
- **Remediation (cheap → structural):** 1) use a data parser with input limits for untrusted input; use `ast.literal_eval` only when its resource use is bounded; 2) explicit dispatch (`match`, dict of handlers); 3) if code execution is genuinely required, move it behind a named trust boundary and review it as security-critical ([Security Review](../reviews/security-review.md)).

### 27. Sync/async bridging hacks
- **Detection clues:** `asyncio.run` inside code that may already be on a loop; `run_until_complete` in async contexts; sync SDK calls hidden in `to_thread` without bounds; `async_to_sync(sync_to_async(...))` ladders; sync and async clients mixed for one dependency.
- **Mechanism:** uncontrolled sync↔async bridges can hide capacity and cancellation semantics — nested-loop errors, blocked loop (I5), or offloaded work continuing after await cancellation (I6). A bounded bridge can be the simplest correct integration.
- **Why it matters:** the async-sandwich problem in slow motion: production behavior depends on which bridge a call happens to cross.
- **False positives:** one deliberate, documented bridge at the outermost layer (a sync SDK behind bounded thread offload).
- **Acceptable exceptions:** framework-provided shims used exactly as documented [FRAMEWORK]; a half-migrated stack with a named removal plan ([migration-plan](../templates/migration-plan.md)).
- **Remediation (cheap → structural):** 1) push the bridge to one layer, one direction only; 2) replace with the dependency's native async/sync API; 3) separate execution models across processes/services instead of nesting them.

### 28. Under-engineered controller / Anemic handler coupling
- **Detection clues:** HTTP route handlers, CLI commands, or background worker callbacks contain 60+ lines of raw SQL, manual transaction handling, multi-step business coordination, and external dispatches; similar transactional workflows are copy-pasted across multiple entrypoints (e.g. API + Celery worker + CLI).
- **Mechanism:** Dogmatic refusal of abstraction under the guise of "simplicity". When business rules and transaction scopes are duplicated across transport handlers, changes in business logic or bug fixes in one entrypoint fail to reach others.
- **Why it matters:** Divergent business rules, transaction boundary inconsistencies, untestable business logic (requires spinning up HTTP or CLI harnesses), and split-brain data corruption.
- **False positives:** True single-consumer CRUD routes where the handler merely translates HTTP request parameters into a single ORM model call.
- **Acceptable exceptions:** Micro-scripts, proof-of-concept prototypes, or single-file tools with zero reuse.
- **Remediation (cheap → structural):** 1) Extract the shared transactional workflow into a cohesive service function or use-case object; 2) Pass the database session/unit-of-work into the service function; 3) Keep transport controllers thin and dedicated solely to protocol translation (HTTP status codes, request parsing, headers).

### 29. Unowned sibling work after gather fails
- **Detection clues:** Default `asyncio.gather` can raise while siblings remain active, with no caller or enclosing scope responsible for finishing them.
- **Mechanism:** An early ordinary child exception propagates without cancelling siblings. Their continued execution may outlive the intended operation; a timeout around the already-failed gather does not fix that ownership gap.
- **Why it matters:** Surviving work can retain resources or commit effects after the caller has moved on. Do not diagnose this by requiring a “Task exception was never retrieved” warning: CPython gather retrieves later child exceptions internally. Observe task lifetime and effects instead ([asyncio reference](../references/asyncio-concurrency.md)).
- **False positives:** A retained sibling is deliberately awaited to provide a required result or fallback; an enclosing supervisor owns its completion and shutdown. Read-only work still needs an owner if its lifetime matters.
- **Acceptable exceptions:** `gather(..., return_exceptions=True)` is suitable when all bounded children should finish and each result/error is inspected; explicit per-task error handling can also preserve the required contract.
- **Remediation (cheap → structural):** First decide whether failure should cancel siblings or preserve a useful result. Use `TaskGroup` for fail-together behavior, catch optional failures inside the child when appropriate, or retain explicit tasks and cancel **and await** unwanted siblings on every exit. Separately bound admission where work can grow; structured lifetime is not a capacity limit.

---

## Fast triage

| Hit | First question | If the answer is "no real risk" |
|---|---|---|
| State/lifecycle entries (1–6) | Who owns and closes the resource? If state is shared, who synchronizes it? | Note and move on |
| Failure handling (7–8) | Which specific failure is swallowed/retried, and what state survives it? | Narrow the handler later |
| Async/concurrency (9–12, 27, 29) | What bounds the concurrency? What is the capacity number? Do sibling tasks leak on error? | Document the bound |
| Data access (13) | How many queries does this path emit at N=1000? | Bound N or leave |
| Testing (14) | What behavior would this test fail on? | Delete/rewrite with the fix that touches it |
| Architecture (15–20, 28) | What named problem does each layer solve? Is multi-entrypoint logic duplicated? | Leave; revisit when the problem appears |
| Config/security (21–23, 26) | Does untrusted data or environment reach this path? | Escalate only on a real trust boundary |
| Cache/performance (24–25) | What is the measured problem and the invalidation/target story? | Do nothing until measured |
