# asyncio and Concurrency

## Contents

- [Classify the workload first](#classify-the-workload-first)
- [asyncio model](#asyncio-model)
- [Threads](#threads)
- [Processes](#processes)
- [Free-threaded CPython and multiple interpreters](#free-threaded-cpython-and-multiple-interpreters)
- [Async production failure list](#async-production-failure-list)
- [Choosing (summary)](#choosing-summary)

Operational reference for Python concurrency: asyncio, threads, processes, and emerging interpreter
capabilities. Version-sensitive facts live only in [modern-python-baseline.md](modern-python-baseline.md).
Invariants I1–I16 from [python-invariants.md](../core/python-invariants.md); execution-model decisions in
[Decision Model §1](../core/decision-model.md).

## Classify the workload first

- **Wait-bound (I/O)**: time is spent waiting on network, disk, DB, subprocesses. **CPU-bound**:
  time is spent executing Python/numeric work. Most services are wait-bound; most data loops are
  CPU-bound. Measure before classifying ([Evidence Rules §3](../core/evidence-rules.md)).
- The concurrency question is never "async or threads — which is faster?" but "what must run
  concurrently, and what does my dependency stack support?"
  - IF one process must multiplex many cooperative waits AND the dependency stack is async-capable
    (async DB driver, async HTTP client) → consider asyncio.
  - IF the work is blocking I/O with a sync library → threads often suffice; a sync codebase stays simple.
  - IF CPU-bound Python → remove the Python loop first (algorithm/vectorization, [performance.md](performance.md));
    then processes (or validated free-threading) for parallelism.
  - ELSE keep the simplest execution model. "Async is faster" is a banned slogan; async is a
    structuring tool for concurrency, not a speed dial.

## asyncio model

- asyncio tasks cooperate on an event loop [STANDARD]. Other tasks can run when the current task
  **actually suspends**; an `await` whose result is already available need not yield. A loop of
  `await immediate_result()` can starve peers. If a long loop needs a cooperative checkpoint,
  `await asyncio.sleep(0)` suspends; it does not make CPU-heavy work cheap or belong in every handler.
  See the [asyncio conceptual overview](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html).
- Vocabulary: `async def` defines a coroutine function; calling it creates a coroutine object. A
  `Task` schedules that object; a `Future` is a placeholder result. `asyncio.run()` creates and closes
  an event loop for one top-level call.
- One loop = one thread. Concurrent tasks interleave, not parallelize. CPU work in a coroutine is
  CPU work stolen from every other task on the loop.

### Blocking calls on the loop (I5)

```python
async def handler(request):
    data = time.sleep(2) or fetch_from_sync_api()   # BUG: stalls EVERY task on the loop
```

- `time.sleep(2)` in a coroutine blocks the entire loop for 2s — every other request, timeout, and
  heartbeat on that loop freezes with it [FRAMEWORK] (FastAPI/Starlette and all ASGI servers share this
  model). Use `await asyncio.sleep(2)`, an async-native client, or bounded thread offload
  (`asyncio.to_thread` / `run_in_executor`) for genuinely blocking libraries.
- Offload is not a cure-all: thread offload has overhead and still consumes a thread per concurrent
  blocking call — bound the underlying work and waiting queue, or move the dependency to its own worker
  ([web-frameworks.md](web-frameworks.md) on async-vs-blocking dependencies).
- Cancelling an await of `asyncio.to_thread` generally does not stop the synchronous function already
  running in its thread. Give that client its own timeout and account for continued work during shutdown
  and capacity planning; a semaphore released by the cancelled await no longer bounds those threads.

### The async sandwich problem

- Pattern: a high-concurrency sync entry creates a fresh event loop per call while most work remains
  blocking, or an async handler directly invokes a synchronous dependency. This pays async complexity
  without gaining useful multiplexing. A one-shot CLI using `asyncio.run()` is normal.
- Diagnosis: does any `await` actually overlap work, and is blocking I/O offloaded? If concurrency is
  always one, the async layer may be unnecessary. Keep the simpler model or isolate blocking work behind
  a bounded worker/thread boundary.

### Task lifetime, cancellation, deadlines

- `TaskGroup` awaits its children; a child failure other than `CancelledError` cancels siblings and
  normally emerges as an exception group [STANDARD]. Use it when fail-fast sibling cancellation fits
  the use case. It owns lifetime, not admission capacity. Cancellation-resistant children can delay exit.
- Handle matching grouped errors with `except* SpecificError`; an ordinary `except SpecificError`
  does not match nested members. Catching the whole `ExceptionGroup` or propagating it is also valid.
  `KeyboardInterrupt` and `SystemExit` receive special treatment. See [Task groups](https://docs.python.org/3.14/library/asyncio-task.html#task-groups).
- **`gather` failure policy:** with `return_exceptions=False`, the first exception propagates while
  siblings keep running. Retain an owner that joins/cancels them, or deliberately preserves and observes
  independent work. Surviving tasks are not automatically leaks; the defect is violating their promised
  lifecycle or side-effect boundary. A timeout wrapper alone cannot repair early-error cleanup: once
  `wait_for(gather(...), limit)` has raised a child error, its timer no longer controls surviving siblings.
  Calling `gather.cancel()` after it is done does not cancel those children. See [gather](https://docs.python.org/3.14/library/asyncio-task.html#asyncio.gather).
- **Async generator lifecycle (`contextlib.aclosing`)** [STANDARD]: `async for` does not by itself await
  `aclose()` when iteration stops early (`break` or an exception). Cleanup can then run later, outside the
  task and context that was iterating. When a generator might be abandoned before exhaustion, wrap it:
  `async with contextlib.aclosing(agen):`. Full consumption is the other path; `aclosing` is the early-exit
  path, not a second copy of every loop.
- Cancellation (I6): `asyncio.CancelledError` directly subclasses `BaseException` [STANDARD] —
  `except Exception` won't catch it, but `except BaseException`, bare `except`, an explicit
  `except CancelledError`, or a `return` in `finally` can swallow it. Rules: normally preserve
  cancellation; re-raise after cleanup; use `try/finally` (not `except Exception: pass`) for cleanup.
  Use `asyncio.shield` sparingly for critical cleanup or an independently owned task that must finish;
  retain and observe that task, and define a shutdown bound because it may continue after the caller
  is cancelled.
- `asyncio.wait_for(coro, t)` cancels the inner operation on timeout and awaits its cancellation —
  the inner must be cancellation-responsive or the timeout is fiction. `asyncio.timeout` (context form)
  scopes a deadline to a block.
- Deadlines vs timeouts: a **timeout** bounds one call; a **deadline** bounds the whole use case and
  should shrink as it propagates down the call chain. Design notes in [reliability.md](reliability.md).

### Unbounded work

- Inspect three separate limits: accepted/pending work, simultaneously running work, and time to
  completion. A semaphore limits holders, not the number of tasks waiting for it; `TaskGroup` joins
  children but does not limit how many are created. For growing input, use bounded admission/queues
  and a fixed number of consumers, or another measured capacity policy. A known small finite batch
  can use simple fan-out. Choose limits from expected load and downstream capacity.

## Threads

- [CPYTHON] On conventional builds a GIL prevents multiple threads from simultaneously executing Python
  bytecode; blocking I/O (and many C-extension calls) commonly release it. Consequences:
  - Threads remain genuinely useful for **blocking I/O concurrency** and syncing with synchronous
    libraries — the "GIL makes threads useless" slogan is false.
  - Threads do not give CPU parallelism for pure-Python CPU work on conventional builds. The
    free-threaded build changes this (below) — verify against [baseline](modern-python-baseline.md)
    before designing around it.
- Shared mutable state across threads needs explicit ownership + synchronization (I4): locks, queues,
  single-writer confinement. `ThreadPoolExecutor` for bounded offload; daemon threads are for
  process-lifetime helpers, not jobs that must finish.
- Threads interleave at arbitrary points (unlike asyncio), so races are harder to reproduce. If you can
  avoid shared mutable state entirely (message passing, immutable snapshots), do.

## Processes

- Processes give isolation and true CPU parallelism at the cost of serialization and coordination.
  `ProcessPoolExecutor`/`multiprocessing` ship work via pickling: argument and result types must be
  picklable, large data pays copy cost per transfer, and `multiprocessing.Connection.recv()`
  **auto-unpickles** — even internal IPC is a trust boundary ([security.md](security.md)).
- Startup cost and memory per worker are real: processes fit coarse-grained work (batch jobs, per-shard
  computation), not per-request fan-out. On `spawn` platforms every worker re-imports your modules —
  import-time side effects multiply (I3).

## Free-threaded CPython and multiple interpreters

- **Free-threaded CPython (PEP 779)** [CPYTHON; supported-but-maturing]: officially supported in
  the current baseline (see [baseline](modern-python-baseline.md)) but the extension ecosystem is still
  maturing. Facts that matter:
  - Removing the GIL does **not** repeal data races (I4). Multi-step operations shared between threads
    need a documented ownership/synchronization argument. Loop-confined state with no suspension,
    reentrancy, or outside-thread access has a different interleaving model; do not add locks solely
    because an operation spans several Python expressions.
  - Incompatible native extensions can cause the GIL to be re-enabled at runtime — a deployment that
    depends on GIL-free behavior must verify its whole extension stack
    ([dependency-review.md](../reviews/dependency-review.md)).
  - Since 3.14, asyncio itself is safe to use on a free-threaded build, and CPU work off the loop can
    run in parallel. **One event loop still executes its callbacks serially on one thread.** Do not
    share a loop across threads. Do not await or mutate a `Task` created on another thread. `asyncio.Lock`,
    `asyncio.Event`, and `asyncio.Queue` are loop-local; cross-thread handoff uses `threading` primitives,
    `queue.Queue`, `loop.call_soon_threadsafe`, or `asyncio.run_coroutine_threadsafe`. Scaling is one loop
    per thread, after the same extension and shared-state audit — not "the loop is now parallel."
  - "Make everything multithreaded" is not the takeaway. Adopt for measured CPU-parallelism needs after
    compatibility testing, not as a default.
- **Multiple interpreters (PEP 734)** [STANDARD; new]: per-interpreter state reduces some sharing hazards,
  but cross-interpreter communication has explicit serialization/communication cost and the accumulated
  operational experience is limited. Be conservative: an ordinary process boundary is the mature
  alternative with the same isolation shape.

## Async production failure list

| Failure | Mechanism | Prevention |
|---|---|---|
| Blocking call on loop (I5) | One sync call stalls all tasks | Async-native deps, bounded offload, or another model |
| Swallowed `CancelledError` (I6) | Bare `except`, `except BaseException`, explicit suppression, or `return` in `finally` | Normally re-raise; cleanup in `finally` |
| Unowned gather siblings | First error returns before siblings finish | Use fail-fast ownership when appropriate; otherwise retain, observe, and join independent tasks |
| Async generator leak on break | Early `break`/exception does not await `aclose()` in the iterating task | `async with contextlib.aclosing(agen)` when iteration can stop early |
| Unbounded tasks/queues | Accepted work grows faster than it finishes | Bound admission, queued work, and active workers; structured lifetime alone does not cap capacity |
| Missing deadlines | Slow dependency accumulates work | Per-call timeouts + end-to-end deadline |
| Shared non-thread-safe resource in tasks | Sync driver/session used concurrently | Session-per-task (I7), explicit ownership (I4) |
| Non-idempotent retries (I8) | Timeout ≠ failure; retry duplicates work | Idempotency analysis before any retry |
| The async sandwich | Async wrapper directly calling blocking work | Use a coherent model or bounded offload |
| Unnecessary per-request event loops | Loop setup cost with no overlapping work | Sync path or a long-lived loop when concurrency requires it |

## Choosing (summary)

Use the conditional flow in [Decision Model §1](../core/decision-model.md). The decision inputs are:
workload class, dependency async-compatibility, required concurrency level, team's ability to reason
about the model, and operational constraints. The output is a named trade-off — not a fashion choice.
