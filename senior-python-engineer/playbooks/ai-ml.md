# AI / ML Systems

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

**Modes:** DESIGN, IMPLEMENT, REVIEW · **Concerns:** OPTIMIZE, DEPLOY · **Domains:** AI_ML (DATA_SCIENCE pipelines route to [data-engineering.md](data-engineering.md))
Procedure for ML training/evaluation/serving systems. Governing rule: **Python is the control plane over
native kernels**; "Python is too slow for ML" is a slogan, not a finding
([ai-ml.md](../references/ai-ml.md), [Evidence Rules](../core/evidence-rules.md) §3).

## 1. Typical system shape

- Pipeline shape: **data → training → evaluation → model artifact → serving**; each stage has explicit inputs/outputs and provenance (data version, code version, config, seed).
- Python orchestrates; the heavy math runs in native kernels (PyTorch C++, JAX→XLA, NumPy) [FRAMEWORK]. The engineering work is data flow, lifecycle, and measurement — not rewriting kernels.
- Experiment environment (notebooks/scripts) and production code share domain logic where possible; training code is versioned code, not notebook state.
- Serving shapes: batch inference job, model server/service, or embedded library call — chosen by who consumes predictions and when (§4).
- Experiment tracking (runs, metrics, artifacts) is part of the shape once there are more than a handful of runs [ECOSYSTEM]; before that, disciplined folders + configs suffice [HEURISTIC].

## 2. Important constraints

- **Device/compile/memory dominate** runtime: GPU/TPU transfer, compilation (JAX `jit` compile time, torch compile), and batch memory ceilings — not Python interpreter cost ([ai-ml.md](../references/ai-ml.md), [Performance](../references/performance.md)).
- **Reproducibility**: seeds, data snapshot IDs, dependency locks, config capture; a result that cannot be re-run is an anecdote [HEURISTIC].
- **Experiment velocity vs production rigor**: fast iteration in research code is fine *behind* the boundary; anything promoted to serving gets the full discipline (tests, validation, monitoring).
- Train/serve skew is a correctness constraint: features computed differently in training and serving silently degrade models (§6).
- Model artifacts are code-adjacent: how they are serialized determines your deserialization risk ([Security](../references/security.md), §9).

## 3. Recommended discovery questions

Ask only what changes the design:
- What is the workload — training, fine-tuning, inference, or all three? (Different shapes entirely.)
- What are the compute targets (GPU class, memory, batch size, latency budget)? (Device/compile constraints dominate.)
- Data scale and modality (images, text, tabular; GB vs TB)? (Data loading becomes the bottleneck at scale.)
- Batch or online inference, and what latency does the consumer require? (Serving shape, §4.)
- How will quality be measured — offline metric, online A/B, human eval? (Evaluation design gates everything.)
- Reproducibility/compliance requirements (regulated domain, audit of training data)? (Provenance depth.)
- Team profile: researchers shipping occasional models, or engineers running a platform? (Rigor vs velocity balance.)
- What invalidates a deployed model — data drift, concept drift, or scheduled retraining? (Lifecycle monitoring, §10.)

## 4. Common architecture choices

- **Framework** [FRAMEWORK]: IF dynamic models, ecosystem breadth, and iteration speed dominate → PyTorch-class stack. BUT IF function transformations, compilation, and TPU/accelerator targets dominate → JAX-class stack. Both are Python-over-native; choose by model/ecosystem fit, not benchmarks of unrelated workloads.
- **Training jobs vs services**: IF training is periodic with large resources → job/scheduler shape (batch worker, [workers-jobs.md](workers-jobs.md)). BUT IF continuous/fine-tuning pipelines feed serving → pipeline + registry discipline ([data-engineering.md](data-engineering.md) patterns).
- **Batch vs online inference**: IF consumers tolerate latency → batch is simpler, cheaper, easier to validate. BUT IF predictions are request-path → service with measured latency budget ([production-service.md](production-service.md) applies).
- **Execution model for Python glue**: sync is default; async only where I/O fan-out (data fetching, API calls) dominates ([Decision Model](../core/decision-model.md) §1). GPU work is neither — it is kernel dispatch [FRAMEWORK].
- **Feature/transform code**: one implementation shared by training and serving (or contract-tested duplicates) — never two unverified paths (§6).
- **Model store**: artifact registry with version + lineage before "a directory on disk" hurts someone [HEURISTIC].

## 5. What not to overengineer

- Distributed training infrastructure for models that fit on one accelerator — measure first ([Evidence Rules](../core/evidence-rules.md) §3); multi-node adds data-parallel complexity (gradient sync, checkpointing) with zero payoff at small scale.
- Microservice per model step (tokenizer service, featurizer service, post-processor service) — one process with modules is the default ([I11](../core/python-invariants.md)).
- Feature platforms, experiment trackers, model servers before there are more than a handful of models and users.
- Hand-rolled training loops over a framework's proven loop for standard architectures [ECOSYSTEM]; custom CUDA/extensions without a profiled kernel gap.
- Premature MLOps abstraction ("any model, any framework, any cloud") for one team's two models.
- Real-time feature stores for models consumed in batch.

## 6. Failure modes

Domain-relevant subset of [Failure Modes](../catalogs/failure-modes.md):
- **Unmeasured "Python is slow / rewrite in Rust" conclusions** ([Evidence Rules](../core/evidence-rules.md) §3): profile first; hot paths are usually data loading, transfers, or a mis-shaped tensor op — not the interpreter.
- **Unsafe model deserialization** — unrestricted pickle loading, including `torch.load(..., weights_only=False)`, can execute code from an untrusted checkpoint. Check the pinned version and loading mode against the [current baseline](../references/modern-python-baseline.md), and treat model artifacts as a trust boundary even with restricted loading [FRAMEWORK] ([Security](../references/security.md)).
- **Train/serve skew** — features/preprocessing computed differently in the two paths; offline metrics look fine while production quality silently decays.
- **Data leakage** — target or future information in features; validation split contaminated; inflated metrics, failed production.
- **OOM at batch boundaries** — dev batch size ≠ prod batch size; serving crashes under real concurrency.
- **JAX/torch compile timing mis-measurement** — async dispatch means naive timers measure enqueueing; synchronize before timing ([ai-ml.md](../references/ai-ml.md), [FRAMEWORK]).
- **Silent training drift** — new data version changes distribution without anyone noticing (monitor input stats; [Observability](../references/observability.md)).

## 7. Performance considerations

- Evidence-first and workload-specific ([I9](../core/python-invariants.md), [Evidence Rules](../core/evidence-rules.md) §3, [Performance](../references/performance.md)):
  1. Define the actual workload (model, batch size, sequence/image sizes, device).
  2. Measure end to end: data loading vs host compute vs transfer vs kernel time vs synchronization stalls.
  3. Fix the dominant term: data pipeline (prefetch, parallel loaders, storage), then model/kernel shape (mixed precision, fused ops, compilation), then topology.
- Compilation-aware benchmarking: warm up compiled paths; synchronize device before/after timing [FRAMEWORK].
- Memory is a hard constraint: batch size, gradient accumulation, activation checkpointing are levers — measured against device limits.
- Native-boundary work (custom kernels via Numba/Cython/PyO3, C++/CUDA) is the last step ([Decision Model](../core/decision-model.md) §6) and needs a profiled kernel gap + stable boundary + build/ABI cost acceptance.
- Verify JIT support and feature status for the selected Python version/build before considering it;
  an experimental capability is not an unstated production default. Benchmark the actual workload
  ([modern-python-baseline.md](../references/modern-python-baseline.md)).
- Data loading at scale: storage format (columnar vs row), worker parallelism, and prefetch dominate GPU utilization; a bored GPU is usually a starved pipeline [HEURISTIC].

## 8. Testing strategy

- Follow [Testing](../references/testing.md), adapted for nondeterminism:
  - **Deterministic unit tests** for preprocessing/feature code with fixed fixtures — this code is ordinary Python and gets ordinary rigor.
  - **Training smoke tests, when training is in scope**: an affordable representative batch run in CI where feasible; an overfit sanity run can catch shape/device/config breaks.
  - **Evaluation gates, when promoting models**: metric thresholds on a held-out set; regression tests on a golden eval set per release.
  - **Serving contract tests, when serving is in scope**: request/response schema; preprocessing parity with training and batch-vs-online consistency where both paths exist.
- Tolerance-based assertions for floating-point results; seed control where supported [FRAMEWORK].
- Data-pipeline tests: fixture datasets through preprocessing; assert feature parity between training and serving paths.

## 9. Security concerns

- Proportional to risk ([Security](../references/security.md)):
  - **Model artifacts cross a trust boundary** — unrestricted pickle-based checkpoint loading can run code; use safer formats and inspect pinned loader modes, and do not load arbitrary untrusted artifacts ([Security](../references/security.md)).
  - Training data crosses trust boundaries (user uploads, scraped text, external datasets) — validate and bound it ([I1](../core/python-invariants.md)); poisoning is a real threat class for learned systems.
  - Secrets for registries/compute via secret boundary ([I15](../core/python-invariants.md)); credentials on training clusters are high-value.
  - Serving endpoints: input size bounds, authn/authz like any API ([web-api.md](web-api.md) security section); model inversion/memorization exposure considered for sensitive data.

## 10. Deployment/lifecycle concerns

- Training reproducibility: pinned environments ([packaging](../references/packaging.md)), captured configs, data snapshot IDs; artifacts registered with lineage before serving.
- Serving is a production service: SLOs, graceful shutdown, probes, capacity ([production-service.md](production-service.md), [Deployment](../references/deployment.md)); GPU serving adds cold-start/model-load-time as a first-class latency term.
- Model lifecycle: promotion criteria (eval gate), rollback = redeploy previous artifact fast, deprecation policy.
- Monitoring: prediction-quality proxies, input-distribution drift, latency/throughput, device utilization ([Observability](../references/observability.md)).

## 11. References for unresolved questions

Read only the section that answers an active question; this list is a menu, not a reading sequence.

- [references/ai-ml.md](../references/ai-ml.md) — framework execution models, device/compile/memory behavior, benchmarking caveats [FRAMEWORK].
- [references/performance.md](../references/performance.md) — profiling methodology including native-kernel attribution.
- [core/evidence-rules.md](../core/evidence-rules.md) §3 — the evidence ladder that blocks unmeasured rewrites.
- [references/testing.md](../references/testing.md) — property/tolerance testing, CI smoke patterns.
- [references/security.md](../references/security.md) — deserialization risk, untrusted training data.
- [references/packaging.md](../references/packaging.md) — reproducible training environments.
- [data-engineering.md](data-engineering.md) — when data pipelines are in scope; [production-service.md](production-service.md) — when serving is a service.
- [workers-jobs.md](workers-jobs.md) — training/inference jobs on queues.

## 12. Exit/readiness criteria

Apply the [mode-specific completion rules](../SKILL.md#task-modes) to the relevant criteria below.
Operational checks are release gates only when release readiness is in scope. Report actual evidence
and label proposed or unavailable checks.

Observable checklist; apply only to the training, evaluation, and serving paths this project owns:
- [ ] Consequential performance claims use a benchmark of the **actual** workload (data load, kernel, transfer, device/batch as relevant), not a slogan ([Evidence Rules](../core/evidence-rules.md) §3).
- [ ] Model artifact source and load mode are known; for owned training, record code version, data snapshot, config, and seed ([Security](../references/security.md)).
- [ ] If serving: SLOs named and checked at target concurrency; request/response contract tested.
- [ ] If training and serving share features: parity demonstrated by one implementation or a contract test.
- [ ] If promoting models: evaluation threshold and rollback artifact defined and tested.
- [ ] If training: an affordable smoke test runs in CI on a representative device; reproducibility is checked to appropriate tolerance.
- [ ] If operating a model: monitor relevant quality, drift, and resource signals ([Observability](../references/observability.md)).
- [ ] If retraining is owned here: trigger and owner are defined.
