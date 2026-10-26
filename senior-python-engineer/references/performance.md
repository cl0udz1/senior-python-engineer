# Performance

## Contents

- [The measurement ladder](#the-measurement-ladder)
- [Tooling](#tooling)
- [Algorithm and data access first](#algorithm-and-data-access-first)
- [Vectorization and batching](#vectorization-and-batching)
- [Caching](#caching)
- [Native boundaries (measured, not reflexive)](#native-boundaries-measured-not-reflexive)
- [Memory and allocation](#memory-and-allocation)
- [JAX and accelerator benchmarking caveats](#jax-and-accelerator-benchmarking-caveats)
- [Common self-inflicted slowness (cheap to fix, frequent to find)](#common-self-inflicted-slowness-cheap-to-fix-frequent-to-find)
- [Performance review discipline](#performance-review-discipline)

Operational reference for performance work with evidence proportionate to the change. The protocol is
[Evidence Rules §3](../core/evidence-rules.md) — follow it; this file is the tool and technique map.
Invariant I9 ([python-invariants.md](../core/python-invariants.md)): consequential optimization follows
representative measurement; obvious local complexity fixes can proceed from code evidence and a test.
Version-sensitive facts live only in [modern-python-baseline.md](modern-python-baseline.md).

## The measurement ladder

1. Define the workload: real inputs, real data size, real concurrency, production-like dependencies.
2. For a consequential change, measure end-to-end: latency distribution (p50/p95/p99), throughput,
   error rate. Before a system exists, use a workload estimate and review trigger.
3. Attribute the cost: CPU-bound Python vs waiting (I/O, lock, GC, serialization) vs native/kernel time.
4. Analyze memory/allocation if the profile implicates it.
5. Fix the dominant cost with the smallest suitable lever: **algorithm/data access, batching or
   pushdown, vectorization, caching, concurrency, or a native boundary** as evidence warrants.
6. Re-measure against the original numbers; record what moved and what didn't.

Skipping from "it feels slow" to "rewrite in Rust / add async / buy a cache" is the failure this
ladder exists to prevent. A small, obvious algorithmic fix need not wait for every rung.

## Tooling

| Tool | Layer | Use for | Notes |
|---|---|---|---|
| `cProfile` / `profile` | stdlib [LANGUAGE] | Function-level CPU attribution | Instrumentation overhead; fine for coarse hotspots |
| `timeit` | stdlib | Micro-benchmarks of expressions | Beware setup cost and caching artifacts |
| `tracemalloc` | stdlib | Allocation attribution, memory growth | Find leaks/growth, not CPU |
| `py-spy` | sampling profiler [ECOSYSTEM] | Production processes, no code changes | Low overhead; sampling misses short-lived work |
| `Scalene` | Python-aware profiler [ECOSYSTEM] | Python vs native CPU split, memory, GPU | Answers "is time in Python or in the C library?" |

- Tool discipline: profile **production-shaped** workloads; warm up caches/JIT-compilation where the
  runtime has them; watch for observer effects (instrumented profilers change timing); sample in
  production (py-spy) when the lab can't reproduce load.
- Attribution question to answer first: *is the time in Python bytecode, in a native library, or in
  waiting?* Scalene/py-spy answer this; the answer decides the entire strategy below.

## Algorithm and data access first

- The dominant cost of most Python services is **not the interpreter**: it's query counts, serialization,
  network round trips, and algorithmic complexity. A pessimal algorithm in C is still slower than a good
  one in Python for sufficiently large n.
- **N+1 queries** are the classic ORM bottleneck: object graphs fetched per-row inside loops. Detection,
  eager/select-in loading strategies, and ORM-vs-SQL reasoning live in [persistence.md](persistence.md);
  this file just enforces the order — data-access fixes precede any interpreter-level work.
- Complexity wins first: dict/set lookup instead of list scanning (expected `O(1)` vs `O(n)`), avoid rebuilding
  collections per call, hoist invariant work out of loops. These fixes dwarf interpreter micro-opts.

## Vectorization and batching

- Move suitable loops **out of Python** into NumPy/PyTorch/JAX array ops: bulk native work can beat
  N interpreted iterations, but conversion/allocation overhead may dominate small inputs [ECOSYSTEM].
  Measure the complete path. Same principle in the database: set-based
  SQL/`bulk` operations instead of per-row ORM calls ([persistence.md](persistence.md)).
- Batching: amortize per-call cost (network, dispatch, validation) across many items — batched HTTP
  calls, `executemany`, batched inference. Batching adds latency to the first item; bound batch size and
  wait time explicitly ([reliability.md](reliability.md) for queue semantics).
- When Python is **not** slow: PyTorch tensor ops execute in C++/CUDA; JAX programs compile to XLA;
  NumPy ops are native loops. Python is the control plane ([ai-ml.md](ai-ml.md)). "Python is too slow
  for ML" is a banned slogan — the question is where the Python/native boundary sits.

## Caching

- Caching is a correctness decision before a performance one: state the **key, TTL, ownership,
  invalidation, and consistency** semantics first. A cache without an invalidation model is stale-data
  delivery ([Anti-Patterns](../catalogs/anti-patterns.md)).
- Levels: in-process dict (fastest, per-process — inconsistent across workers), Redis/Memcached (shared,
  network cost, serialization), HTTP caching (CDN, `ETag`), computed-property memoization
  (`functools.lru_cache` for pure functions of hashable args — its default `maxsize` is bounded;
  `functools.cache` or `lru_cache(maxsize=None)` can grow without bound).
- Add a performance cache when repeated expensive work is measured or otherwise demonstrated and the
  consistency cost is acceptable. Invalidation options: explicit on write (couples writers), TTL
  (simple, allows staleness), versioned keys (safe, more writes). Choose per data's staleness budget;
  if you can't name the staleness budget, recompute instead.

## Native boundaries (measured, not reflexive)

- Options for a **performance-driven** native boundary when profiling shows interpreter-bound CPU after
  cheaper changes (a security-motivated parser decision has a different evidence test):
  - **Existing array libraries (NumPy/PyTorch/JAX)** when the workload and dependencies already fit;
    include conversion and transfer costs before adding a new stack.
  - **Numba** (JIT-compiled numeric functions) / **Cython** (typed Python→C) for hot numeric loops with
    stable shapes.
  - **C extensions / PyO3 (Rust)** for the lowest-level hot paths — when the boundary is stable and the
    win justifies build, ABI, wheel-matrix, and debugging cost ([packaging.md](packaging.md)).
- A published native boundary adds build toolchains, platform wheels, debugging difficulty, and a
  security surface ([security.md](security.md)). For speed claims, record profile evidence and the
  measured win; a safety or interoperability need has a different evidence test. "Rewrite it in Rust"
  without a named constraint is the banned reflex.
- JIT note: the current CPython JIT is [EXPERIMENTAL] and not a production default
  ([baseline](modern-python-baseline.md)). Benchmark with and without it for experiments; do not infer
  a speedup from its availability.

## Memory and allocation

- Symptoms: RSS growth, GC churn, OOM kills, latency spikes from allocation. Tools: `tracemalloc` (who
  allocates), `gc` module stats (cycle pressure), Scalene (per-line memory), `objgraph`-style ref
  inspection [ECOSYSTEM] for leak hunts.
- Common causes: unbounded caches/queues (see [reliability.md](reliability.md)), accidental retention
  (closures, `__del__` cycles, big lists kept in globals), per-request copies of large data, string
  concatenation in loops (use `join`), loading whole files/tables where streaming/batching would do.
- Memory limits are deployment facts ([deployment.md](deployment.md)): container limits + 10 workers ×
  per-worker RSS is the real math, not one process in a terminal.

## JAX and accelerator benchmarking caveats

- JAX traces Python code into XLA-compiled computations and dispatches asynchronously [FRAMEWORK]:
  - **Compilation time** dominates first calls. Warm up before timing; separate compile cost from
    steady-state.
  - **Async dispatch** means a naive timer measures *enqueueing*, not completion. Block on the result
    (`block_until_ready()` or equivalent device synchronization) before stopping the clock.
- Same class of pitfall everywhere: timing a GPU enqueue, a `submit()` to a pool, or an un-awaited
  coroutine measures the wrong thing. **Measure completion, not submission.**

## Common self-inflicted slowness (cheap to fix, frequent to find)

- Hot-path string building: concatenation in loops (`+=` on strings), `json.dumps` per row where one
  batched dump works; join lists instead.
- Recomputing invariant work per call: regex compilation (`re.compile` once at module level), config
  parsing per request, `datetime.now()`-based recomputation of constants.
- Logging in hot loops: f-string arguments are evaluated even when the level is disabled; use lazy
  logging (`logger.debug("%s", x)`) or guard expensive formatting ([observability.md](observability.md)).
- Membership tests on lists (`x in some_list`) where a set would be O(1) — shows up as unexpected
  hotspots in cProfile on large inputs.
- Per-item serialization round trips in batching code (N small `dumps`/`loads` where the batch API
  exists) — same family as N+1 ([persistence.md](persistence.md)).

## Performance review discipline

- Consequential findings cite measured numbers (before/after, workload described) per
  [templates/code-review.md](../templates/code-review.md). An obvious local complexity defect may be
  supported by code evidence and a representative test. "This looks slow" without either is a
  hypothesis; label it as one (Evidence Rules §5).
- Performance work scales with risk: a batch script tolerates minutes; a request path needs latency
  budgets ([reliability.md](reliability.md)). Define the target before optimizing; without one, "faster"
  has no stopping condition.
