# Evidence Rules

## Contents

- [1. Evidence sources (match the source to the claim)](#1-evidence-sources-match-the-source-to-the-claim)
- [2. Claim typing before delivery](#2-claim-typing-before-delivery)
- [3. Performance evidence protocol](#3-performance-evidence-protocol)
- [4. Migration and change evidence](#4-migration-and-change-evidence)
- [5. Distinguishing inference from fact](#5-distinguishing-inference-from-fact)
- [6. Verification of generated work](#6-verification-of-generated-work)
- [7. Decision records](#7-decision-records)
- [8. Counting what "enough context" means](#8-counting-what-enough-context-means)

Distinguish what is known, measured, and assumed. Match the evidence collected to the decision it supports.
This file defines the discipline used by
[decision-model.md](decision-model.md), the reviews, and every optimization or migration recommendation.

## 1. Evidence sources (match the source to the claim)

These sources answer different questions. A reproduction shows what the current system does, not what
its contract requires; a specification defines a contract, not whether this deployment follows it.
Use the strongest evidence for the question being asked:

1. **Reproduction / test / measured output in the actual system** — observed behavior and cost here.
2. **Repository evidence** — `pyproject.toml`, lockfile, CI config, test suite, existing patterns,
   deployment config, dependency APIs in use. Local evidence outranks ecosystem preference.
3. **Formal specifications** — language reference, PEPs, typing spec, PyPA specs, stdlib docs;
   authoritative for their stated contracts ([STANDARD]/[LANGUAGE]).
4. **First-party library/framework documentation for the pinned version** — behavior of *this* SQLAlchemy,
   FastAPI, Django, pytest… ([FRAMEWORK]).
5. **Project architecture docs & source** — how PyTorch/JAX/etc. actually execute work.
6. **Ecosystem practice and surveys** ([ECOSYSTEM]) — descriptive; never proof that a pattern is desirable.
7. **Engineering inference** ([HEURISTIC]) — reasoning from mechanisms; labeled as such.

Downgrade rule: any claim resting on levels 6–7 must not be stated as a guarantee. Slogans are rejected
outright ([principles §2](engineering-principles.md)).

## 2. Claim typing before delivery

Before stating a fact about behavior, classify it: [LANGUAGE] / [CPYTHON] / [STANDARD] / [FRAMEWORK] /
[ECOSYSTEM] / [HEURISTIC] / [EXPERIMENTAL] / [LEGACY] (taxonomy in
[SKILL.md](../SKILL.md#knowledge-classification)). Where the layer changes the recommendation, state the
layer in the output.

- CPython GC timing, GIL behavior, JIT effects → [CPYTHON]; never generalize to "Python".
- Framework lifecycle (session models, dependency injection, async support) → [FRAMEWORK]; never universalize.
- A feature formally designated experimental/provisional → [EXPERIMENTAL]. An optional supported
  feature may still need [CPYTHON] and [ECOSYSTEM] caveats; check the baseline for current status.
- Version-sensitive facts (what is stable, what is current) live only in
  [modern-python-baseline.md](../references/modern-python-baseline.md) — cite that file, don't hardcode
  versions elsewhere.

## 3. Performance evidence protocol

For nontrivial performance changes, use the relevant steps below. An obvious, low-risk complexity fix
can proceed from code evidence with representative verification; it need not wait for a production profile.

```text
1. Define the workload        → request mix, data size, concurrency, latency/throughput target
2. Measure end-to-end         → p50/p95/p99 or throughput under representative load
3. Attribute the cost         → CPU vs wait; interpreter vs native kernel vs DB vs network vs serialization
4. Classify the bottleneck    → algorithm? data access? N+1? lock contention? GC/alloc? blocking call?
5. Improve the dominant term  → algorithm/data access first, then batching/vectorization/caching
6. Only then touch the runtime→ concurrency model change, native extension, service split (architectural!)
7. Re-measure against target  → record before/after; revert if the target isn't hit
```

- Tooling (starting points, [CPYTHON]/[ECOSYSTEM]): `cProfile`/`timeit`/`tracemalloc` (stdlib),
  `py-spy` for running processes, Scalene to separate Python vs native CPU and memory/GPU.
  Mechanics: [performance.md](../references/performance.md).
- Async execution caveat: in JAX-style compiled/async-dispatch systems, naive timing may measure
  enqueueing, not completion — synchronize before measuring [FRAMEWORK].
- Worker-count, pool-size, and cache-size decisions use workload measurements or provisional capacity
  estimates, then validation under load; never copy a formula as an answer [HEURISTIC].

### Evidence to seek before consequential recommendations

In an existing system, measure the real workload where feasible. For greenfield decisions, use a
representative benchmark or explicit workload estimate, state the assumption, and set a review trigger.
A safety, compatibility, or ownership reason for a change does not require a performance profile.

| Recommendation | Decision evidence |
|---|---|
| "Rewrite in Rust/C/C++/Cython/Numba" | For speed: profile showing a dominant cost the native boundary can remove, stable boundary, target number. For safety/interoperability: concrete requirement and boundary; account for build cost |
| "Convert to async" | Measured or credibly projected concurrency need + wait-bound workload + audit of async-native dependencies and bounded sync offload |
| "Add a cache" | Repeated expensive work or capacity estimate + defined invalidation/staleness semantics + plausible hit-rate expectation |
| "Add a queue" | Named need (buffering, decoupled retry, scheduling) + failure-semantics analysis + idempotency answer |
| "Split into services" | Concrete independent ownership/deploy/scale/fault-domain need + distributed-failure analysis |
| "Switch ORM→SQL or SQL→ORM" | Query/round-trip profile or concrete productivity defect being fixed |
| "Migrate tool X→Y (Poetry→uv, Flake8→Ruff…)" | The named defect (maintenance, speed, capability gap) the migration fixes |
| "Add strict typing / retype module" | Defect class being prevented at that boundary + annotation cost estimate |
| "Free-threaded build / multiprocessing" | CPU-bound profile or representative compute estimate; for free-threading, extension compatibility and shared-state audit |

## 4. Migration and change evidence

Never recommend a stack migration (framework, package manager, sync→async, monolith→services, ORM→SQL,
Python→other) without: (a) the concrete problem, (b) evidence the migration addresses it, (c) migration
risk/cost, (d) a rollback or recovery path suited to its reversibility. "Modern" and "popular" are not
problems. Where the repo's choice works,
[invariants I10–I12](python-invariants.md) keep it.

## 5. Distinguishing inference from fact

When filling a gap the research/specs don't cover:

- Say "engineering inference" or tag [HEURISTIC]; frame conditionally.
- Prefer reversible decisions; name the review trigger.
- Never launder an inference into a rule ("studies show…", "Python guarantees…"). If a claim would change
  a reader's architecture, verify it against the spec or pinned-version docs, or downgrade the certainty.

## 6. Verification of generated work

Evidence obligations for delivered code ([principles §5](engineering-principles.md)):

- New behavior is verified at risk-proportional depth; run relevant tests and state the command + result,
  adding tests where the failure risk warrants them.
- Claims about third-party behavior cite the pinned version's documentation or observed behavior, not memory.
- Review checklists were applied to code crossing trust boundaries; the result (including
  "No significant issue found.") is reported with what was checked.
- If evidence could not be obtained (no network, no env), the deliverable marks the assumption and names
  the cheapest check to close it.

## 7. Decision records

For low-reversibility decisions (datastore, service split, native boundary, public API shape), record:
dominant constraint, chosen option, rejected alternatives + why, evidence, reversibility, review trigger
— [architecture-decision-record.md](../templates/architecture-decision-record.md). High-reversibility
decisions need only a line of rationale in the PR/commit.

## 8. Counting what "enough context" means

Ask questions only when the missing fact **changes the decision** and cannot be cheaply discovered
(read the repo, run the test). Otherwise state the working assumption and proceed — refusing to decide
under manageable uncertainty is a failure mode of this Skill. Keep the
[requested task mode](../SKILL.md#task-modes) unchanged while resolving uncertainty.
