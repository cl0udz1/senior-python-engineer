# Performance Investigation

## Contents

- [Fill-in structure](#fill-in-structure)
- [Workload definition](#workload-definition)
- [Measurements before](#measurements-before)
- [Cost attribution](#cost-attribution)
- [Bottleneck classification](#bottleneck-classification)
- [Candidate changes (evidence-ladder ordered)](#candidate-changes-evidence-ladder-ordered)
- [Change + re-measure](#change--re-measure)
- [Result vs target](#result-vs-target)
- [Revert decision](#revert-decision)
- [JAX / async-dispatch caveat (required note for compiled/async runtimes)](#jax--async-dispatch-caveat-required-note-for-compiledasync-runtimes)
- [Filled fragment](#filled-fragment)

Purpose: record one performance probe as evidence — what was measured, what the cost actually is, what
changed, and what the numbers did. Follows the evidence ladder in
[Evidence Rules](../core/evidence-rules.md) §3 (workload → measure → attribute → classify → improve the
dominant term → only then touch the runtime → re-measure). Invariant anchor: optimization follows
measurement (I9).

Use for work with OPTIMIZE concerns, latency/throughput complaints, and capacity questions. Follow
[task modes](../SKILL.md#task-modes): inspection and measurements may establish a diagnosis; changing
application code requires implementation scope. A requested investigation plan specifies measurements
and does not report them as executed. Not for "this looks
slow" — that starts at Measurements, not at candidate fixes. Depth rule: a 2-page report is complete;
skip sections that didn't apply with "n/a + why". Decision inputs: [Decision Model](../core/decision-model.md)
§6, [Performance](../references/performance.md), [Performance Review](../reviews/performance-review.md).

**Anti-pattern watch:** the fastest way to waste a week is to pick the fix first ("rewrite in Rust",
"add a cache", "go async") and hunt for confirmation. If a candidate change wasn't derived from the cost
attribution below, it is a guess — label it one.

---

## Fill-in structure

# Performance investigation: <path/operation> — <date>

## Workload definition
*Request mix, data sizes, concurrency level, environment (hardware, Python version, [CPYTHON] build —
JIT on/off, free-threaded?), and the **target** (p95 < X ms? throughput ≥ Y rps?). No target = no way
to say "fixed". If the target is unknown, state the current number and who owns the SLO.*

## Measurements before
*Tool used + command; raw numbers: p50/p95/p99 or throughput, plus resource profile (CPU, memory).
Measurements must come from representative load — a microbenchmark of a non-hot path proves nothing.
Record the variance, not just the mean.*

## Cost attribution
*Where does the time actually go: interpreter (Python bytecode) vs wait (network/disk/locks) vs DB
(query count, slow queries) vs serialization vs native kernels vs GC/alloc. Evidence: profile output
(cProfile, py-spy, Scalene, tracemalloc), query logs, span timings. This section decides everything
after it.*

## Bottleneck classification
*One sentence: the dominant term is <X> because <evidence>. Common classes: algorithmic complexity,
data access / N+1, lock contention, blocking call on a hot path, serialization size, allocation churn,
interpreter-bound loop, native-kernel-bound (not a Python problem). If ambiguous, measure again with a
narrower probe — do not average two hypotheses into one fix.*

## Candidate changes (evidence-ladder ordered)
*Only candidates justified by the attribution above, ordered per
[Evidence Rules §3](../core/evidence-rules.md) §3: algorithm/data-access first → batch/vectorize/cache
→ concurrency matched to workload → runtime/native boundary last (architectural, requires the full
"what must be measured" evidence from §3). Each candidate: expected effect on the dominant term.*

1. …

## Change + re-measure
*What was actually changed (diff/commit), then the same measurement repeated under the same workload.
One variable at a time where practical; note confounders if not.*

## Result vs target
*Before/after table. Did it hit the target? Percent improvement on the dominant term — not on a number
chosen after the fact.*

## Revert decision
*Keep / revert / iterate, with the reason. Reverting a 20% win that adds permanent complexity is often
right; keep/revert is a judgment against the target and the cost (I9), not a victory lap. If iterating,
the next investigation starts again at Measurements.*

---

## JAX / async-dispatch caveat (required note for compiled/async runtimes)

In JAX-style compiled / async-dispatch systems, naive timing may measure **enqueueing, not completion**
[FRAMEWORK]. Synchronize the device before stopping the timer (`block_until_ready()` or equivalent),
account for compilation time separately from steady-state execution (first call ≠ hot call), and state
which one the target refers to. The same trap exists for any fire-and-forget async API: timing the
submit is not timing the work.

---

## Filled fragment

*Illustrative example only: replace its names, values, and reported outcomes with project evidence.*

```markdown
## Workload definition
Batch report endpoint, 500-row dataset, 20 concurrent clients, staging ≈ prod hardware.
Target: p95 < 800ms (current SLO draft).

## Measurements before
`py-spy record` + `cProfile` under k6 load: p95 4.2s. Query log: ~11k queries/report (N+1 on line_items).

## Cost attribution
Wait 82% (DB round trips), CPU 15% (parsing), serialization 3%. Interpreter not the bottleneck.

## Bottleneck classification
Data access: ORM lazy-load in line-item loop (N+1) — confirmed by query count scaling with rows.

## Candidate changes (ladder order)
1. Eager/select-in load or one joined query for line_items (attacks the dominant term). 2. n/a —
   no CPU/interpreter work worth vectorizing. Native rewrite not proposed: cost is in wait (I9).

## Change + re-measure
Commit abc123: joined query + manual mapping. Same k6 profile: p95 610ms, ~3 queries/report.

## Result vs target
p95 4.2s → 610ms (−85%), target < 800ms met. CPU unchanged.

## Revert decision
Keep. No new dependencies; query plan verified with EXPLAIN (index on line_items.order_id used).
```
