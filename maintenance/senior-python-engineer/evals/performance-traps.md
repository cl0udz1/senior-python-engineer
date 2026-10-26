# Performance Traps

Evidence-first performance work ([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §3 ladder,
I9 in [core/python-invariants.md](../../../senior-python-engineer/core/python-invariants.md)). Every case here has a plausible-looking
optimization that skips the evidence ladder. Routing:
[reviews/performance-review.md](../../../senior-python-engineer/reviews/performance-review.md),
[references/performance.md](../../../senior-python-engineer/references/performance.md),
[templates/performance-investigation.md](../../../senior-python-engineer/templates/performance-investigation.md). Grading per
[expected-behavior.md](expected-behavior.md) — banned slogans in play: "Python is too slow for ML",
"async is faster", "the GIL makes threads useless", "free-threading makes shared state safe".

---

### Case P1 — Premature Rust rewrite

**Input**
> "This Python ML service is slow. Rewrite it in Rust. Users wait seconds for predictions."
>
> The service: FastAPI endpoint → loads a tabular batch → preprocesses with pandas → runs a PyTorch
> model on CPU → post-processes → responds. p95 ≈ 2.1s. We have coarse stage timings but no
> interpreter/native profile. The team says
> "Python is too slow for ML".

**Context**
Per-request shape: ~50 rows, pandas preprocessing ~10ms, PyTorch forward pass ~1.8s on CPU, JSON
serialization ~5ms, DB lookup ~30ms. The model itself is a PyTorch C++/native-kernel workload
(Python is the control plane). Deployment: CPU-only pods today; batch size 1 per request (50 rows
arrive one at a time from the client, so 50 sequential single-row forward passes).

**Desired reasoning behavior**
Profile before prescribing ([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §3 — "rewrite in
Rust/C/C++/Cython/Numba" requires a profile showing interpreter-bound cost in the hot path, a stable
boundary, and a target number). Attribute the cost: the 1.8s is PyTorch native kernel time + 50×
single-row forward passes (batching would amortize); pandas/Python is ~10ms — the interpreter is not
the dominant term. Rust would re-implement the ~15ms of control-plane glue while the model cost stays
exactly where it is ("Python is too slow for ML" is a slogan — PyTorch executes expensive ops in C++
[FRAMEWORK]; JAX traces to XLA). Then the ladder: batch the 50 rows into one forward pass, check
device (CPU vs accelerator), check model cost (quantization/distillation are model questions),
serialization shape — re-measure against a stated target. Rust/Cython/PyO3 only if profiling later
shows interpreter-bound hot loops, with build/ABI/maintenance cost acknowledged.

**Acceptable outcomes**
1. Refuses the rewrite without a profile; walks the cost attribution using the given numbers; recommends batching + measurement first; names exactly what evidence would justify a native boundary (a profile with interpreter-dominant hot path + stable boundary + target number).
2. Same, plus the concrete biggest lever (test one batched forward pass instead of 50 single-row calls; do not assume a 50× speedup) and the measurement plan (py-spy/Scalene/cProfile split of Python vs native time).
3. Same, plus naming what a Rust rewrite would and would not change (control-plane glue: maybe faster; native model kernels: unchanged unless the whole inference stack moves, which is a model-serving decision, not a language one).

**Failure modes**
- Drafting the Rust port plan (or a PyO3 skeleton) as the first deliverable (automatic Rust rewrite).
- "Speed up Python" suggestions at the wrong layer: JIT flag ([EXPERIMENTAL]), micro-optimizing the 10ms pandas part, more uvicorn workers.
- Accepting "Python is too slow for ML" as the diagnosis without question (banned slogan).
- Benchmarking the *Python* function and concluding from it, without separating native-kernel time.

**Critical mistakes**
- Claiming the JIT is a stable fix to enable (invented spec/version fact — "calling the CPython JIT stable" is the canonical example, [expected-behavior.md](expected-behavior.md) §3.4).

---

### Case P2 — Cache without invalidation semantics

**Input**
> "Add caching to make this fast:
>
> ```python
> def get_permissions(user_id):
>     roles = db.query("SELECT role FROM roles WHERE user_id = %s", user_id)
>     perms = expand_roles(roles)          # pure, fast
>     return perms
> ```
>
> It's called on every request and it's 'the hot path' according to everyone."

**Context**
`expand_roles` is pure and fast (~1ms). The DB query is ~3ms. Total ~4ms — not actually slow (no
measurement contradicts this; nobody has profiled). Permissions must reflect role changes within
seconds (revoking access must actually revoke — correctness-critical). Multi-process deployment.

**Desired reasoning behavior**
Two moves. (1) Evidence bar first: "add a cache" requires measured repeated expensive work +
defined invalidation/staleness semantics + hit-rate expectation ([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md)
§3). 4ms of cheap work is not an expensive computation; there is no measured bottleneck at all —
the right first answer is "measure; this may not need optimizing". (2) If caching is still pursued,
the *staleness question dominates*: a permissions cache serves revoked access after revocation —
the cost of stale here is a security property, not a UX nit. A correct design would need explicit
invalidation on role change (event/trigger/TTL bounded by the revocation SLO), per-process coherence
awareness (multi-process = in-process dicts don't cohere), and a stated "cost of stale" analysis.
TTL-only caching may be acceptable **only** if the revocation SLO tolerates it — named explicitly.

**Acceptable outcomes**
1. Asks for/demands measurement first, notes ~4ms is likely fine, and declines caching with the evidence-bar reasoning. Names what would make caching legitimate (measured expensive work + defined staleness budget).
2. Designs a cache only after stating the staleness semantics: invalidation on role change (or TTL bounded by a stated revocation SLO), cross-process invalidation strategy, and the security framing of stale permissions.
3. Redirects to the actual question: is this even hot? Proposes a measurement (trace/counter) and defers the cache decision to the result — decision deferred with a named trigger, not refused.

**Failure modes**
- Adding a module-level dict cache "for speed" with a 5-minute TTL chosen by feel (cache without invalidation model — and in a security-relevant path).
- Caching per process while multiple workers serve traffic, no invalidation story (stale revocations).
- A Redis/memcached platform for a 4ms query (infrastructure ahead of evidence).

**Critical mistakes**
- Presenting stale-permission caching as safe with no staleness/invalidation analysis (unsafe security advice shape + I9).
- Claiming profiling measured the query as the bottleneck when nobody profiled it (fabricated evidence).

---

### Case P3 — Micro-benchmark-driven optimization

**Input**
> "I optimized our report generator! The old loop was slow, so I benchmarked variants with `timeit`:
>
> ```python
> # timeit: this variant won
> def fmt_row(row):
>     return (row["id"], row["name"], row["amount"] / 100, row["ts"].isoformat())
> ```
>
> vs building dicts. It's 40% faster in `timeit`. But end-to-end the report takes the same ~90
> seconds. Where's the speedup going?"

**Context**
The real workload: 200k rows fetched from Postgres (fetch ~55s), formatting in Python (~8s), writing
XLSX with cell-by-cell writes (~25s), email (~2s). `timeit` measured formatting of one synthetic row
repeatedly — pure interpreter micro-cost, hot cache, no I/O.

**Desired reasoning behavior**
Explain why the micro-benchmark lied: `timeit` measured one term (per-row formatting) of a workload
dominated by I/O and library work; Amdahl's shape — 40% of 8s ≈ 3s theoretical, and the measurement
itself (hot-loop, single row, cache-warm) doesn't predict the integrated path. The evidence ladder
applied to *this* workload: measure end-to-end, attribute (fetch 55s DB+network; XLSX 25s library
behavior), then improve the dominant terms (batch/fetch fewer columns, server-side aggregation where
possible, bulk XLSX write API instead of cell-by-cell, or CSV if spreadsheets don't need styling),
re-measure against the target. Micro-optimizations are fine as trivia but must never drive the
optimization plan; state which target number the change was supposed to hit.

**Acceptable outcomes**
1. Explains the gap (micro-benchmark measured one small term; dominant costs are fetch + XLSX writes), proposes fixes at the dominant terms with before/after measurement discipline.
2. Same, plus explicitly reframing the investigation: define the workload and target ("report under 30s?"), then re-profile end-to-end (cProfile/Scalene/tracemalloc as appropriate) and attack the measured top term.
3. Same, plus noting the formatting tweak may be kept (it's harmless) but is recorded as ~3s of 90s — engineering honesty about magnitude.

**Failure modes**
- Insisting the benchmark proves the formatting matters and optimizing further variants (benchmark theater).
- "Rewrite the generator in C/Rust" off the micro-benchmark (layer confusion + automatic rewrite).
- Proposing async for the generator (the waits are DB/XLSX library work; no concurrency requirement stated — "async is faster" shape).

**Critical mistakes**
- Reporting a benchmark number as if it were the measured end-to-end improvement (fabricated evidence).

---

### Case P4 — JAX benchmark measuring enqueueing

**Input**
> "Our JAX preprocessing is blazing fast — 0.2ms per batch per our benchmark. But production p95 is
> 40ms. Something is wrong with the deployment. Benchmark we used:
>
> ```python
> import time
> start = time.perf_counter()
> out = jax.jit(preprocess)(batch)
> elapsed = time.perf_counter() - start
> ```"

**Context**
`preprocess` is jitted; first call compiles. JAX dispatch is asynchronous by default — dispatch
returns before device work completes. The benchmark ran one call, warm-up not separated, no
synchronization before stopping the clock. Production batches vary in shape/size.

**Desired reasoning behavior**
Spot the measurement error by mechanism ([FRAMEWORK], the async-dispatch caveat in
[core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §3): JAX dispatch is asynchronous — without
blocking on the result (`out.block_until_ready()` or equivalent device synchronization), the timer
measures *enqueueing*, not completion; also compilation cost on first call and shape-dependent
recompilation must be separated from steady-state. Production 40ms likely includes sync + real
compute + varying shapes triggering recompiles — measure the same way production executes. Correct
benchmark shape: warm up / separate compile, synchronize before stopping the clock, batch shapes
representative of production, report compile-time and steady-state separately. Then decide whether
40ms is even a problem against a stated target before optimizing (I9). Note: this is JAX-specific
[FRAMEWORK] behavior — do not universalize the sync requirement to all libraries (I10).

**Acceptable outcomes**
1. Diagnoses the async-dispatch measurement flaw (timer stops at enqueue; add `block_until_ready()` / device sync; separate compile from steady state), re-benchmarks realistically, then compares 40ms to the target before optimizing.
2. Same, plus the shape-recompilation hypothesis for production variance (varying batch shapes → recompiles) and how to verify (jit lowering logs / compilation cache stats).
3. Same, plus listing what to check next only if 40ms misses the target (device transfer costs, input pipeline, batch shape padding) — proportional follow-ups behind the measurement.

**Failure modes**
- Blaming the deployment/network/K8s first (the benchmark itself is invalid; no deployment change can reconcile a mis-measured 0.2ms).
- Reporting the fixed benchmark as 50× improvement without production re-measurement (benchmark theater).
- Recommending caching or async to "close the gap" without re-measured evidence.

**Critical mistakes**
- Asserting JAX execution is synchronous and the benchmark is therefore valid (invented [FRAMEWORK] semantics).
- Presenting enqueue-time numbers as completion-time numbers to claim a win (fabricated evidence).

---

### Case P5 — Threads for a CPU-bound loop (and the free-threading follow-up)

**Input**
> Part A: "Our image filter is slow. I wrapped the CPU loop in threads to parallelize it:
> ```python
> def filter_images(images):
>     with ThreadPoolExecutor(8) as pool:
>         return list(pool.map(apply_filter, images))
> ```
> It barely got faster. I thought the GIL makes threads useless anyway — should we use processes, or
> just rebuild Python without the GIL?
>
> Part B (a teammate chimes in): "We could move to the free-threaded build and keep the threads —
> then shared state is safe and it just works, right?"

**Context**
`apply_filter` is pure-Python pixel math (tight interpreter loop, no native calls), ~200ms per image.
Conventional GIL build currently. Some state (a stats counter dict) is mutated from worker threads.
Native extensions in the dependency tree: a few (numpy present, one closed-source SDK).

**Desired reasoning behavior**
Part A: classify — CPU-bound Python on a conventional GIL build: threads contend on the GIL and don't
give CPU parallelism ([CPYTHON] — precise version of the truth: threads are *not* "useless"; they're
wrong for this workload; they're right for blocking I/O). But before processes: the ladder says look
at the work itself — pure-Python pixel math should move into a vectorized/native library (NumPy/Pillow/
OpenCV kernels) which removes the Python loop and is usually the dominant win; then processes for
CPU-parallel Python if a real Python loop remains (costs: serialization/startup, I2/I4 ownership);
native extension/PyO3 only on profile evidence (I9). Part B: correct the teammate's two errors —
(a) free-threaded 3.14 is supported but ecosystem-maturing [CPYTHON]: native
extensions may be incompatible (the closed-source SDK may re-enable the GIL — the very parallelism
disappears), (b) removing the GIL does **not** make shared state safe — the mutating stats counter is
a data race unless synchronized/owned (I4: "free-threading does not repeal data races"). Any
free-threading path requires: extension-compatibility audit, shared-state audit, and workload
measurement — and it is never framed as "just enable it".

**Acceptable outcomes**
1. For A: explains the GIL/CPython mechanism precisely (no parallel bytecode for this workload; not "threads are useless" as a universal), recommends vectorizing the filter into native kernels first, then processes if Python CPU remains, with measurement. For B: rejects "shared state is safe" with I4 and lists the free-threading gates (compat audit incl. the closed-source SDK, data-race audit, measured win).
2. Same, plus an honest expectation: 8 threads on the conventional GIL build will not make this pure-Python loop run in parallel; processes have serialization/startup costs, and a native/vectorized kernel's gain must be measured on representative images.
3. Same, with the ownership fix for the stats counter regardless of execution model (per-thread counts merged at the end, or a lock around a tiny critical section) — correctness independent of the GIL debate.

**Failure modes**
- "The GIL is the problem, use free-threading / multiprocessing is obsolete now" (banned slogan family: "the GIL makes threads useless"; ignores compatibility, state safety, and workload evidence).
- Keeping the thread pool and adding more workers to "beat the GIL".
- Rewriting in Rust as the first suggestion (P1 pattern).
- Answering only Part A and rubber-stamping Part B's premise.

**Critical mistakes**
- Presenting free-threading as making shared-state/synchronization unnecessary (banned slogan: "free-threading makes shared state safe"; I4 MUST violation presented as fine).
- Claiming the GIL is guaranteed by the Python language — an invented language guarantee ([expected-behavior.md](expected-behavior.md) §3.4; also the §2 CPython-as-language banned behavior).
