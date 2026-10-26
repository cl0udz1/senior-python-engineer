# Performance Review

## Contents

- [Scope & trigger](#scope--trigger)
- [Review contract](#review-contract)
- [Hard rule: evidence before optimization](#hard-rule-evidence-before-optimization)
- [Procedure](#procedure)
- [Checklist](#checklist)
- [Finding format](#finding-format)
- [False positives / legitimate exceptions](#false-positives--legitimate-exceptions)
- [Output expectations](#output-expectations)

Review of performance claims, optimizations, and capacity decisions. **Hard rule: evidence before
optimization** ([evidence-rules §3](../core/evidence-rules.md)) — a performance finding without
measurement is an *assumption*, and this review labels it as one instead of laundering it into a defect.

## Scope & trigger

Use when: someone claims code is slow or fast; a performance change (caching, batching, concurrency,
native rewrite, worker counts) is proposed or merged; an SLA/latency target must be verified; or a
benchmark is presented as proof. Design-level execution-model choices belong in
[architecture-review.md](architecture-review.md); algorithmic correctness in [code-review.md](code-review.md).
This review judges the *evidence and the layer*, not the taste of the code.

## Review contract

Follow the shared [review contract](code-review.md#review-contract) for task scope,
priority, severity, evidence, finding format, and a valid clean-review outcome.

## Hard rule: evidence before optimization

Use the relevant steps of the evidence protocol in [evidence-rules §3](../core/evidence-rules.md):
define the workload, measure when available, attribute cost, choose the smallest lever, and re-measure.
A code-obvious complexity fix can be reviewed with representative verification; architecture-level
runtime changes need stronger evidence.

## Procedure

1. **Find the workload definition.** If a claimed speedup names no workload (data size, concurrency,
   target latency/throughput), ask for one or label the claim unverified. Missing context alone is not
   a code finding.
2. **Find the measurement.** For consequential changes, inspect profile or benchmark numbers and method
   (tool, data, repetitions). Without a live system, use a representative estimate and review trigger.
3. **Attribute the layer** of the claimed cost: interpreter-bound Python, waiting on I/O, DB round
   trips, network, serialization, native kernel, lock contention, allocation/GC [CPYTHON].
4. **Check the fix targets the dominant term** and that its added complexity is justified. Algorithm
   or data-access fixes are often cheapest; another lever can win when the evidence points there.
5. **Audit the benchmark method** for the known traps below (JAX async dispatch, warm-up, cache effects,
   micro-benchmark mismatch with the real workload).
6. **Check the complexity budget**: what did the change cost in maintainability, correctness risk
   (threads, shared caches, native builds) against the measured gain?
7. **Audit benchmark hygiene**: warm-up excluded consistently; steady-state vs compile-time regimes
   stated (JAX compilation, JIT [EXPERIMENTAL]); realistic data sizes; enough repetitions; same machine
   and build for before/after; measurement noise vs claimed delta.
8. **Report** measured numbers inline; label unverified cost claims as assumptions. Complexity analysis
   from the code may justify a narrow local fix without a production profile.

## Checklist

| Check | Mechanism | Evidence to look for |
|---|---|---|
| Workload defined | Claim names data size, concurrency, and target | "Slow" without a workload is not a finding; "p95 > 300 ms at 200 rps on 50k-row tables" is |
| Measurement present when needed | Profile/benchmark with method stated | cProfile/timeit/tracemalloc output, py-spy/Scalene samples [CPYTHON/ECOSYSTEM]; small code-obvious fixes can use representative tests |
| Cost layer attributed | CPU vs wait; interpreter vs DB vs network vs serialization vs native | Wall-time-only claims with no attribution; "Python is slow" without a profile is the banned slogan |
| Lever fits the cost | Dominant cost addressed with justified complexity | Threads/Rust proposed while an O(n²) loop or missing index dominates |
| N+1 / round trips | Query counts scale with result size | Query log evidence ([database-review](database-review.md)); frequently the dominant term in ORM apps |
| Blocking-in-async | Stall attributed to a blocking call on the loop | Loop-lag evidence ([async-review.md](async-review.md)); "async is slow" often means one blocking dep |
| Allocation hotspots | Memory churn / GC pressure identified | tracemalloc/Scalene output; per-request giant temporaries, string concat in loops |
| Caching with invalidation | Cache names key, TTL, owner, and staleness semantics | Cache added with no invalidation model = correctness risk first ([failure-modes](../catalogs/failure-modes.md)) |
| Batching / vectorization | Bulk ops or array ops replace per-item work | `executemany`/bulk ORM ops, NumPy/pandas over Python loops; measure both — small data may not care |
| "Rewrite in Rust/native" claims | Profile proves interpreter-bound cost in the hot path; stable boundary; target number stated | Required evidence table in [evidence-rules §3](../core/evidence-rules.md); premature native rewrites are a known trap |
| JAX/async-dispatch benchmarking | Timings synchronize before measuring | Naive JAX timing measures enqueueing, not completion [FRAMEWORK]; compilation warm-up excluded/included consistently |
| Worker/pool counts measured | Counts derived from measurement vs CPU/memory/pool limits | "2 workers per core" formulas copied from docs; worker counts are measured [HEURISTIC] |
| JIT claims | Workload measured on the actual build | The CPython JIT is [EXPERIMENTAL] and not a production default ([modern-python-baseline.md](../references/modern-python-baseline.md)); experiments require workload benchmarks |

## Finding format

Per [templates/code-review.md](../templates/code-review.md):
`Severity:` `Evidence:` `Why it matters:` `Recommended change:` `Trade-off:` `Verification:`.

Severity follows impact at the expected workload: a local inefficiency can be Low, while capacity
exhaustion threatening availability can be High. An optimization that introduces a race or data loss is
graded by that consequence, not by the MUST label. Unmeasured cost claims are **assumptions** unless
code evidence alone establishes the mechanism (for example unbounded growth or obvious quadratic work).

### Example finding vs assumption (shape only)

Finding (measured):

- **Severity:** Medium
- **Evidence:** py-spy sample (30 s, production-shaped load) attributes 71% of wall time to
  `serialize_batch`'s per-row `json.dumps` loop (`export/writer.py:77`); end-to-end p95 = 2.4 s vs
  0.8 s target at 10k rows.
- **Why it matters:** serialization, not the interpreter or the DB, is the dominant term — tuning
  queries would not hit the target.
- **Recommended change:** serialize once with `json.dumps(rows)` (or a batch writer) on this path.
- **Trade-off:** one big allocation vs many small ones; measure memory at max batch size.
- **Verification:** re-run the same load: p95 ≤ 0.8 s target; py-spy sample shows serialization
  no longer dominant.

Assumption (unmeasured) — reported as: *"Assumption: `parse_log_line` is a hot spot because it uses
regex. Cheapest check: cProfile over one representative file. Not a finding until measured."*

## False positives / legitimate exceptions

- **Python orchestration over native kernels (NumPy/PyTorch/JAX) is not slowness.** "Python is too slow
  for ML" is a banned slogan; measure where time actually goes ([ai-ml](../references/ai-ml.md)).
- **ORM overhead without query-log evidence is not a finding** — round trips dominate, not abstraction
  ([persistence](../references/persistence.md)).
- **Small internal tools and batch scripts** rarely need optimization; flag only against a stated target.
- **A measured, target-meeting system gets no findings** however inelegant the hot path looks.
- **Debug logging in cold paths** is not a performance finding.
- **Warm-up costs of compiled/async systems** (JAX compilation, JIT [EXPERIMENTAL]) are not steady-state
  regressions when the benchmark excludes them consistently — say which regime is measured.
- **Optimizations already merged** with before/after numbers are reviewed for correctness/complexity,
  not relitigated.

## Output expectations

- Lead with the measured picture (workload, numbers, dominant cost layer), then findings, then what
  would change the conclusion.
- Every number states its method; every unmeasured claim is explicitly labeled an assumption with the
  cheapest measurement to close it ([evidence-rules §6](../core/evidence-rules.md)).
- "No significant issue found." is valid — including "no evidence of a performance problem". Never
  invent bottlenecks to appear thorough.
- Recommendations stop at the dominant term: the smallest change that hits the target wins over the
  architectural change ([principles §1](../core/engineering-principles.md)).
