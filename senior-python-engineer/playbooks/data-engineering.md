# Data Engineering / Pipelines

## Contents

- [1. Typical system shape](#1-typical-system-shape)
- [2. Important constraints](#2-important-constraints)
- [3. Recommended discovery questions](#3-recommended-discovery-questions)
- [4. Common architecture choices](#4-common-architecture-choices)
- [5. What not to overengineer](#5-what-not-to-overengineer)
- [6. Failure modes](#6-failure-modes)
- [7. Performance considerations](#7-performance-considerations)
- [8. Testing strategy](#8-testing-strategy)
- [9. Security concerns](#9-security-concerns)
- [10. Deployment/lifecycle concerns](#10-deploymentlifecycle-concerns)
- [11. References for unresolved questions](#11-references-for-unresolved-questions)
- [12. Exit/readiness criteria](#12-exitreadiness-criteria)

**Modes:** DESIGN, IMPLEMENT, REVIEW · **Concerns:** DEBUG · **Domains:** DATA_ENGINEERING (pipelines for DATA_SCIENCE too)
Procedure for ETL/ELT pipelines and data transformation systems. Governing rule: **explicit schemas at
every boundary** and re-runnable loads ([I1](../core/python-invariants.md), [I8](../core/python-invariants.md)).

## 1. Typical system shape

- **Extract → transform → load** stages with explicit, validated schemas at each boundary; stage outputs are inspectable artifacts, not hidden in-memory handoffs.
- Batch (full snapshot per run) vs incremental (delta since watermark) is the first structural choice; batch first unless data volume or freshness demands incremental [HEURISTIC].
- Orchestration (scheduler/DAG) is a thin layer over pipeline *functions*; the transform logic runs and is tested outside the orchestrator.
- IF the data fits in memory and the run is a few minutes → a script with a lockfile is a complete system. IF not → chunked/spill/streaming execution (§4).
- Each stage's output is content-addressable or run-ID-scoped where feasible; reprocessing old runs must not clobber newer data [HEURISTIC].

## 2. Important constraints

- **Data volume and shape dominate tooling** (§4): row counts × column widths × growth rate determine plain Python vs dataframe vs SQL-pushdown vs distributed engine.
- **Schema evolution** is a when, not an if: upstream producers change columns/types silently; boundary validation catches drift before it corrupts loads ([I1](../core/python-invariants.md)).
- **Late-arriving data**: incremental watermarks must define what happens when rows arrive older than the last checkpoint (reprocessing window, or accepted loss — stated, not accidental).
- **Backfill**: history must be re-loadable; this is the same code path as normal runs with different parameters.
- **Orchestration semantics**: retries, overlap, and partial-run behavior are part of the pipeline design ([I8](../core/python-invariants.md)), not the scheduler's problem.

## 3. Recommended discovery questions

Ask only what changes the design:
- Volume now and at horizon (rows/run, bytes, growth)? (Execution engine choice, §4.)
- Freshness requirement — hours, minutes, near-real-time? (Batch vs incremental vs streaming.)
- Is there a single source of truth for each schema, and who owns it? (Validation contracts.)
- What happens on partial run — which loads must be atomic together? (Transaction/idempotency design.)
- How far back can late data arrive? (Watermark/reprocessing policy.)
- What downstream consumers read this data, and what do they assume? (Output contract stability.)
- Where does execution run today — laptop, warehouse, cluster, container? (Pushdown opportunities, memory limits.)
- Who consumes outputs and when do they notice corruption? (Data-quality check placement and alert urgency.)
- Are there PII/regulated columns? (Access/masking policy, §9.)

## 4. Common architecture choices

- **Execution placement** — where the work runs is the architecture [HEURISTIC]:
  - IF transforms are row/record-level logic (parsing, enrichment rules, API calls) or data fits in memory → plain Python or dataframe tooling in the pipeline process.
  - IF transforms are set operations over large relational data (joins, aggregations, filters) → **SQL pushdown** to the database/warehouse engine; move code to the data, not data to the code.
  - IF data exceeds one machine comfortably → distributed dataframe/SQL engine (Spark-class or warehouse-native) — a real operational commitment; justify with measured volume ([Decision Model](../core/decision-model.md) §6 step 6).
- **Dataframe tooling vs plain Python** [ECOSYSTEM]: vectorized dataframes (pandas/Polars/similar) win on bulk tabular transforms; plain Python wins on irregular record logic and small volumes. Mixed pipelines are normal.
- **Batch vs incremental**: IF volume allows and freshness tolerates → full batch (simplest, self-healing). BUT IF volume or freshness demands it → incremental with explicit watermark, late-data policy, and periodic reconciliation runs.
- **Idempotent load** ([I8](../core/python-invariants.md)): load via replace-partition/upsert-keyed/append-with-dedupe — never "append and hope"; re-running a run ID must converge to the same state.
- **Schema handling**: typed schemas at extract and load ([I1](../core/python-invariants.md)); reject or quarantine rows failing validation — with counts reported, not silent drops.

## 5. What not to overengineer

- Microservices per pipeline stage; message buses between stages that run in one job ([I11](../core/python-invariants.md)).
- Custom orchestration frameworks/DAG engines when the platform's scheduler (or a cron) suffices.
- Streaming infrastructure for a nightly batch with no freshness requirement; exactly-once machinery for loads that are naturally idempotent.
- Hand-rolled dataframe abstractions wrapping one library's DataFrame "for portability"; premature data-lake/lakehouse platforms for one team's CSVs.
- Schema registries and contract platforms before there are multiple independent producers/consumers.
- Reimplementing window/aggregate logic in Python that the source database computes natively [HEURISTIC].

## 6. Failure modes

Domain-relevant subset of [Failure Modes](../catalogs/failure-modes.md):
- **Silent schema drift** — upstream renames/drops a column; pipeline writes nulls or wrong-typed data for weeks (mitigate: boundary schema validation + drift alerts, [I1](../core/python-invariants.md)).
- **Partial load without idempotent re-run** — run fails at 70%; re-run double-inserts the first 70% (mitigate: keyed load + run IDs, [I8](../core/python-invariants.md)).
- **Unbounded memory on big inputs** — `read_csv()` of a 40GB file into RAM; OOM kills the run after burning an hour (mitigate: chunked/streaming reads, or pushdown).
- **Watermark corruption** — checkpoint advanced before the load committed; a crash loses a window of data silently.
- **Late data beyond the reprocessing window** — quietly dropped; totals drift from truth until someone reconciles.
- **Orchestrator retry duplicating side effects** ([I8](../core/python-invariants.md)) — external API calls inside a retried task repeated without dedupe.

## 7. Performance considerations

- Evidence-first ([I9](../core/python-invariants.md), [Evidence Rules](../core/evidence-rules.md) §3, [Performance](../references/performance.md)): profile a representative run — wall time per stage, rows/sec, memory high-water mark, I/O wait.
- The dominant costs are usually I/O and data movement: reading more columns/rows than needed, shuffling data to Python that SQL could aggregate, per-row writes instead of bulk/copy loads. Fix those first ([Decision Model](../core/decision-model.md) §6).
- Vectorize/avoid Python loops over rows for tabular transforms; use the engine's native functions over UDFs where semantics allow [ECOSYSTEM].
- Memory: chunked processing, spill-capable engines, or pushdown — pick by measured volume, not preference.
- Benchmarks must run on representative data sizes; 1000-row dev samples hide every scaling failure [HEURISTIC].
- Skew/stragglers: one oversized key or partition dominates the run; inspect per-partition timing before adding machines.

## 8. Testing strategy

- Follow [Testing](../references/testing.md):
  - **Schema contracts**: fixtures per source schema version; drift/unknown-column cases asserted.
  - **Transform correctness**: unit tests over small known datasets with expected outputs; property-based tests for arithmetic/parse transforms ([Testing](../references/testing.md)).
  - **Idempotency test**: run the load twice on the same input; assert identical resulting state ([I8](../core/python-invariants.md)).
  - **Data-quality checks run in production** (row counts in/out, null rates, referential checks) — these are tests that keep running after deployment.
- Golden-file/regression tests for parsed outputs where formats are stable; sample real (sanitized) inputs, not only handcrafted ones.
- Backfill drill: before launch, run a historical backfill in staging and verify it converges to expected totals.

## 9. Security concerns

- Proportional to risk ([Security](../references/security.md)):
  - Parsed input formats (CSV, XML, Excel, archives) cross trust boundaries — schema validation ([I1](../core/python-invariants.md)); beware archive/path traversal in file ingestion and formula injection in spreadsheet outputs.
  - PII/regulated columns identified and handled per policy (masking, access control); pipelines are bulk-exfiltration surfaces by nature.
  - Credentials for stores/schedulers via secret boundary ([I15](../core/python-invariants.md)); service accounts least-privilege per source/sink.
  - No unsafe deserialization of cached intermediate artifacts ([Security](../references/security.md)) — parquet/JSON with schema, not pickle, for anything crossing a trust boundary.

## 10. Deployment/lifecycle concerns

- Runs are deployments: versioned code + pinned environment ([packaging](../references/packaging.md)); "the notebook that works on the cluster driver" is not reproducible.
- Overlap/locking for scheduled runs; retry policy consistent with idempotent loads ([I8](../core/python-invariants.md)).
- Backfill procedure documented and exercised before it is needed; recovery from a corrupt run defined (rollback partition / re-run window).
- Observability: per-run records (rows in/out, rejected, duration), stage metrics, and alerts on volume anomalies and schema drift ([Observability](../references/observability.md), [Reliability](../references/reliability.md)).

## 11. References for unresolved questions

Read only the section that answers an active question; this list is a menu, not a reading sequence.

- [core/python-invariants.md](../core/python-invariants.md) — I1 (schema boundary), I8 (idempotent re-run), I9 (measure before optimizing).
- [references/performance.md](../references/performance.md) — profiling batch workloads, vectorization, memory analysis.
- [references/testing.md](../references/testing.md) — property-based/golden-file testing for transforms.
- [references/security.md](../references/security.md) — untrusted file parsing, path traversal, deserialization.
- [references/reliability.md](../references/reliability.md) — retry/overlap/recovery semantics for scheduled runs.
- [references/observability.md](../references/observability.md) — run metrics, data-quality monitoring.
- [references/packaging.md](../references/packaging.md) — reproducible environments for pipeline runs.
- [workers-jobs.md](workers-jobs.md) — when the pipeline runs on a queue/worker fabric.
- [reviews/database-review.md](../reviews/database-review.md) — when loads touch transactional stores.

## 12. Exit/readiness criteria

Apply the [mode-specific completion rules](../SKILL.md#task-modes) to the relevant criteria below.
Operational checks are release gates only when release readiness is in scope. Report actual evidence
and label proposed or unavailable checks.

### DESIGN completion

Specify input/output contracts, load semantics, ownership, late-data policy, partial-failure recovery,
and expected volume. State assumptions and the checks that will establish idempotency, correctness,
and capacity. A backfill run or production monitoring deployment is not required to finish the design.

### IMPLEMENT / release evidence

Apply these checks to the pipeline paths delivered in the task:

- [ ] Schemas validated at extract and load boundaries; drift behavior defined (reject/quarantine/alert) ([I1](../core/python-invariants.md)).
- [ ] Re-run/backfill semantics defined and tested: running twice converges to identical state ([I8](../core/python-invariants.md)).
- [ ] Relevant data-quality checks implemented and exercised; production scheduling and alerts verified
      when operational readiness is in scope.
- [ ] Late-data/watermark policy stated explicitly, including the reprocessing window.
- [ ] Memory/performance checks use representative data when size or throughput is a material risk;
      identify estimates and untested capacity assumptions.
- [ ] Partial-failure recovery defined (rollback/re-run window); overlap/locking for scheduled runs set.
- [ ] Run observability in place: per-run row counts, rejected rows, durations, anomaly alerts.
- [ ] Output provenance recorded (code version, run ID, source snapshot) per load.
- [ ] When backfill execution or release readiness is in scope, rehearse the backfill in an appropriate
      environment and reconcile totals; otherwise supply its procedure and mark the rehearsal pending.
