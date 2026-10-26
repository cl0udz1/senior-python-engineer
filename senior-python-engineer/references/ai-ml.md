# AI/ML

## Contents

- [Python as control plane over native kernels](#python-as-control-plane-over-native-kernels)
- [Training vs inference workloads](#training-vs-inference-workloads)
- [Data loading pipelines](#data-loading-pipelines)
- [Device transfer, compilation, memory](#device-transfer-compilation-memory)
- [Benchmarking discipline](#benchmarking-discipline)
- [LLM and agent stacks ECOSYSTEM](#llm-and-agent-stacks-ecosystem)
- [Model serialization safety](#model-serialization-safety)
- [Mixing native boundaries](#mixing-native-boundaries)
- [Reproducibility, seeds, experiment tracking](#reproducibility-seeds-experiment-tracking)
- [Decision heuristics](#decision-heuristics)

Operational reference for Python in AI/ML systems. Version-sensitive facts live only in
[modern-python-baseline.md](modern-python-baseline.md). Cross-refs: [ai-ml playbook](../playbooks/ai-ml.md),
[performance.md](performance.md), [security.md](security.md), [data-engineering playbook](../playbooks/data-engineering.md).
Framework claims [FRAMEWORK]; practice [ECOSYSTEM].

## Python as control plane over native kernels

- The expensive work in modern ML runs in native runtimes: PyTorch tensor ops execute in C++/CUDA
  [FRAMEWORK]; JAX traces Python-expressed array programs into XLA-compiled computations [FRAMEWORK].
  Python orchestrates: training loops, data pipelines, model composition, experiment logic.
- Consequence: "Python is too slow for ML" is a banned slogan. The real question is **where the
  Python/native boundary sits**. Python-loop-over-tensors (per-element ops, `.item()` in hot loops,
  Python-side data munging per sample) is where Python genuinely loses; batched tensor ops and native
  kernels are where it doesn't.
- Where Python does lose [HEURISTIC]: kernel authoring (CUDA/C++/Triton-class work), extreme
  serving latency (sub-millisecond dispatch overhead matters), tiny-footprint embedded runtimes.
  Boundary decisions: [Decision Model §6](../core/decision-model.md) (native boundaries).

## Training vs inference workloads

| | Training | Inference |
|---|---|---|
| Dominant cost | Compute (GPU), data loading, device transfer | Latency (dispatch, transfer), throughput/batching |
| Shape | Batch, long-running, checkpointed | Request/response or streaming, continuous |
| Python role | Orchestration loop, logging, checkpointing | Request handling, pre/post-processing, batch assembly |
| Failure mode | Wasted GPU-hours on a crashed run (checkpointing) | Latency SLO misses, OOM on large batch |

- Training: checkpointing + resumability are reliability requirements (I2 lifecycle: close writers,
  atomic checkpoints); validation loop metrics feed experiment tracking.
- Inference: batch assembly is the leverage point (batching amortizes dispatch
  ([performance.md](performance.md) batching); dynamic batching with max-latency bound); model
  loading/warmup at startup (readiness, [deployment.md](deployment.md) probes).

## Data loading pipelines

- The GPU waits for data: input pipelines (PyTorch `DataLoader` workers, TF `tf.data`, JAX input
  pipelines) are commonly the bottleneck, not the model [ECOSYSTEM]. Prefetch, parallel decode, cache
  small datasets in memory; measure pipeline throughput vs device consumption rate before buying GPUs.
- Data loading is where Python CPU cost + serialization + disk/network I/O meet: worker processes
  (not threads for CPU-bound decode) ([asyncio-concurrency.md](asyncio-concurrency.md) processes);
  beware fork+threads+native libs interactions on `spawn` vs `fork` platforms.
- Determinism: seeded shuffling/augmentation where reproducibility matters (below); schema/label
  validation at the data boundary (I1) — corrupted labels are silent training damage.

## Device transfer, compilation, memory

- The three dominant constraints beyond "GPU speed":
  1. **Host↔device transfer**: staging batches to GPU is expensive; overlap with compute
     (`pin_memory`, non_blocking transfers, prefetch); keep tensors on-device across steps
     (`.item()`/`.cpu()` in loops is the classic self-inflicted slowdown).
  2. **Compilation** (torch.compile, XLA compilation): startup cost + recompilation on shape changes;
     static shapes amortize; measure steady-state vs compile time ([performance.md](performance.md)
     JAX caveats apply equally to torch.compile).
  3. **Memory**: activation/batch-size math; OOM debugging is memory attribution work (profiler
     memory timeline); gradient accumulation trades compute for memory; fragmentation in long runs.
- Mixed precision (fp16/bf16) is a memory+throughput lever with numerical caveats [ECOSYSTEM];
  verify metric stability when enabling.

## Benchmarking discipline

- Measure **completion, not enqueueing** ([performance.md](performance.md)): async dispatch means
  naive timers measure submission. Synchronize the device before/after timing.
- Warmup: first iterations include compilation/caching; report steady-state. Report p50/p95 latency
  and throughput at realistic batch sizes, not just max-throughput headline numbers.
- A/B with the same seeds/data order where variance is a concern; report variance, not single runs.

## LLM and agent stacks [ECOSYSTEM]

- Python dominates LLM app layers: orchestration frameworks, RAG pipelines, tool/function-calling
  loops, evaluation harnesses. Python cost here is negligible vs model latency — optimize for
  correctness and observability, not dispatch overhead ([llm-agentic playbook](../playbooks/llm-agentic.md)).
- Reliability shape: API calls to model providers are external boundaries — timeouts, retries with
  idempotency-aware design (I8: a retried tool call re-executes the tool!), bounded concurrency,
  cost accounting ([reliability.md](reliability.md)). Streaming responses need backpressure and
  cancellation ([asyncio-concurrency.md](asyncio-concurrency.md)).
- Security: prompt injection, tool-use blast radius, credential handling, output handling for
  downstream code execution ([security.md](security.md)); agent privilege is risk.

## Model serialization safety

- Checkpoints and model files are often **pickle-based**. `pickle.load` executes code
  ([security.md](security.md) unsafe deserialization). Stable `torch.load` defaults to restricted
  `weights_only=True`; `weights_only=False` is unrestricted pickle, and PyTorch still says not to
  load an untrusted file ([baseline](modern-python-baseline.md)). Prefer safe formats
  (safetensors-class [ECOSYSTEM]) for cross-org exchange; treat model hubs as untrusted input when
  provenance is weak. "User uploads a model" = "user uploads code execution."
- Version compatibility: serialized models couple to library versions; pin and record versions with
  artifacts ([packaging.md](packaging.md) app pinning; experiment tracking below).

## Mixing native boundaries

- When to write native code (CUDA kernels, C++/Rust extensions, Triton-class) vs use existing kernels:
  profile first ([performance.md](performance.md) ladder) — most "slow model code" is data handling or
  unfused ops, not missing kernels. Native boundary adds build/ABI/distribution cost
  ([packaging.md](packaging.md) wheels) and a security surface ([security.md](security.md)).
- Hybrid patterns: keep Python for orchestration; move proven-hot kernels natively; verify with
  before/after measurement (I9).

## Reproducibility, seeds, experiment tracking

- Seeds: set Python/NumPy/framework seeds; know that full determinism on GPUs is often unavailable or
  costly (nondeterministic kernels) [FRAMEWORK/ECOSYSTEM] — claim reproducibility only to the level
  you verified. Deterministic data order + seeded augmentation covers most experiment-drift causes.
- Experiment tracking (MLflow/W&B-class [ECOSYSTEM]): record params, metrics, artifacts, code version,
  data version. The value is comparability and auditability (which data produced this metric?) —
  proportional to how expensive experiments are to rerun.
- Evaluation itself gets engineering discipline: a held-out protocol that survives overfitting
  (repeated peeking at the eval set is training on it), metrics named before runs (not chosen
  post-hoc), and eval data versioned like code ([testing.md](testing.md) property-vs-example
  reasoning applies to eval suites too).
- Data and code versioning together: a metric without its data version is anecdote. Model registry
  promotion (staging → prod) is a release process with rollback ([deployment.md](deployment.md)
  release basics).

## Decision heuristics

- Buy/lease before build: managed training/serving platforms are justified when ops cost exceeds
  platform cost; self-hosted when data gravity/compliance requires [HEURISTIC].
- Serving: compare a maintained dedicated model server with in-process inference
  ([web-frameworks.md](web-frameworks.md)); versioning, warmup, batching, GPU sharing, and isolation
  can justify a server. Check maintenance and dependency compatibility before selecting a product.
  TorchServe's published notice says active maintenance and planned security fixes have ended; treat
  existing deployments as a maintenance decision, not an ordinary new-production default. See
  [TorchServe notice](https://docs.pytorch.org/serve/) and the dated [baseline](modern-python-baseline.md#tool-and-framework-status).
- GPU utilization < 30% steady-state is a pipeline/shape problem before a hardware problem — measure
  ([performance.md](performance.md)) before requesting more GPUs.
