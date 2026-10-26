# Database Review

## Contents

- [Scope & trigger](#scope--trigger)
- [Review contract](#review-contract)
- [Procedure](#procedure)
- [Checklist](#checklist)
- [Finding format](#finding-format)
- [False positives / legitimate exceptions](#false-positives--legitimate-exceptions)
- [Output expectations](#output-expectations)

Persistence-layer review: transaction/session ownership, query shape, and migration safety. The core
question is not "ORM or SQL" but *who owns the transaction, and what does the database actually receive*.
Query performance claims route through [performance-review.md](performance-review.md) evidence rules;
injection surface routes to [security-review.md](security-review.md).

## Scope & trigger

Use when: code touches a database via ORM or raw SQL (SQLAlchemy, Django ORM, DBAPI drivers, async
drivers); transactions span multiple steps; N+1 symptoms appear (latency grows with result size);
connection-pool errors appear under load; migrations are written or run; retry logic wraps DB calls;
or a data-consistency bug is suspected. Design-level ownership questions belong in
[architecture-review.md](architecture-review.md).

## Review contract

Follow the shared [review contract](code-review.md#review-contract) for task scope,
priority, severity, evidence, finding format, and a valid clean-review outcome.

## Procedure

1. **Map session/transaction ownership (I7).** Who creates the Session/AsyncSession, in which thread or
    task, and where does the unit of work commit or roll back? The boundary must be visible at the
    use-case level. SQLAlchemy's recommended model is Session per thread, AsyncSession per task;
    concurrent sharing of one session is unsafe [FRAMEWORK].
2. **Read the SQL, not just the Python.** Enable query logging (`echo=True`, engine events, DB slow-log)
   for the paths under review. Object access patterns and SQL round trips must be judged together.
3. **Check query shape**: N+1 lazy loads, over-eager loading, missing pagination, `SELECT *` on wide
   tables, per-row inserts instead of bulk operations.
4. **Check transaction width and isolation**: how long does the transaction live, what does it hold
   (locks, connections), does it span external calls; which isolation level and which anomalies the
   code assumes away.
5. **Check retry semantics (I8).** Serialization-conflict failures retry the *whole transaction*, not a
   single statement [FRAMEWORK]; every retried write answers "can this safely happen twice?".
6. **Check migration safety**: expand-contract, backfill plan, reversibility, test against realistic
   volume, compatibility of old code with the new schema during rollout
   ([templates/migration-plan.md](../templates/migration-plan.md)).
7. **Check pool sizing** against actual concurrency (workers × tasks per worker), not formulas.
8. **Report** findings in the standard format; verify claims by running the query/logging evidence where
   possible ([principles §9](../core/engineering-principles.md)).

### Inspecting the SQL (evidence gathering)

Findings here need query-level evidence, not vibes. Cheap sources, before touching production:

- SQLAlchemy: `create_engine(..., echo=True)` in a safe test environment or counters registered with
  `sqlalchemy.event.listen(engine, "before_cursor_execute", ...)`; assert query counts in tests to pin
  N+1 fixes without logging sensitive production values.
- Django ORM: `django.db.connection.queries` / `assertNumQueries` in tests [FRAMEWORK].
- The database itself: slow query log, `EXPLAIN`/`EXPLAIN ANALYZE` for candidate statements,
  `pg_stat_statements`-style aggregates when available.
- Pool behavior: client-side pool logs (checkout timeouts) correlated with concurrent task counts.

## Checklist

| Check | Mechanism | Evidence to look for |
|---|---|---|
| Session/thread/task ownership (I7) | SQLAlchemy Session/AsyncSession not shared concurrently [FRAMEWORK] | Module-level or app-startup session reused by concurrent requests/tasks; session passed into concurrently awaited calls — grade by effect |
| Transaction boundary visible (I7) | The unit of work is visible at the use-case level | `commit()` buried in a repository helper called from multiple use cases; two use cases sharing one commit scope unintentionally |
| N+1 lazy loads | Lazy relationships fire per-object queries | Accessing `obj.children` in a loop; query count scaling with result size when logging is enabled |
| Eager/select-in fit | Loading strategy matches access pattern | `selectin`/`joinedload` missing for known access patterns; `joinedload` on large collections causing row explosion |
| ORM vs raw SQL fit | Conditional: entity/unit-of-work productivity vs query-shape/bulk/DB-specific needs | Bulk updates done row-by-row through the ORM; hand-written SQL duplicating simple ORM work — either can be right; "ORMs are slower" is a banned slogan, not a finding |
| Connection pool sizing | Pool size vs workers × task concurrency; pool exhaustion visible | `TimeoutError: queue pool limit` in logs; pool default under high task concurrency |
| Connection pool fork safety (I7) | SQLAlchemy `Engine` or pool shared across `fork()` without disposal [FRAMEWORK] | Live connections inherited by a deliberately forked worker (e.g. Celery prefork or Gunicorn `--preload`) without child pool replacement; see [pool fork safety](../references/persistence.md#connection-pools) for context selection and disposal |
| Serialization-failure retry (I8) | Whole-transaction retry after rollback, bounded; not every SQLSTATE is retryable | Per-statement retry after any PostgreSQL error (`25P02` until `ROLLBACK`). `40001`/`40P01` can be retried as a new transaction; `23505`/`23P01` are not automatically transient |
| Idempotent writes (I8) | Retried jobs use idempotency key/dedupe/upsert | Job runners that insert on every attempt; counters incremented by retried consumers |
| Migration safety | Expand-contract, backfill, reversibility, tested | Migration that rewrites/locks a large table in one step; no rollback statement; migration untested at volume |
| Isolation-level awareness | Code's read patterns match the configured isolation | check-then-insert without unique constraint (phantom/dup under concurrency); `READ COMMITTED` assumptions in code that rereads rows |
| Long transactions / lock waits | Transactions stay narrow; no external calls inside | HTTP calls, email sends, or heavy CPU inside an open transaction; lock-wait evidence in DB logs |
| Schema-change compatibility | Running code tolerates the schema during rollout | New NOT NULL column without default while old code still writes; renamed column without a compatibility window ([migration-plan](../templates/migration-plan.md)) |

## Finding format

Per [templates/code-review.md](../templates/code-review.md):
`Severity:` `Evidence:` `Why it matters:` `Recommended change:` `Trade-off:` `Verification:`.

Severity follows reachable consequence, not the MUST/SHOULD label. A demonstrated double write or
lost commit can be High/Critical; a small extra query may be Low. N+1 severity depends on the
expected data size and observed query growth; it can threaten availability at scale.
Performance findings follow [evidence-rules §3](../core/evidence-rules.md): a claimed slow query without
a measured number or query log is an **assumption**, and must be labeled as one.

### Example finding (shape only)

- **Severity:** Medium
- **Evidence:** query log for `GET /orders` shows 1 + N statements: `api/orders.py:18` iterates
  `order.items` and fires one `SELECT` per order (logged run over 50 orders = 51 queries).
- **Why it matters:** latency grows linearly with result size; at list-page sizes this becomes the
  endpoint's dominant cost and can exhaust the pool under concurrency.
- **Recommended change:** add `selectinload(Order.items)` (or a joined read model) to the loading
  strategy for this use case.
- **Trade-off:** `selectin` adds a second query per fetch and can over-fetch when items are not always
  rendered; adjust per use case rather than globally.
- **Verification:** a SQLAlchemy event-counter assertion in the endpoint test locks the count at 2;
  latency measured at a representative page size before/after. In Django, use `assertNumQueries`.

## False positives / legitimate exceptions

- **Deliberately small, bounded relationship fetches** in a loop (a handful of items) are not N+1
  findings; the finding needs evidence of growth with data size.
- **A background refill/maintenance job with its own narrower session scope** is correct (I7 exception)
  when the scope is named.
- **Raw SQL is not a defect.** Query shape, bulk operations, window functions, and DB-specific features
  legitimately favor SQL; the finding is the *problem*, not the tool.
- **ORM use is not a defect either.** Unit-of-work productivity for entity-shaped work is the ORM's job.
- **Lazy loading in small internal tools** with tiny data sets is often acceptable; flag only with
  scale evidence.
- **A pool smaller than max concurrency** is fine when queuing is the intended backpressure — the finding
  is unbounded waiting without a timeout, not the pool size itself.
- **Migration lock-free small tables** don't need heavyweight expand-contract ceremony
  ([principles §7](../core/engineering-principles.md)).

## Output expectations

- Lead with data-integrity and ownership findings, then query-shape findings with SQL evidence (query
  counts, log excerpts, `EXPLAIN` output where available).
- "No significant issue found." is a valid result — state which paths were inspected with SQL logging
  and which were not. Never invent N+1s or "lock risks" without evidence.
- Recommended changes name the mechanism (add `selectinload`, move `commit()` to the use case, retry the
  transaction) and the trade-off (extra joins vs extra round trips; wider transaction vs fewer commits).
- For schema changes, the output points at a [migration-plan.md](../templates/migration-plan.md) entry
  covering rollout and rollback, not just the DDL.
