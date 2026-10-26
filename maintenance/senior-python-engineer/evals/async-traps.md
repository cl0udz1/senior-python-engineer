# Async Traps

asyncio mechanics and execution-model judgment. Invariants in play: **I5** (no blocking on the loop),
**I6** (cancellation/deadlines propagate), **I7** (AsyncSession-per-task), **I4** (shared state
ownership). Routing: [reviews/async-review.md](../../../senior-python-engineer/reviews/async-review.md),
[references/asyncio-concurrency.md](../../../senior-python-engineer/references/asyncio-concurrency.md),
[playbooks/web-api.md](../../../senior-python-engineer/playbooks/web-api.md). Grading per
[expected-behavior.md](expected-behavior.md) — note the banned slogan "async is faster". The 3.14
free-threaded build is supported but ecosystem-maturing and requires compatibility and shared-state
analysis; the JIT remains experimental ([references/modern-python-baseline.md](../../../senior-python-engineer/references/modern-python-baseline.md)).

---

### Case AS1 — Blocking call inside `async def`

**Input**
> "This async worker sometimes stalls everything for ~10 seconds and I can't figure out why. Any idea?"
>
> ```python
> async def work(client):
>     await client.post("https://api.example.com/ping")
>     time.sleep(10)              # give the service time to settle
>     await client.post("https://api.example.com/report")
> ```
>
> The worker runs 200 of these concurrently on one event loop.

**Context**
One asyncio loop, 200 concurrent `work()` tasks. The stall blocks *all* tasks, not just the sleeping
one. The sleep exists to work around a slow downstream service.

**Desired reasoning behavior**
Diagnose by mechanism: `time.sleep` blocks the thread that runs the event loop, so every coroutine on
that loop stalls ([STANDARD] asyncio scheduling — I5); "sometimes" fits whichever task reaches
the sleep. Explain, then fix along the real axis: the wait is *semantically* a delay → `await
asyncio.sleep(10)` (or better: poll/readiness or retry with backoff on the actual API signal, killing
the magic sleep); if the work were CPU-bound or a sync driver call → bounded thread offload or a
different execution model ([decision-model](../../../senior-python-engineer/core/decision-model.md) §0 tree). Also consider whether
the 200-task fan-out needs bounds and whether the downstream slowness is what should actually be fixed
(deleted sleep > async sleep here). Mechanism + proportional fix, not just the decorator swap.

**Acceptable outcomes**
1. Names the mechanism (event-loop thread blocked; all coroutines stall; that's why "everything" freezes), replaces `time.sleep` with `await asyncio.sleep`, and notes the better fix is removing the magic delay (readiness check / retry on the API).
2. Same diagnosis plus the observation that the sleep is masking a downstream-service behavior — a fix that chases the symptom is second-best.
3. Diagnosis + fix + a bounded-concurrency note (semaphore/`TaskGroup` batches) tied to the 200-task fan-out and connection limits.

**Failure modes**
- "Use `await asyncio.sleep(10)` instead" with no explanation of why the original stalls the loop (right fix, wrong reasoning — Partial).
- Recommending threads, multiprocessing, or free-threading to "fix the sleep" (execution-model mismatch).
- Claiming `time.sleep` "holds the GIL" as the *reason* (slogan-y and imprecise; the loop thread simply cannot run coroutines meanwhile — [CPYTHON] detail misused).

**Critical mistakes**
- Saying blocking calls in coroutines are fine/normal ("FastAPI handles it") (I5 MUST violation presented as fine).
- Claiming all 200 tasks run in parallel on one loop so "sleeping is async anyway" (invented semantics).

---

### Case AS2 — "Make everything async" for performance

**Input**
> "Our FastAPI service is slow. Make everything async for performance — convert all endpoints and
> dependencies to `async def`."
>
> (Service reality: endpoints call a synchronous SQLAlchemy engine with sync sessions, plus a blocking
> `requests`-based internal API client. Current deployment: 4 Uvicorn worker processes running sync
> endpoints in a thread pool. Traffic:
> ~30 req/s, p95 dominated by a 250ms DB query and an 80ms internal API call.)

**Context**
Sync SQLAlchemy engine + sync `requests` client are blocking dependencies. p95 breakdown (from the
APM): DB 250ms wait, internal API 80ms wait, Python CPU <5ms. 30 req/s over 4 processes is nowhere near
thread/process limits. The stated goal is performance.

**Desired reasoning behavior**
Reject the premise, then do the analysis the request actually needs ([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md)
§3 "convert to async": measured concurrency requirement + wait-bound profile + async-capable dependency
audit). Three findings: (1) sprinkling `async def` over blocking calls makes it *worse* — a blocking
driver/`requests` call in a coroutine now stalls the loop (the async-sandwich problem,
[decision-model](../../../senior-python-engineer/core/decision-model.md) §1); (2) the workload is wait-bound but the concurrency
demand is low (30 req/s ÷ 4 processes with sub-350ms waits ≈ a handful of in-flight requests per
process) — sync workers handle this fine; (3) the measured dominant cost is the 250ms DB query — the
optimization question is the query (N+1? missing index? round trips?), not the execution model. If
async is still wanted, keep blocking dependencies off the event loop with bounded offload or sync
endpoints, and migrate to async-native DB/HTTP clients where measured concurrency need justifies the
cost. AsyncSession remains per task when introduced — evidence-gated per §3–§4.

**Acceptable outcomes**
1. Declines blanket conversion; presents the profile-based diagnosis (query first), names the async-sandwich trap explicitly, and states the conditions under which async would be justified (real concurrency spikes, streaming endpoints, async-native dependency migration with measurement).
2. Same, plus a concrete staged path if the team has another reason for async: use sync endpoints or bounded offload around the blocking dependencies while they remain; migrate a dependency to an async-native driver when that boundary pays; keep AsyncSession-per-task where used (I7), and re-measure.
3. Same, plus the intermediate option: keep sync and raise worker/thread capacity *if measured* needed — noting worker counts are measured, never formulaic.

**Failure modes**
- Mechanical conversion: decorate handlers `async def`, keep sync SQLAlchemy/`requests`, declare victory ("everything is async now") — makes latency *worse* under load and hides it.
- "Async is faster" as the argument (banned slogan).
- Recommending the experimental JIT as a drop-in speed fix, or the supported free-threaded build without a workload/extension/shared-state audit.
- Micro-optimizing Python CPU <5ms of work while the 250ms query goes unexamined.

**Critical mistakes**
- Shipping the blocking-in-coroutine conversion and presenting it as an improvement (I5 MUST violation presented as fine).
- Claiming async reduces the latency of a DB query (invented mechanism).

---

### Case AS3 — CPU-heavy work on the event loop

**Input**
> "I made my API async but it's still slow. It computes SHA-256 over uploaded files and runs a JSON
> schema validation in pure Python over large payloads:
>
> ```python
> async def process(payload: bytes, doc: dict):
>     digest = hashlib.sha256(payload).hexdigest()
>     validate_all_fields(doc)          # pure-Python, ~200ms per call
>     await save(digest, doc)
> ```
>
> Concurrent load: 50 requests in flight. `validate_all_fields` is ~200ms of pure Python per call."

**Context**
Both `hashlib.sha256` on big payloads and `validate_all_fields` are synchronous CPU work. On one event
loop, the 200ms pure-Python validation burst blocks other requests. Hashlib may release the GIL on
large buffers, but the event-loop thread still cannot schedule other coroutines during the call. The
naive profile says "async didn't help".

**Desired reasoning behavior**
Classify before choosing tools ([decision-model](../../../senior-python-engineer/core/decision-model.md) §0): CPU-bound Python work
on an event loop = blocking (I5); asyncio is a concurrency *multiplexer* for waits, not a CPU
parallelizer — 50 concurrent CPU-bound coroutines on one loop serialize and also starve the I/O
handlers. Then walk the evidence ladder: (1) can `validate_all_fields` do less work or use a suitable
native-backed validator, and can hashing move into the save pipeline; (2) batch only where the actual
validation contract permits; (3) then consider execution model: bounded
`asyncio.to_thread`/process pool offload for real concurrency, or a worker process model, or
free-threaded build **only** after extension-compat + data-race audit (supported but
ecosystem-maturing, never "just enable it"); (4) microservices/native rewrite only with profile proof
and stated target. Thread offload unblocks the loop but does not parallelize the pure-Python validator
under the conventional GIL; native hashing may release the GIL ([CPYTHON]). Processes or native code
are the CPU-parallelism answers when a pure-Python hot loop remains.

**Acceptable outcomes**
1. Diagnoses CPU-bound-on-loop (each 200ms burst stalls the loop; async gains nothing for CPU), then ladder: replace/accelerate the validator (native-backed lib), batch/hash smartly, offload to `run_in_executor`/process pool with bounded workers, re-measure. Names free-threading conditions (compat + race audit) without promoting it.
2. Same, with the workload math shown (50 × 200ms = 10s of serialized CPU per burst window) making the queueing behavior concrete.
3. Same, plus deciding the *right* boundary: move validation to the ingestion worker / a job queue if latency-sensitive traffic shouldn't share CPU with validation — with the named need (isolation) that a queue requires.

**Failure modes**
- "Add more uvicorn workers / threads / enable the JIT" without classifying the bottleneck.
- "Rewrite validation in Rust" as the first move (automatic Rust rewrite).
- Wrapping `validate_all_fields` in `await asyncio.sleep(0)` or an `async def` wrapper and claiming it's now async (mechanism misunderstanding).
- Free-threading recommended as a drop-in fix ("just build with --disable-gil").

**Critical mistakes**
- Claiming asyncio gives parallel execution of CPU-bound Python (invented semantics; banned "async is faster" family).
- Claiming a free-threaded build makes this one event loop run those coroutines on multiple cores. Since 3.14 the asyncio implementation is thread-safe on that build, and one loop still runs its callbacks serially ([references/asyncio-concurrency.md](../../../senior-python-engineer/references/asyncio-concurrency.md)).
- Claiming free-threaded CPython guarantees arbitrary shared mutable state is safe without synchronization (invented CPython guarantee; material I4 violation if acted on).

---

### Case AS4 — Shared AsyncSession across concurrent tasks

**Input**
> "We see intermittent `InvalidRequestError` / weird interleaved results under load in this FastAPI
> endpoint. Any idea?"
>
> ```python
> session = AsyncSession(engine)          # created at startup, stored on app.state
>
> async def get_dashboard(user_id: str):
>     user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
>     loans = (await session.execute(select(Loan).where(Loan.owner == user_id))).scalars().all()
>     stats = (await session.execute(stats_stmt)).scalar_one()
>     return build(user, loans, stats)
> ```
>
> Endpoints also mutate data through the same shared session.

**Context**
One `AsyncSession` shared by all concurrent requests/tasks. Intermittent failures only under load;
works fine single-threaded in tests. The team suspects "a race in SQLAlchemy".

**Desired reasoning behavior**
Name the [FRAMEWORK] rule, not a mystery: SQLAlchemy's unit-of-work/identity-map Session is
session-per-thread and **AsyncSession-per-task; never shared across concurrent tasks** ([I7](../../../senior-python-engineer/core/python-invariants.md)). Under
concurrent awaits, interleaved `execute()` calls stomp each other's identity map/transaction state —
the exact symptom. Fix shape: create a session per request/task (`async with AsyncSession(engine) as
session:` per use case, or a dependency with `yield`), make the transaction scope visible at the
use-case boundary (what commits/rolls back together), and note that a mutation + read sequence in one
request shares one transaction deliberately. Also worth checking connection-pool sizing vs. concurrency
(resource ownership, I2). Do not "fix" it with a global lock around the session (that serializes the
service and hides the ownership error).

**Acceptable outcomes**
1. Diagnosis + fix: per-task session via dependency/context manager, visible unit-of-work boundary per request, brief note on pool sizing; explains why single-task tests never show it.
2. Same, plus explicit transaction design for the mutating endpoints (one commit per use case; rollback on error) and a concurrency test suggestion (two concurrent requests against an in-memory/CI Postgres).
3. Same core fix, framed as ownership: "the session's owner is the request task; a module-level session has no owner and N owners at once" (I4/I7 language).

**Failure modes**
- Adding `asyncio.Lock` around session calls to "stop the race" (serializes everything; keeps the wrong ownership).
- Upgrading/downgrading SQLAlchemy versions, blaming asyncpg, or switching to raw SQL to dodge the issue (evidence-free migration).
- Concluding "asyncio has races, use threads" (banned-slogan/invented semantics).

**Critical mistakes**
- Recommending keeping the shared session with "it's fine, sessions are thread-safe-ish" (I7 MUST violation presented as fine — SQLAlchemy explicitly forbids concurrent sharing).
- Claiming the failures are a SQLAlchemy bug without evidence (fabricated diagnosis).

---

### Case AS5 — Cancellation and timeouts swallowed

**Input**
> "Timeouts don't work in our async pipeline — we set them but errors just disappear and we get `None`:
>
> ```python
> async def run_pipeline():
>     try:
>         return await asyncio.wait_for(fetch_and_store(), timeout=5)
>     except Exception:
>         log.warning("pipeline step failed; continuing")
>         return None
>
> async def fetch_and_store():
>     try:
>         data = await fetch_remote()   # sometimes hangs 60s+ at the transport
>         await store(data)             # commits in stages
>     except Exception:
>         log.warning("fetch_and_store failed; continuing")
>         return None
> ```
> The caller can't tell 'no data' from 'timed out' from 'crashed'."

**Context**
`asyncio.wait_for` reports its timeout to the caller as `TimeoutError` (an `Exception` subclass in
modern Python) while cancellation is delivered into the coroutine as `CancelledError`. `store` may
have committed partial state before whatever cut the run short. Callers key retry/alerting behavior on
the return value.

**Desired reasoning behavior**
Multi-layer discipline ([I6](../../../senior-python-engineer/core/python-invariants.md) + I13 + I8): (1) the broad `except Exception` at pipeline level erases the
timeout signal — `TimeoutError` is an `Exception` subclass, so "timeouts don't work" is really "the
timeout happened and the handler swallowed it"; callers can't distinguish no-data / timeout / failure
(I13 — failure must remain visible); (2) distinguish this from task cancellation: modern
`asyncio.CancelledError` inherits `BaseException`, so the shown `except Exception` blocks do not catch
it. Check that the transport and any cleanup layers propagate cancellation; re-raise it if explicitly
caught (I6). Do not invent a swallowed-cancellation bug in this snippet; (3) partial state: `store` may
have committed before the timeout — make the
stage idempotent/transactional so a rerun is safe (I8/I7); (4) the 60s transport hang needs its own
deadline at the lowest level that can act (client timeout params), not just an outer `wait_for`. Fix
shape: narrow exception handling, distinct error types (or raising) so failure states are
distinguishable, `except CancelledError: raise` discipline, transport-level timeouts.

**Acceptable outcomes**
1. Finds all layers: timeout signal erased by `except Exception`, failures hidden by catch-and-return (I13), cancellation is *not* caught by these handlers but must propagate through transport/cleanup (I6), and partial-commit rerun safety (I8) — with fixes for each.
2. Same, plus the API-shape fix: callers get typed failures (raise domain errors / result enum) instead of `None`.
3. Leads with the debugging question "what does `wait_for` raise to the caller, and where is it caught?" and walks the mechanism to the answer (structured reasoning rewarded).

**Failure modes**
- "Replace `except Exception` with `except Error` and done" while missing the cancellation and partial-write layers (Partial at best).
- Suggesting increasing the timeout (symptom) or converting to threads.
- Treating both `except Exception` blocks as fine because "they log" (I13 is about visibility of failure states to the caller, not log presence).

**Critical mistakes**
- Recommending `except BaseException: pass` or suppressing `CancelledError` and presenting it as fine (material I6 violation).
- Asserting asyncio timeout/cancellation semantics that contradict documented behavior (invented fact — e.g. claiming `CancelledError` is an `Exception` subclass flowing through these handlers).

---

### Case AS6 — Unbounded task spawning

**Input**
> "Our async ingestion endpoint occasionally OOMs and the DB connection pool maxes out under burst
> traffic. Code sketch:
>
> ```python
> @app.post("/ingest")
> async def ingest(batch: list[Item]):
>     for item in batch:
>         asyncio.create_task(handle(item))
>     return {"accepted": len(batch)}
> ```
> `handle` opens its own DB connection and calls an external API. Batch size is unbounded (clients
> send whatever they want).

**Context**
Burst traffic arrives in waves; each `handle` holds a pool connection for its duration. Task references
are dropped immediately after `create_task`. No queue, no admission control.

**Desired reasoning behavior**
Find the compound ownership failure (I4/I13 + [decision-model](../../../senior-python-engineer/core/decision-model.md) §1 "unbounded
create_task is a defect"): (1) no bounds — N items × burst = unbounded concurrent tasks, each holding a
pool connection → pool exhaustion and OOM by design, not by accident; (2) dropped task references mean
tasks can be garbage-collected mid-flight ([CPYTHON] caveat: fire-and-forget without keeping a
reference is a documented footgun) and errors vanish (I13 — who observes `handle` failures?); (3) no
backpressure — the endpoint acknowledges work it has not bounded capacity for. Fix shapes: bounded
semaphore or worker pool with a bounded queue + real backpressure (return 429/queue-depth signal),
an application-lifespan supervisor or task set to own in-process task lifetimes, bound the batch size
at the validation boundary (I1), surface per-item failures (result collection/dead-letter), and size
the pool vs. concurrency deliberately (measured). A request-scoped `TaskGroup` can await completion,
but then the response reports completed work, not background acceptance. If the endpoint must promise
durable acceptance, persist each job to a bounded queue before returning and make handlers idempotent
(I8). If it cannot persist, describe the acceptance as best-effort and expose failure/loss semantics.

**Acceptable outcomes**
1. Names all three defects (unbounded concurrency, lost task references/silent failures, no backpressure) and proposes bounded execution (worker pool/queue or semaphore after admission) + owned task set + input bound + failure visibility. It distinguishes accepted work from completed or durable work.
2. Same, with the capacity math sketched (max in-flight ≤ pool size ÷ connections-per-task) and the client-visible overload behavior defined.
3. Moves the work to a durable queue/worker design *with* the named justification (bursts must not size the request path; retries independent), an idempotency answer, and an acknowledgement only after persistence succeeds.

**Failure modes**
- "Add a sleep between tasks" or "catch exceptions inside handle" — symptom patches (failure modes remain: unbounded, invisible).
- Keep `create_task` and just raise the pool size (capacity reasoning missing).
- Introduce Kafka + 3 services for the fix (disproportionate vs. a semaphore).

**Critical mistakes**
- Presenting the shown endpoint as a reliable "accepted" contract while tasks can be lost and their errors vanish (material I13 violation presented as fine).
- Claiming asyncio tasks cannot be garbage-collected / or that they are always safe without references, contradicting documented semantics (invented fact).

---

### Case AS7 — A sync-only SDK inside one async route

**Input**
> "Our ASGI service has one streaming route that must stay async. A vendor SDK used once per request
> is sync-only and blocks for 100–300ms. We can serve at most 20 simultaneous vendor calls. Should we
> replace the SDK or convert the whole service to sync? Show the smallest safe implementation shape."

**Context**
The SDK releases the GIL while waiting on network I/O. No supported async SDK exists. The route
streams data before and after the call; the rest of the service is healthy. The vendor permits 20
in-flight requests and exposes timeouts. Replacing the SDK would be a substantial migration.

**Desired reasoning behavior**
Classify the wait and preserve the useful async streaming route. An explicit bounded offload of the
sync call (framework thread pool or `asyncio.to_thread` behind admission control), with vendor timeout,
is a valid hybrid boundary. Limit queued as well as active work so bursts do not create unlimited
waiting tasks; name cancellation's limit: cancelling the await does not necessarily stop an in-flight
thread or remote operation. An async-native client would need a real benefit and compatible API, not a
blanket rule that sync and async code can never mix (I5/I8 and [references/asyncio-concurrency.md](../../../senior-python-engineer/references/asyncio-concurrency.md)).

**Acceptable outcomes**
1. Keeps the route async and offloads the SDK call behind a 20-call concurrency/admission bound, sets the SDK timeout, and explains cancellation/unknown-outcome behavior.
2. Same, with a small code sketch using a bounded worker pool and a queue limit, plus a test for overload and timeout behavior.
3. Moves only the vendor step to an owned worker queue if its completion need not occur in the response, with a stated delivery and retry contract.

**Failure modes**
- Calling the sync SDK directly on the event-loop thread (I5).
- Requiring a whole-service rewrite or an unmaintained async client solely to avoid a hybrid boundary.
- Using unbounded `to_thread` calls and assuming the vendor limit will enforce local backpressure.
- Claiming cancellation of the await cancels the already-running thread or remote side effect.

**Critical mistakes**
- Presenting direct blocking SDK calls on the busy event loop as safe (material I5 violation).
- Inventing a guarantee that cancelling `to_thread` stops the underlying call (invented execution-model fact).

---

### Case AS8 — `asyncio.gather` error handling and sibling task leakage

**Input**
> "Review this async orchestrator function. It queries three microservices concurrently to assemble a user dashboard:
>
> ```python
> async def fetch_user_dashboard(user_id: str) -> dict[str, Any]:
>     profile_task = asyncio.create_task(fetch_profile(user_id))
>     billing_task = asyncio.create_task(fetch_billing(user_id))
>     recommendations_task = asyncio.create_task(fetch_recommendations(user_id))
>     
>     try:
>         profile, billing, recs = await asyncio.gather(
>             profile_task, billing_task, recommendations_task
>         )
>     except BillingServiceError:
>         logger.warning("Billing service failed for %s, falling back", user_id)
>         profile = await profile_task
>         return {"profile": profile, "billing": None, "recommendations": []}
>         
>     return {"profile": profile, "billing": billing, "recommendations": recs}
> ```
>
> The author says: 'If billing fails, we catch the exception and return a degraded dashboard with the user profile.' Is this implementation correct and robust?"

**Context**
`fetch_recommendations` normally takes 800 ms, `fetch_profile` 50 ms, and billing fails after
10 ms with `BillingServiceError`. A valid profile is required. On that billing error, return the
profile-only fallback without waiting for recommendations to finish; cancel and await unnecessary
owned work before returning. Profile failure must propagate, and caller cancellation must stop and
await all owned child tasks. Normal success returns all three results. Calls cooperate with
cancellation and complete cleanup promptly. Other service failures propagate after cleanup.

**Desired reasoning behavior**
Explain the actual lifetime contract: default `gather` propagates an early child exception while
siblings can continue. The missing operation is cancellation and draining of recommendations once
billing degradation makes them unnecessary. Awaiting the required profile in the error handler is
valid; propagation of its failure is part of the stated contract, not inherently a race bug.

Do not infer an unretrieved-exception warning merely because the handler stopped awaiting the outer
`gather`: CPython's gather callback retrieves later child exceptions after the outer future is done.
The unwanted surviving work is the defect independently of warning behavior. Do not require the
phrase "Task exception was never retrieved" for credit.

A direct replacement by an unqualified TaskGroup can cancel the profile needed for fallback.
`return_exceptions=True` alone waits for unnecessary recommendations and changes fallback latency.
Accept an explicit owned-task cleanup policy, optional-error normalization with a suitable lifetime
structure, or another implementation preserving all visible contracts. Judge observable outcomes;
do not require a particular concurrency primitive or private chain of thought.

**Acceptable outcomes**
1. Keeps the required profile alive on billing degradation, cancels and drains unnecessary recommendations, and handles normal success, profile failure, caller cancellation, and other service failures under explicit ownership.
2. Uses structured concurrency with billing failure converted to a domain result and a deliberate policy for stopping recommendations, preserving the same profile fallback and cleanup contract.
3. Gives an evidence-backed review identifying the surviving-work defect and the pitfalls of both naive replacements, with targeted tests proposed. Implementation is not required by this review prompt.

**Failure modes**
- Approving the unwanted surviving recommendations work as robust fallback behavior.
- Blindly switching to TaskGroup and cancelling a still-needed profile.
- Waiting for all optional work with `return_exceptions=True` without acknowledging the changed contract.
- Cancelling children without awaiting cleanup, or treating a required profile failure as successful degradation.

**Critical mistakes**
- **C4 — invented contract fact:** asserting that default `gather` automatically cancels siblings on an ordinary child exception, or necessarily emits an unretrieved-exception warning for this later gathered failure.
- **C2 — harmful invariant violation presented as fine:** presenting swallowed caller cancellation and demonstrated surviving owned work as safe.

Sources: [Python asyncio task documentation](https://docs.python.org/3.14/library/asyncio-task.html#asyncio.gather)
and [released CPython gather implementation](https://github.com/python/cpython/blob/v3.14.0/Lib/asyncio/tasks.py).
The [FX01 fixture](fixtures/FX01/task.md) tests cleanup and fallback outcomes, not CPython warning text.
