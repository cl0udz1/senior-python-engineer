# Decision Model

## Contents

- [0. The master question](#0-the-master-question)
- [1. Execution model](#1-execution-model)
- [2. Design (functions, classes, structure)](#2-design-functions-classes-structure)
- [3. Architecture](#3-architecture)
- [4. Data](#4-data)
- [5. Types and validation](#5-types-and-validation)
- [6. Performance](#6-performance)
- [7. Packaging and tooling](#7-packaging-and-tooling)
- [8. Deployment](#8-deployment)
- [Quick playbook (summary form)](#quick-playbook-summary-form)
- [For consequential decisions, record](#for-consequential-decisions-record)

Reusable decision engine. Each frame lists signals for the options, the questions that must be answered
before choosing, evidence to collect, and how reversible the choice is. No frame has a universal answer;
the governing question is always *which constraint actually dominates?*

Read the frame that resolves the current choice. Consult [engineering-principles.md](engineering-principles.md)
for conflicting design heuristics or [evidence-rules.md](evidence-rules.md) for consequential evidence claims;
neither is a prerequisite read for every decision.

Legend: **Rev** = reversibility (high = cheap to change later; low = expensive to unwind).

## 0. The master question

1. What constraint dominates this system — correctness risk, latency, throughput, team size, delivery
   speed, operational budget, compliance?
2. What is the simplest correct solution under that constraint?
3. Which complexity below does a *named* constraint actually require?

### Execution classification (do this before choosing any concurrency tool)

- Work is **wait-bound** (network, disk, DB, API calls) or **CPU-bound** (compute, parsing, numeric)?
- How many concurrent waits must one process multiplex? Ten? Ten thousand?
- Are the dominant dependencies natively async? Blocking?
- Is work latency-sensitive per request, or throughput-batched?

```text
What constraint actually dominates?
├── Mostly waiting on I/O?
│   ├── High concurrency AND dominant I/O async-capable → consider asyncio / ASGI
│   └── Otherwise → straightforward sync code; threads may bridge blocking I/O
├── CPU-bound Python work?
│   ├── Algorithm / vectorization / native library can remove the Python loop → do that first
│   └── Not removable → processes; free-threading after compatibility validation; or native component
└── Neither dominates → keep the simplest execution model
```

## 1. Execution model

### Sync vs async

- **Signals for async:** many concurrent waits per process; dominant I/O is async-capable, with any
  blocking dependency isolated behind bounded offload; streaming/WebSocket/SSE interfaces; high
  connection counts where thread-per-connection is too expensive.
- **Signals for sync:** simple request flow; low concurrency; blocking dependencies; CPU-bound handlers;
  small team that would fight async debugging; CLI/batch lifecycle.
- **Risks:** async affects the call chain (one unoffloaded blocking call stalls the loop);
  sync/async bridging adds capacity and cancellation concerns.
- **Must answer:** What dominates the time — wait or CPU? Which hot dependencies are async-native,
  which need bounded offload, and who ensures neither blocks the loop? What is the cancellation/deadline policy?
- **Evidence:** representative request profile or greenfield workload estimate; dependency sync/async
  API surface and offload capacity; measured or projected concurrency requirement.
- **Rev:** medium — the decorator syntax converts cheaply; the dependency graph and test style do not.

### Threads vs processes vs free-threading vs subinterpreters vs external workers

| Option | Use when | Cost |
|---|---|---|
| Threads [CPYTHON] | Blocking I/O parallelism; integrating sync libraries; shared in-memory cache/structures | GIL limits parallel bytecode on conventional builds; shared-state discipline required |
| Processes | CPU-bound Python parallelism; crash isolation | Serialization, startup, IPC, memory overhead |
| Free-threaded build [CPYTHON] | CPU parallelism with shared memory, after extension-compat and data-race audit | Check [baseline](../references/modern-python-baseline.md) for status; extensions can re-enable GIL; synchronization remains mandatory |
| Multiple interpreters [STANDARD/CPYTHON] | Isolation of interpreter state within one process | Explicit communication/serialization cost; implementation and package support vary (PEP 734; see [baseline](../references/modern-python-baseline.md)) |
| External workers (queue/sidecar/service) | Work must survive process death; independent scaling; different runtime needs | Operational surface, delivery semantics, failure modes multiply |

- **Must answer:** Is the workload CPU-bound or wait-bound? Does shared mutable state exist, and who owns
  it? What happens when a worker dies mid-unit? (Mechanism detail:
  [asyncio-concurrency.md](../references/asyncio-concurrency.md).)
- **Evidence:** CPU profile; GIL-release behavior of the hot calls; extension compatibility matrix for
  free-threaded builds.
- **Rev:** processes/workers are low-rev once data flows through them.

### asyncio specifics

- Give tasks an owner and completion/shutdown path. `TaskGroup` owns lifetimes and normally cancels
  siblings after an ordinary child failure; it does not bound admission or task count. Bound growing work
  separately ([anti-patterns](../catalogs/anti-patterns.md) §10). Handle grouped failures as a whole or
  use `except*` for selected member exceptions [STANDARD/LANGUAGE].
- Default `asyncio.gather` propagates an early child exception while siblings continue. Use `TaskGroup`
  when that failure should cancel siblings. When a sibling supplies a required fallback, retain and await
  it, or catch the optional failure inside its own task. Explicit cancel-and-await cleanup is another
  valid policy. A timeout wrapper does not clean up siblings after an early exception.
- Preserve cancellation: re-raise `CancelledError`; timeouts must reach the actual I/O.
- Be aware that `asyncio.to_thread` does NOT abort the underlying OS thread on cancellation. If the task is
  cancelled, the thread continues running to completion; releasing locks or semaphores in a `finally` block
  surrounding `to_thread` can cause concurrency limit breaches.
- `asyncio.shield` protects a coroutine from cancellation, but cancellation of the outer task leaves the
  inner task running detached unless explicitly retained and awaited.
- Blocking calls never run on the loop: async-native API, bounded thread offload, or move the work out.
- Full checklist: [async-review.md](../reviews/async-review.md).

## 2. Design (functions, classes, structure)

### Function vs class

- **Class when:** cohesive mutable state with lifecycle, genuine polymorphism at a call site, or a
  protocol implementation. **Function when:** behavior is a transformation; state is passed explicitly.
- **Must answer:** Does this need identity and lifecycle, or just namespacing? If just namespacing, a
  module of functions is enough. A dataclass is a record, not a domain model [HEURISTIC].
- **Rev:** high.

### Composition vs inheritance

- **Inheritance when** a subtype is genuinely substitutable, a framework contract requires subclassing,
  or a small controlled mixin/template hierarchy has a stable extension contract. **Composition** when
  the goal is reuse without that contract.
- [HEURISTIC] Cooperative multiple inheritance via C3 MRO is deterministic [LANGUAGE], but a hierarchy
  needing a diagram to predict attribute lookup is a design defect.
- **Rev:** high if kept shallow; deep hierarchies become low-rev.

### Change locality, duplication, and patterns

- [HEURISTIC] Criteria: [architecture.md](../references/architecture.md) — where a change lands, when a
  duplicate is cheaper than a base class, public surprises, state transitions, and when a pattern earns
  rent. A green test run does not answer these.
- **Must answer:** If this rule changes, which files change? "Every caller that only wanted the outcome"
  means the steps leaked. "A base shared by two rules that change for different reasons" means the
  extraction leaked.
- **Rev:** high while the seam is a function or a small type; low once callers depend on a public hierarchy.

### Protocol vs ABC

- **Protocol [STANDARD]:** structural typing, multiple interfaces, third-party types you don't control,
  typing-only contracts. **ABC:** runtime enforcement of an interface, shared implementation, registries.
- [HEURISTIC] Use a `Protocol` for static structural contracts and an ABC when nominal runtime
  identity, abstract methods, or shared implementation matters; neither is a universal upgrade over
  plain duck typing.
- **Rev:** high.

### Mutable vs immutable modeling

- Immutable by default for values crossing boundaries (records, configs, DTOs). Mutable where in-place
  change is the domain (buffers, accumulators, caches) — with a named owner ([principles §4](engineering-principles.md)).
- Frozen dataclasses/tuples/namedtuples can express shared value intent, but freezing is shallow:
  contained lists or dicts still need immutability or ownership. Specialized tooling is not required.

#### Service abstraction / DI / plugins

- Add a service layer when use-case orchestration spans multiple collaborators with transaction/permission
  boundaries, or when multiple entrypoints (e.g. HTTP API, background worker, CLI command) invoke the same
  business workflow. Add DI when object graphs genuinely vary (plugins, test doubles at stable boundaries,
  multi-tenant wiring). Add plugins when third parties must extend without editing core.
- **Signals against:** single implementation, one call site, "future flexibility" as the only driver.
- ([anti-patterns](../catalogs/anti-patterns.md): unjustified repository/service layers, excessive DI; or conversely, under-engineered handler bloat duplicating domain logic across entrypoints.)

## 3. Architecture

| Option | Add when | Avoid when |
|---|---|---|
| Simple module structure | Small/medium system, one team, one deployable | — (default) |
| Layered API/use-case/persistence boundaries | Multiple interfaces or complex policies share use cases | CRUD straight over ORM with one consumer; a repository layer is not automatic |
| Modular monolith | Module boundaries with shared deployment | — (default before distribution) |
| Hexagonal/ports & adapters | Volatile infra deps, multiple adapters, strong test policy | Boundary exists only conceptually |
| Event-driven | Decoupled producers/consumers, audit trail, fan-out needed | Direct call has simpler failure semantics |
| Queue/worker | Buffering, retries independent of request, scheduling decoupled | Latency-sensitive direct path suffices |
| Microservices | Independent ownership/deploy/scale/fault domains are real | Boundary is conceptual; team shares everything |

- **Must answer:** Which concrete problem does each boundary solve? Who owns which data? What failure
  modes does distribution add (partial failure, ordering, dual writes, tracing)? Is this reversible?
- **Evidence:** team/deploy topology, not blog architecture; measured scaling need.
- **Rev:** module structure high; event-driven/microservices low. Default: modular monolith until a named
  constraint forces distribution.
- Details: [architecture.md](../references/architecture.md), [architecture-review.md](../reviews/architecture-review.md).

## 4. Data

### ORM vs raw SQL

- **ORM when:** entity-centric CRUD, unit-of-work productivity, portability, domain iteration speed.
- **SQL/expressions when:** bulk operations, reporting queries, DB-specific features, tight query-shape
  control dominates. Mixed use inside one system is normal [HEURISTIC].
- **Must answer:** Where is the transaction boundary? Who owns the session? What SQL does object access
  emit (N+1)? ([persistence.md](../references/persistence.md); SQLAlchemy Session model: session-per-thread,
  AsyncSession-per-task, never shared concurrently [FRAMEWORK].)

### Store choice / transactions / caching / idempotency

- Relational by default when data relations and transactions matter; specialized stores earn their ops
  cost with a named workload (document, key-value, search, time-series, queue).
- Transaction scope visible at the use-case boundary; one unit of work = one visible boundary.
- Cache only with defined key, TTL/invalidation, and staleness semantics ("what is the cost of stale?").
- Every write path that can be retried gets an idempotency answer (key, dedupe, or "safe to repeat").
- In PostgreSQL, any statement error aborts the transaction block (`25P02`) until rollback. Serialization
  (`40001`) and deadlock (`40P01`) retries re-run the whole unit of work; other SQLSTATEs are not
  automatically retryable ([persistence.md](../references/persistence.md)) [STANDARD].
- **Connection pool fork safety**: never share an initialized SQLAlchemy `Engine` or database connection pool
  across `fork()` without a child pool reset (e.g. `multiprocessing.get_context("fork").Process(...)`
  on platforms that support `fork`, or Gunicorn `--preload`). File
  descriptors and SSL socket states are duplicated, causing silent stream corruption or concurrent read races.
  Dispose connections post-fork (`engine.dispose(close=False)`) or instantiate pools inside the worker lifecycle.
- **Rev:** store choice low; transaction boundaries medium.

## 5. Types and validation

- Static annotations = static analysis; runtime validation is a separate, explicit step at trust
  boundaries ([typing.md](../references/typing.md)).
- **Where typing pays:** public APIs, shared domain models, libraries, refactoring-heavy code, complex
  call contracts. **Where it pays less:** short-lived internals, throwaway analysis, one-off scripts.
- Tool choice: TypedDict (typed records without behavior), dataclass (records + defaults),
  Pydantic-style models (runtime validation of external data), domain objects (behavior + invariants),
  `Protocol` (structural contracts), generics sparingly where they remove real duplication.
- Strictness (mypy/Pyright strict) is a team policy decision — [HEURISTIC] ramp strictness by module
  boundary, not by grand-bang conversion. `TypeIs`/`TypeGuard`, `Literal`, `Annotated`, `Self`, `NewType`,
  overloads where they prevent actual defects.
- **Must answer:** What defect class does this annotation prevent? What does this validation buy at this
  boundary? If the answer is vague, use simpler annotations.

## 6. Performance

Candidate levers, roughly from local changes to larger commitments; use the measured dominant term,
not this order as a required sequence (details [evidence-rules.md](evidence-rules.md),
[performance.md](../references/performance.md)):

1. Ordinary Python + algorithm/data-access fix, including DB-side aggregation when appropriate.
2. Vectorization/batching (NumPy/pandas/Polars/similar) for numeric loops.
3. Caching (only with invalidation semantics).
4. Concurrency matched to workload (§1).
5. Native/compiled boundary (Numba, Cython, C/C++/Rust via PyO3) — profile-proven, stable boundary,
   build/ABI cost accepted.
6. Offload compute to a specialized engine (GPU/TPU via PyTorch/JAX) when the work belongs there.

- **Must answer:** Where does time actually go (interpreter vs wait vs native kernel vs serialization vs
  network vs DB)? What does the profile say? What is the target number?
- **Rev:** architecture-level moves (native service split) are low-rev. Never start at step 5 because a
  system is "hot" — Python commonly orchestrates already-native kernels [HEURISTIC].

## 7. Packaging and tooling

- **Package vs application:** libraries need API stability, broad dependency ranges, docs, tests against
  supported versions; apps need reproducible lockfile, pinned deploy, operational config.
- **Environment:** standard `pyproject.toml` [STANDARD]; lock strategy explicit (e.g. `pylock.toml` or
  tool-native lock); editable installs for dev only — production reproducibility comes from declared
  deps/artifacts, not developer environments.
- **Frontend (pip/uv/Poetry/PDM/Hatch):** workflow choice, not a standard [ECOSYSTEM]. On existing repos,
  keep the incumbent unless a concrete problem names the migration ([existing-codebase](../playbooks/existing-codebase.md)).
- **Lint/format/type-check:** pick per team/CI needs (e.g. Ruff consolidated lint+format, or Black +
  checker; mypy vs Pyright) — configure once in `pyproject.toml`/CI; don't churn tools for taste.
- **Rev:** high for tooling inside CI; low for published API/dependency contracts.

## 8. Deployment

| Option | Use when | Watch |
|---|---|---|
| Local tool / script | Personal or team utility | Distribution story (venv/pipx/lock) |
| Scheduled process / cron | Batch windows, no service surface | Overlap, locking, alerting on failure |
| VM / bare service | Simple long-running, steady load | Process supervision, graceful shutdown |
| Container | Reproducible deploys, orchestration platform | Image size, startup, probes, signal handling |
| Worker fleet | Queue-based async work | Backpressure, idempotency, poison messages |
| Serverless | Spiky/low-utilization, event-shaped | Cold start, timeouts, statelessness, vendor lock |
| Kubernetes | Platform standard, many services, scale/ops maturity | Probes (readiness ≠ liveness), resource limits, drain |

- **Must answer:** What is the process model (workers per container, threads)? What is the shutdown/drain
  sequence? What are liveness/readiness criteria? What must finish before exit?
- **Evidence:** load shape, latency targets, connection-pool sizes; worker counts are measured, never
  copied from a formula [ECOSYSTEM]. ([deployment.md](../references/deployment.md).)
- **Rev:** container/serverless boundaries are low-rev.

## Quick playbook (summary form)

| Question | Consider X when… | But prefer Y when… |
|---|---|---|
| Sync or async? | Many concurrent waits; dominant I/O async-capable or safely offloaded | Simple, low-concurrency, CPU-heavy or mostly sync deps |
| Function or class? | Stateful lifecycle or polymorphism exists | Pure transformation; no identity |
| Inherit or compose? | Substitutable subtype or required/stable subclass contract | Goal is reuse without that contract |
| Static typing depth? | Shared API, big refactors, invariants, library users | Annotation complexity > defect-prevention value |
| Runtime validation? | Data crosses trust/process/network/storage boundary | Values are already trusted internal objects |
| ORM or SQL? | Entity/unit-of-work productivity dominates | Query shape/bulk/DB features dominate |
| Thread or process? | Blocking I/O / shared in-process resources | CPU parallelism / isolation dominates |
| Queue? | Buffering, independent retries, decoupled scheduling | Direct call preserves simpler failure semantics |
| Cache? | Repeated expensive work + known invalidation semantics | Correct invalidation costs more than recompute |
| Microservices? | Real independent ownership/deploy/scale/fault domains | Boundaries are conceptual; monolith is simpler |
| Native/Rust/C++? | Profile shows a native performance gap, or a concrete safety/interoperability requirement | Python orchestrates already-native libraries; added build cost exceeds benefit |
| Service/domain layer? | Multiple entrypoints (API, worker, CLI) execute shared workflow; cross-entity coordination | Pure single-entrypoint CRUD with no shared business logic |
| Framework? | Removes substantial recurring integration work | Stdlib composition is smaller and clearer |

## For consequential decisions, record

- The dominant constraint and the chosen option.
- Signals that would have flipped the choice ("we'd add a queue if…").
- The evidence backing the choice; the evidence still missing.
- Reversibility and the review trigger (date or metric).
Use [architecture-decision-record.md](../templates/architecture-decision-record.md) when the decision is
expensive to unwind.
