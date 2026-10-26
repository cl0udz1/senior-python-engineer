# Persistence

## Contents

- [SQLAlchemy Session model FRAMEWORK](#sqlalchemy-session-model-framework)
- [Lazy loading and N+1](#lazy-loading-and-n1)
- [ORM vs raw SQL](#orm-vs-raw-sql)
- [Transaction boundary visibility](#transaction-boundary-visibility)
- [Session ownership patterns](#session-ownership-patterns)
- [Migrations](#migrations)
- [Connection pools](#connection-pools)
- [Failures: serialization and retries](#failures-serialization-and-retries)
- [Idempotency for writes (I8)](#idempotency-for-writes-i8)
- [Other stores (conditional)](#other-stores-conditional)

Operational reference for database correctness in Python. The core invariant is I7 (session/transaction
scope visible at the use-case boundary) in [python-invariants.md](../core/python-invariants.md); ORM vs
SQL decisions in [Decision Model §4](../core/decision-model.md). Framework claims are [FRAMEWORK]-tagged.
Version-sensitive facts live only in [modern-python-baseline.md](modern-python-baseline.md).

## SQLAlchemy Session model [FRAMEWORK]

- A `Session` is a **unit-of-work + identity map**: it tracks objects loaded/changed in a transaction and
  flushes/commits them together. It is *not* a generic connection handle and not a thread-safe client.
- Concurrency rules (SQLAlchemy's own model, [FRAMEWORK]):
  - **Session-per-thread**; **AsyncSession-per-task**. NEVER share one Session across threads, nor one
    AsyncSession across concurrent tasks (I7). No exceptions — concurrent use corrupts the unit of
    work and leaks connections.
  - Session lifetime should match a unit of work: per-request, per-job, per command — not per process
    singleton and not per function call created ad hoc in deep helpers.
- `sessionmaker`/`async_sessionmaker` factories + a context manager per unit of work keep this explicit.
  The code that opens and commits the session is where transaction scope becomes visible (I7).

## Lazy loading and N+1

- Relationship attribute access can trigger SQL for each related object not already loaded → **N+1 queries**:
  loading 100 orders with 100 distinct, uncached customers and then touching `order.customer` can issue
  101 queries [FRAMEWORK]. Identity-map reuse or eager loading can reduce that count. Per-row ORM work
  in loops can have the same shape.
- Loading strategies (choose by the access pattern, which is why the pattern must be known):
  - `selectin` / joined / subquery eager loading: fetch relationships in batch when the code will touch
    them. Choose the strategy per access pattern; a model-wide `lazy="selectin"` can over-fetch elsewhere.
  - Explicit queries/bulk fetch for large or variable shapes — fetch the ids/rows you need, not the
    object graph you don't.
  - Use `raiseload` when unexpected relationship access should raise [FRAMEWORK]. In SQLAlchemy 2.0,
    legacy `noload` instead leaves relationships unloaded and can return `None` or an empty collection;
    it is not an error guarantee or proof that no related rows exist. The unit-of-work flush may still
    perform loads despite `raiseload`; verify actual SQL when that distinction matters. See
    [relationship loading](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#preventing-unwanted-lazy-loads-using-raiseload).
- Diagnosis: SQL logging/echo in dev, query-count assertions in tests
  ([testing.md](testing.md)), and profiling ([performance.md](performance.md)). "It works" and
  "it issues 3 queries" are different claims.

## ORM vs raw SQL

- Use the ORM when: entity lifecycle + unit-of-work productivity dominates (CRUD, moderately complex
  object graphs), domain model maps cleanly to tables, and team benefits from identity map/typed models.
- Use raw SQL/`Core` when: query shape dominates (analytics, bulk operations, DB-specific features like
  window functions, CTEs, `INSERT … ON CONFLICT`), or when the ORM abstraction fights the SQL you need.
- "ORMs are slower than SQL" is a banned slogan; ORM overhead is usually the query *pattern* (N+1),
  not the mapping. Mixed use is normal: ORM for aggregates, Core/SQL for set-based reads and bulk
  writes. Decision detail: [Decision Model §4](../core/decision-model.md).

## Transaction boundary visibility

- The unit-of-work boundary (what commits or rolls back together) is visible at the use-case boundary,
  not hidden arbitrarily inside low-level functions (I7). A service function that opens its own session
  cannot compose with another into one transaction; a function that accepts a session participates in
  the caller's transaction — make that contract explicit in the signature.
- Read-only paths still get explicit boundaries (even if they just close the session): leaked sessions
  leak connections.
- Partial-failure semantics: multi-write use cases must state what "all or nothing" covers
  ([reliability.md](reliability.md)); outbox/compensation where a transaction cannot span the DB and
  an external call. Avoid holding a DB transaction open across network I/O unless its lock duration and
  failure behavior are deliberately acceptable [HEURISTIC].

## Session ownership patterns

| Pattern | Ownership | Notes |
|---|---|---|
| Per-request (web) | Middleware/dependency opens, closes at response | FastAPI dependency or Django `ATOMIC_REQUESTS`-style scope [FRAMEWORK]; keep visible (I7) |
| Per-job (worker) | Job boundary owns one session per job | Crash mid-job: rollback on failure, message redelivery ([reliability.md](reliability.md)) |
| Per-command (CLI) | Entry point owns the transaction | Keep helpers session-accepting, not session-creating |
| Background task | Own session per task | Never reuse the request's session; AsyncSession-per-task (I7) |

## Migrations

- Migration tooling is a choice (Alembic for SQLAlchemy, Django migrations, plain SQL migrations) —
  [ECOSYSTEM]; the invariants are tool-neutral:
  - **Forward-only vs reversible**: forward-only + expand/contract is the safer default for
    production data [HEURISTIC]. Reversible migrations are convenient until an `ALTER` can't be undone.
  - **Expand/contract** for zero-downtime schema change: add new column/table (expand), backfill,
    switch code, drop old (contract). Never couple a deploy to a breaking schema change
    ([deployment.md](deployment.md) release ordering).
  - **Test migrations**: run them against a copy of realistic data in CI — a migration that works on an
    empty DB and locks a 50M-row table in prod is a different thing. Measure lock/rewrite cost for
    large tables.
  - Migrations are code: review them ([database-review.md](../reviews/database-review.md)); they are
    part of the data-integrity priority, not boilerplate.

## Connection pools

- Pool size is a **measurement**, not a magic number: calculate the potential total connections across
  instances × processes × each process's pool limit, plus other DB users, and compare with DB
  `max_connections` ([deployment.md](deployment.md)). Oversized pools → DB contention; undersized pools
  → queueing at the pool (which looks like DB latency in profiles).
- Timeouts matter as much as size: pool acquisition timeout, statement timeout, and connection
  recycling/lifetime must exist ([reliability.md](reliability.md)). "Connection pool exhausted" is a
  failure question answered too late.
- **Connection pool fork safety:** do not let parent and child reuse the same live pooled DB
  connections after `fork()` [CPYTHON/FRAMEWORK]. Inherited socket descriptors can corrupt protocol
  streams. Create pools in the worker, or use the documented child initializer pattern with
  `engine.dispose(close=False)`; do not carry a live Session/transaction across the boundary.
  See [SQLAlchemy pool multiprocessing guidance](https://docs.sqlalchemy.org/en/20/core/pooling.html#using-connection-pools-with-multiprocessing-or-os-fork).
- Select a multiprocessing context explicitly when needed: `ctx = multiprocessing.get_context("spawn")`,
  then `ctx.Process(target=worker)`. `Process` has no `start_method` keyword. Deliberate `"fork"` use
  requires a supported platform and a safe process lifecycle; it is no longer the default anywhere
  in Python 3.14. Libraries should accept a caller-supplied context when necessary. See
  [contexts and start methods](https://docs.python.org/3.14/library/multiprocessing.html#contexts-and-start-methods).

## Failures: serialization and retries

- **PostgreSQL errors abort the transaction block** [STANDARD]. Any statement error, not only a
  serialization failure, leaves the transaction aborted: further commands fail with `25P02`
  `in_failed_sql_transaction` until `ROLLBACK`. Retrying the failed statement in that same transaction
  cannot succeed. Serialization failures (`40001`) are the errors PostgreSQL tells you to retry by
  re-running the **whole** transaction, including the logic that chose the SQL. Deadlocks (`40P01`) are
  often retryable the same way. Unique-violation (`23505`) and exclusion-violation (`23P01`) sometimes
  mask a serialization conflict and sometimes are permanent; do not retry those blindly. Roll back
  (`session.rollback()`), then re-execute the unit of work from the start, with a bound and backoff.
  If the transaction is non-idempotent across retries, its external side effects need idempotency first
  (I8).
- Connection loss before commit normally rolls the open transaction back, but loss during or just after
  `COMMIT` can leave the outcome unknown to the caller. Reconcile with a durable operation key or query
  the resulting state before retrying the whole use case; never infer "not applied" from a timeout or
  lost response ([failure-modes.md](../catalogs/failure-modes.md), I8).

## Idempotency for writes (I8)

- Write paths that may be retried (job redelivery, HTTP retry, at-least-once queues) need: an
  idempotency key or natural key with `INSERT … ON CONFLICT DO NOTHING/UPDATE`, a dedupe record, or a
  compensating design. At-least-once delivery means duplicates are normal, not exceptional
  ([reliability.md](reliability.md)).

## Other stores (conditional)

- Choose stores by access pattern, not fashion: key-value cache (Redis) for derived/perishable data
  with named invalidation ([performance.md](performance.md)); document store for schemaless aggregates;
  search engine for full-text/faceted search; queue for buffering ([reliability.md](reliability.md)).
  Each adds operational and consistency cost — the "right store" is the one whose consistency model
  matches the use case's actual requirement ([Decision Model §4](../core/decision-model.md)).
- Polyglot persistence needs a concrete reason per store; a second store is a second failure domain,
  backup story, and consistency question.
- Cache-aside pattern: the cache is a derived copy — the database remains the source of truth; write
  paths state the invalidation order (invalidate-then-read vs write-through) and the staleness budget
  ([performance.md](performance.md) caching semantics). Cached reads under concurrent writers are
  eventually consistent by definition — know which reads may be stale.
