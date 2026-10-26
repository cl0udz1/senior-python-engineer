# Async Review

## Contents

- [Scope & trigger](#scope--trigger)
- [Review contract](#review-contract)
- [Procedure](#procedure)
- [Checklist](#checklist)
- [Quick triage](#quick-triage)
- [Finding format](#finding-format)
- [False positives / legitimate exceptions](#false-positives--legitimate-exceptions)
- [Output expectations](#output-expectations)

Review of asyncio-specific structure: is the loop ever blocked, does cancellation reach real I/O, are
task lifetimes bounded, and do deadlines exist? Thread/process shared-state issues belong in
[concurrency-review.md](concurrency-review.md); the *decision* to go async belongs in
[architecture-review.md](architecture-review.md).

## Scope & trigger

Use when: code uses `asyncio`, `anyio`, ASGI apps (FastAPI/Starlette/Litestar) with async handlers or
dependencies, async DB/HTTP drivers, `TaskGroup`/`create_task`, background tasks, or when symptoms match
async failure patterns (all requests stall together, timeouts that don't cancel work, "Task exception was
never retrieved"). Framework lifecycle caveats are [FRAMEWORK]-local (I10): FastAPI's dependency/threadpool
rules, Flask worker-tied async, Django ORM async caveats apply where those frameworks run.

## Review contract

Follow the shared [review contract](code-review.md#review-contract) for task scope,
priority, severity, evidence, finding format, and a valid clean-review outcome.

## Procedure

1. **Map the async surface**: which entrypoints are async, which dependencies they call, and where the
   loop's request path touches I/O.
2. **Blocking sweep first (I5).** Every call on the request path that can block: sync drivers, `time.sleep`,
   CPU-heavy loops, sync file/network I/O, `subprocess.run`, blocking queue operations.
3. **Dependency-stack audit.** Check each dependency invoked from async code: an async-native client
   can be awaited directly; a blocking client needs a sync route or explicit bounded offload
   ([FRAMEWORK] FastAPI can offload sync dependencies). A sync call directly on the loop is the defect.
4. **Cancellation walk (I6).** From each timeout/cancellation source down to the I/O: can a bare
   `except`, `except BaseException`, explicit `CancelledError` handler, `finally`, or shield suppress or
   delay it? Also check whether `except Exception` hides the caller-facing `TimeoutError`.
5. **Task-lifetime audit.** Every `create_task`/`ensure_future`/`gather`: who awaits it, who bounds it,
   what happens to its exception?
6. **Deadline audit.** Calls that can stall a use case have an effective timeout/deadline reaching the
   actual I/O; growing work has a capacity bound. An inherited deadline can serve several calls.
7. **Resource ownership (I2, I7).** Async sessions/clients per task or per scope, closed explicitly;
   connection-pool size vs task concurrency.
8. **Report** in the standard format; run the loop-lag/blocking check suggested in Verification when
   feasible ([principles §9](../core/engineering-principles.md)).

## Checklist

| Check | Mechanism | Evidence to look for |
|---|---|---|
| Blocking calls on the loop (I5) | One blocking call stalls every coroutine on the loop [FRAMEWORK] | `time.sleep`, sync `requests`/DB drivers, `subprocess.run`, big CPU loops, sync file I/O inside `async def` handlers |
| Async sandwich | Sync framework wrapping async per call, or async handler calling sync framework internals | `asyncio.run()` per request; async def handler wrapping a sync ORM call on the hot path |
| Truly-async dependencies | Declared-async code that internally blocks | Async route → sync HTTP client / sync driver; FastAPI runs *sync* dependencies in its threadpool — mislabeling changes concurrency semantics [FRAMEWORK] |
| Cancellation propagation (I6) | `CancelledError` re-raised if caught, timeouts reach I/O | Bare `except:`, `except BaseException`, `CancelledError`→result, `shield()` around work that should cancel; `except Exception` can hide a caller-facing `TimeoutError`, not `asyncio.CancelledError` |
| Structured lifetimes | An owner joins children and observes outcomes | Fire-and-forget work with no retained owner or shutdown policy; TaskGroup gives lifetime ownership, not a task-count bound |
| `gather` early failure | First exception can reach the caller before siblings finish | No owner joins/cancels surviving work; a timeout wrapper has already finished on the early error; independent work's contract is lost by a blind TaskGroup swap |
| `TaskGroup` exception handling | Non-cancellation failures normally emerge as grouped errors [STANDARD] | `except SpecificError` incorrectly expected to match nested members; `except* SpecificError`, whole-group handling, or propagation may each fit the contract |
| Async generator lifecycle | Async generators closed deterministically on early break | `async for` over an async generator with `break` or exceptions without `async with contextlib.aclosing(agen):` |
| Unbounded task creation | Pending work grows beyond the capacity budget | All input items become tasks before a semaphore; unbounded queues; no admission limit. Neither TaskGroup nor a timeout caps task count |
| Cooperative scheduling | An await need not suspend | Long loops await immediately completed operations while peers cannot run; assess real suspension, not keyword count |
| Missing deadlines | Potentially hanging work lacks an effective bound | Inspect the actual client/driver defaults and enclosing deadline; a missing `wait_for` is not evidence by itself |
| Concurrency limiting | Effective pool/limiter/backpressure protects downstreams | In-flight demand can exceed the downstream's safe capacity or wait budget; check client and pool limits before demanding a semaphore |
| AsyncSession per task (I7) | SQLAlchemy session not shared across concurrent tasks; transaction scope visible to the use case | App-startup session reused by concurrent handlers; commit hidden in a low-level helper — grade by reachable effect |
| Task exception handling (I13) | Task failures recorded | "Task exception was never retrieved" patterns; done callbacks absent; exceptions swallowed in `finally` blocks that also block |
| Event-loop-per-thread misuse | One loop per thread; a free-threaded build does not make that loop's callbacks parallel or shareable [CPYTHON] | A loop object used from two threads; awaiting a `Task` created on another thread; `asyncio.Queue`/`asyncio.Lock` used across threads instead of `queue.Queue` / `threading` plus `call_soon_threadsafe` or `run_coroutine_threadsafe` |

## Quick triage

| Symptom | First checks |
|---|---|
| All requests stall together | Blocking call on the loop (I5): sync driver, `time.sleep`, CPU loop in a handler |
| Timeout fires but work continues | `CancelledError` swallowed; `shield()`; sync work in a thread continues after await cancellation; timeout not reaching the actual I/O (I6) |
| "Task exception was never retrieved" | Fire-and-forget task with no owner and no exception handling |
| Latency grows with traffic while CPU stays low | Unbounded task fan-out; missing semaphore; downstream rate limit hit |
| Memory grows over time | Un-awaited tasks, unclosed sessions/clients (I2), unbounded in-memory queues |
| DB pool exhaustion in an async app | Check session sharing, pool wait, actual concurrent DB demand, and timeout budget (I7) |
| Fine at low load, falls over at high load | Blocking dependency masked by low concurrency; threadpool offload pool saturated |
| Nested `asyncio.run` / loop errors | Event-loop-per-thread misuse; coroutine awaited from the wrong loop |

## Finding format

Per [templates/code-review.md](../templates/code-review.md):
`Severity:` `Evidence:` `Why it matters:` `Recommended change:` `Trade-off:` `Verification:`.

### Example finding (shape only)

- **Severity:** High
- **Evidence:** `handlers/report.py:31` (`async def`) calls the sync `psycopg2` connect/query path;
  `py-spy` dump during a stall shows the loop thread inside `socket.recv`.
- **Why it matters:** one blocking call stalls every coroutine on that loop (I5) — all concurrent
  requests queue behind a single report query.
- **Recommended change:** route this handler through the async driver, or offload the sync block with
  bounded submissions and a timeout on the sync client; account for work that continues after await cancellation.
- **Trade-off:** thread-offload adds a pool to size and monitor; the async driver adds a dependency
  change. Either is smaller than converting the whole service.
- **Verification:** load test at expected concurrency shows p95 flat while reports run; loop-lag
  probe stays under the stated bound.

Grade by demonstrated or plausible impact and reachability, not the MUST/SHOULD label
([invariants](../core/python-invariants.md#using-these-in-reviews)). Evidence names the blocking call or
exception path by location; "this might block" without a mechanism is an assumption.

## False positives / legitimate exceptions

- **Tiny nonblocking CPU work** (constant-time-ish, measured upper bound) in async code is not an I5
  violation; a 200 ms dataframe transform is.
- **Startup-time blocking work before the loop serves traffic** is fine (I5 exception).
- **Explicit bounded offload** (`asyncio.to_thread`, threadpool dependency) is valid when submissions,
  running threads, and the sync client's own timeout fit the capacity budget. Cancelling the await may
  leave the thread running ([asyncio-concurrency.md](../references/asyncio-concurrency.md)).
- **Deliberate shutdown paths** that record-and-drain with a bounded time may catch `CancelledError`
  (I6 exception) if they re-raise/finish within the bound.
- **Deliberate `gather` fan-out** is valid with owned siblings and explicit success, error, cancellation,
  and shutdown paths. A timeout alone does not clean up siblings after an earlier child error.
  See [task lifetime](../references/asyncio-concurrency.md#task-lifetime-cancellation-deadlines).
- **Sync code in an async codebase** is fine when it is off the event-loop path (CLI helpers, scripts).
  Automatic async conversion of everything is a forbidden behavior ([SKILL.md](../SKILL.md)).
- **A framework's threadpool offload of sync dependencies** [FRAMEWORK] is not a finding by itself; a
  finding requires showing the pool or loop saturates under expected load.

## Output expectations

- Lead with the concrete failure ("this 300 ms sync call in `handle()` stalls all concurrent requests
  on the loop"), then the mechanism and fix.
- "No significant issue found." is a valid result — state the surface swept (which handlers, which
  dependency stacks) and what was not covered. Never fabricate findings.
- Fixes stay minimal: offload or async-native API first; converting the whole system to async is not a
  review fix ([evidence-rules §3](../core/evidence-rules.md) — async conversion needs its own evidence).
- Where behavior could not be observed, mark the assumption and the cheapest check (e.g. a loop-lag
  probe under load, `py-spy` dump during a stall).
