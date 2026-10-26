# Database Traps

Transactions, sessions, retries, and migrations. Invariants in play: **I7** (transaction/session scope
visible; Session-per-thread / AsyncSession-per-task), **I8** (retries need idempotency analysis),
**I2** (resource lifetimes), **I14** (failure questions at boundaries). Routing:
[reviews/database-review.md](../../../senior-python-engineer/reviews/database-review.md),
[references/persistence.md](../../../senior-python-engineer/references/persistence.md). Grading per
[expected-behavior.md](expected-behavior.md).

---

### Case D1 — Non-idempotent retry after timeout

**Input**
> "Our payment job occasionally times out talking to the payment gateway. We added retries to make it
> more reliable:
>
> ```python
> def process_payment(order):
>     for attempt in range(3):
>         try:
>             gateway.charge(order.customer, order.total_cents)
>             order.status = "paid"
>             db.commit()
>             return
>         except TimeoutError:
>             time.sleep(2 ** attempt)
>     order.status = "failed"
>     db.commit()
> ```
>
> Finance says a few customers were charged twice last week. Investigate and fix."

**Context**
`gateway.charge` moves real money. Its timeout can fire **after** the gateway committed the charge
(network died after the request landed). The gateway supports idempotency keys; the code does not send
one. The job runs from a queue that itself re-delivers messages.

**Desired reasoning behavior**
Answer the I8 question first — "can this operation safely happen twice?" — and the answer is the
finding: a timeout is an *unknown outcome*, not a failure; retrying an unknown-outcome money movement
without an idempotency guarantee is exactly how customers get double-charged. Then design the fix at
the right layer: send a per-order idempotency key (derived from the order id, stable across attempts)
so the gateway can dedupe; record attempt state before calling (intent), reconcile unknown outcomes
against the gateway instead of blind replay; treat the queue re-delivery path with the same analysis
(the double-charge may be from job redelivery, not just the retry loop — failure questions at
boundaries, I14: "runs twice?"). Explicitly name what must never be blindly retried: charges, sends,
anything with an external side effect and no idempotency mechanism. Reads and key-guarded calls are
the retryable class. (Mechanics: [core/python-invariants.md](../../../senior-python-engineer/core/python-invariants.md) I8;
PostgreSQL serialization retries retry the whole *transaction*, a separate rule not applicable here.)

**Acceptable outcomes**
1. Diagnosis (timeout = unknown outcome; retry without idempotency = double charge; queue redelivery is the same bug) + fix (idempotency key per order sent to gateway, intent/attempt record, reconciliation for unknown outcomes, bounded retries only for classified transient failures) + "never blindly retry X" list.
2. Same, plus verification design: a test harness with a fake gateway that commits-then-times-out, asserting exactly one charge per order key across retry + redelivery.
3. Same, plus distinguishing the DB side: `order.status = "paid"` and the gateway charge need a stated consistency story (status set only on confirmed charge; unknown → explicit `payment_pending`/reconcile state).

**Failure modes**
- "Increase timeout / add more retries / add jitter" — treating symptoms (makes double charges *more* likely).
- Wrapping the whole loop in a DB transaction and committing once (the money movement happens outside your DB; your transaction can't undo it).
- A distributed saga/event-sourcing platform proposal for one charge call (disproportionate).
- Concluding "the gateway is flaky, switch providers" without evidence.

**Critical mistakes**
- Keeping auto-retry on the charge with no idempotency analysis and presenting it as safe (I8 MUST violation presented as fine).
- Claiming the DB transaction prevents double charging (invented mechanism; fabricated assurance).

---

### Case D2 — N+1 hidden in an innocuous loop

**Input**
> "The admin page for orders got slow as we grew — 10s+ page loads at ~2k orders. The code looks
> simple to me:
>
> ```python
> def order_rows(tenant_id):
>     orders = repo.list_orders(tenant_id)          # one query
>     rows = []
>     for o in orders:
>         rows.append({
>             "id": o.id,
>             "customer": o.customer.name,          # relationship access
>             "items": len(o.items),
>             "region": o.customer.address.region,
>         })
>     return rows
> ```
>
> Should we add caching?"

**Context**
ORM with lazy-loading relationships (SQLAlchemy-style). Each relationship attribute access emits a
query per order. `list_orders` is one query; the loop emits ~2–3 more per row. Data changes with each
admin action, so caching has real staleness cost.

**Desired reasoning behavior**
Diagnose the actual mechanism before any fix: lazy loading turns innocent attribute access into
per-row queries (N+1, arguably N+2k here); 2k orders × 3 queries ≈ 6k round trips — the 10s is
round-trip count, not "Python being slow". Evidence habit: count queries (engine event logging /
`echo` / EXPLAIN) rather than guessing. Fix at the data-access layer: eager/select-in loading of the
two relationships, or one joined/aggregated query (the `len(items)` case can be a GROUP BY count),
then re-measure. Caching is the wrong lever here: it papers over a fixable query pattern and introduces
invalidation semantics the app doesn't need (the "add a cache" evidence bar from
[core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §3 is not met — no measured repeated expensive
*computation*, just repeated queries).

**Acceptable outcomes**
1. Identifies lazy-loading N+1 with the query-count estimate, prescribes select-in/eager loading or a single aggregated query, says re-measure, and declines caching with the reason (staleness cost + wrong lever).
2. Same, plus naming where to verify (SQL logging in a test, query counter assertion so the regression is caught).
3. Same, plus the scope note: fix the relationship access pattern in this path only; a bulk export endpoint may want a different query shape (proportionality).

**Failure modes**
- "Add Redis caching for orders" first (caching without invalidation semantics — [core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §3 cache bar; masks the bug).
- "ORMs are slow, rewrite with raw SQL" (banned slogan; the ORM has an eager-loading answer).
- Proposing async or more workers to "handle the load" (wrong bottleneck class).
- Blindly annotating `selectinload` everywhere without measuring which relationships this path touches.

**Critical mistakes**
- Claiming caching makes the page correct/consistent while stale rows would be shown post-update — asserting consistency over a stale-read regression is fabricated assurance ([expected-behavior.md](expected-behavior.md) §3.1).

---

### Case D3 — External API call inside a long transaction

**Input**
> "Occasionally the whole app grinds to a halt and the DB shows dozens of idle-in-transaction sessions.
> Reproduces under load. The suspect area:
>
> ```python
> def fulfill_order(order_id):
>     order = session.get(Order, order_id)
>     order.status = "fulfilling"
>     session.flush()
>     label = shipping_api.create_label(order.address)   # external HTTP, p95 ~3s, can hang 30s+
>     order.label = label.id
>     order.status = "shipped"
>     session.commit()
> ```
>
> This runs in 20 worker threads, each with its own session."

**Context**
The DB is PostgreSQL. Connection pool ≈ 20. `shipping_api.create_label` is an external service with
p95 3s and tail hangs of 30s+. Work is triggered by a queue; at-least-once delivery.

**Desired reasoning behavior**
Find the two coupled problems. (1) Transaction scope: the unit of work holds a DB transaction open
across a slow external HTTP call — under load, hung calls hold connections/row locks "idle in
transaction" until the pool is exhausted ([I7](../../../senior-python-engineer/core/python-invariants.md): the commit boundary should be visible; the external call
does not belong inside it). (2) Failure semantics: if `create_label` fails after `flush`, what commits?
If the process dies after the label is created but before commit, the queue redelivers — another label
is created (I8: external side effect + at-least-once delivery = need a provider-honored idempotency key
or reconciliation of an unknown outcome before retry). Fix shape: make the transaction tight (commit
status transition, release; call API; new transaction to record result), or the durable-step pattern
(persist `label_requested` intent, call, persist result) with reconciliation. A local intent records
state but cannot by itself deduplicate an effect at the provider. Add a timeout to the HTTP call;
answer "what if we crash between the two steps?" explicitly. Note the pool-sizing observation follows
from measurement, not formula.

**Acceptable outcomes**
1. Names both defects (open transaction across external call → pool/lock exhaustion; at-least-once delivery → duplicate label side effect) and proposes tight transaction boundaries + intent/step recording + provider-honored idempotency or reconciliation before retry + HTTP timeout.
2. Same, with the crash matrix walked through: crash before API call / after API call before commit / after commit — and the recovery behavior defined for each.
3. Same, plus the queue-level note: `fulfill_order` must be safe to run twice through provider-honored dedupe or reconciliation of unknown outcomes, since delivery is at-least-once.

**Failure modes**
- "Raise the pool size / add more workers" (capacity patch; locks and duplicate labels remain).
- Moving the API call into a new thread so "the transaction isn't blocked" (still open; worse ownership).
- Adding a distributed transaction manager (disproportionate).

**Critical mistakes**
- Claiming the ORM commits or releases the transaction while the shown slow HTTP call is pending, despite the observed idle-in-transaction pool exhaustion (invented framework behavior).
- Claiming `session.flush()` commits (invented SQLAlchemy semantics — flush is not commit).

---

### Case D4 — Shared session across background tasks

**Input**
> "Our worker crashes sporadically with `InterfaceError: connection already closed` and sometimes
> persists data attributed to the wrong order. Architecture sketch:
>
> ```python
> session = Session(engine)   # one session created at worker startup
>
> def handle_order(order):
>     save_snapshot(session, order)                  # touches shared session
>     asyncio.create_task(notify_async(order))       # also writes via the same session
>     update_status(session, order)                  # same session, main flow
>     session.commit()
> ```
>
> (Mixed sync/async code; multiple orders handled concurrently.)

**Context**
One SQLAlchemy `Session` shared by the main flow, concurrent order handling, and background async
tasks. Wrong-attribution writes match identity-map/interleaving behavior. The worker processes orders
concurrently "for throughput".

**Desired reasoning behavior**
Identify the ownership violation by name: a Session is a unit-of-work/identity-map object —
session-per-thread, AsyncSession-per-task, **never shared across concurrent threads/tasks** ([I7](../../../senior-python-engineer/core/python-invariants.md),
[FRAMEWORK] rule from SQLAlchemy's documented model). The symptoms map to the mechanism: interleaved
use stomps transaction state (wrong attribution), and tasks outliving the commit close the connection
under them (`connection already closed`). Also catch the async trap shape: `create_task` with dropped
reference and a session write inside (I6/I4); commit boundaries now span other tasks' writes — one
task's failure rolls back another's data. Fix: per-task/per-unit-of-work sessions scoped to one order's
handling (context manager, I2), background work gets its own session, commit scope = one order's use
case; bounds on concurrent handling (worker pool). Wrong-attribution may also require a data audit —
naming that is a plus.

**Acceptable outcomes**
1. Diagnosis (shared Session across concurrent flows violates the session ownership model; commit scope spans unrelated writes) + fix (session per use case/order; own session for the background task; context-managed lifetime) + note that wrongly-attributed rows need reconciliation.
2. Same, plus restructuring the background notification to carry its own data/keys and open its own unit of work (no shared identity map), with bounded task ownership (I6).
3. Same, plus the sync/async layering note: pick an execution model per worker (sync workers or fully async with AsyncSession-per-task), the mixed sharing is itself the smell (I4).

**Failure modes**
- Adding `threading.Lock` around the session (serializes; keeps wrong commit scope).
- "Upgrading SQLAlchemy" or switching to raw psycopg to dodge it (evidence-free migration).
- Declaring it "a concurrency bug in asyncio" (invented diagnosis).

**Critical mistakes**
- Keeping the shared session with a claim that sessions can be shared with care (I7 MUST violation presented as fine; SQLAlchemy explicitly forbids concurrent sharing).
- Claiming flush/commit ordering guarantees that make cross-task writes safe (invented semantics).

---

### Case D5 — Destructive migration without expand-contract

**Input**
> "Ship this migration, the refactor is done:"
>
> ```sql
> ALTER TABLE customers DROP COLUMN full_name;
> ALTER TABLE customers ADD COLUMN name TEXT NOT NULL;
> UPDATE customers SET name = 'unknown';
> ```
>
> "We renamed `full_name` → `name` and the new code uses `name`."

**Context**
The service runs N instances during deploys; old and new code overlap for several minutes. Zero
downtime is a stated requirement. `full_name` holds real data. A committed drop would destroy the only
copy of it; PostgreSQL DDL in an uncommitted transaction can still be rolled back. Old code reads
`full_name` on every read path until fully rolled out. Rollback after deployment must remain possible.

**Desired reasoning behavior**
Recognize the deploy-overlap and data-loss hazards (I14 failure questions: schema change, partial
deploy, rollback). The destructive facts: *if committed*, `DROP COLUMN` loses the only copy of the
names (and `name` would get `'unknown'` — silent data corruption of real values); the shown
`ADD COLUMN ... NOT NULL` fails on a populated PostgreSQL table before the backfill. In a transactional
migration this failure rolls back the earlier drop; if DDL steps commit separately, the drop can
persist. Even a reordered migration would break old code during the deployment overlap. Prescribe
expand-contract: (1) add `name` nullable, (2) dual-write or backfill from `full_name`, (3) verify
counts/values, (4) switch reads, (5) drop `full_name` only in a later release after rollback window
closes. Rollback story and verification queries named ([templates/migration-plan.md](../../../senior-python-engineer/templates/migration-plan.md)).
Also: migrations are reviewed at this team's risk level — flag that "the refactor is done" pressure
doesn't change the expand-contract necessity where zero-downtime is required.

**Acceptable outcomes**
1. Rejects the migration as written (data destruction + deploy-window breakage), provides the expand-contract sequence with dual-write/backfill/verify/switch/drop, names the rollback point at each stage.
2. Same, plus the concrete verification (row-count and value-equality check between columns before drop; alert on old-code insert failures during the window).
3. Same, plus noting the NOT NULL ordering trap (backfill first, add constraint later; or add with default only if the default is semantically correct — `'unknown'` is not).

**Failure modes**
- "Add `DEFAULT ''` and run it" — approving a variant that still loses the original values.
- Suggesting a maintenance window instead (may be acceptable if *stated* requirements change, but the case says zero-downtime is required — dropping the requirement silently is a miss).
- Focusing on naming conventions or Alembic file organization while the destructive DDL goes unchallenged.

**Critical mistakes**
- Presenting the destructive drop as safe because "the code no longer uses the column" — a fabricated safety claim about an irreversible data-destroying change ([expected-behavior.md](expected-behavior.md) §3.1; it also silently drops the stated zero-downtime/rollback requirement).
- Claiming a *committed* drop can recover the original values without a backup or retained source (invented data-recovery guarantee); denying that PostgreSQL can roll back uncommitted DDL is also a factual error.

---

### Case D6 — Statement-level retry inside an aborted PostgreSQL transaction

**Input**
> "We're experiencing intermittent serialization failures (`40001: could not serialize access due to concurrent update`) in PostgreSQL during a high-concurrency ticket reservation checkout. To handle this, a junior dev added a retry loop around the specific update statement:
>
> ```python
> def reserve_seats(session: Session, user_id: str, event_id: str, seat_ids: list[str]):
>     # Step 1: Record reservation intent
>     reservation = Reservation(user_id=user_id, event_id=event_id, status="PENDING")
>     session.add(reservation)
>     session.flush()
>     
>     # Step 2: Update seat status with retry
>     for attempt in range(3):
>         try:
>             session.execute(
>                 update(Seat)
>                 .where(Seat.id.in_(seat_ids), Seat.status == "AVAILABLE")
>                 .values(status="RESERVED", reservation_id=reservation.id)
>             )
>             break
>         except DBAPIError as e:
>             if "40001" in str(e) and attempt < 2:
>                 time.sleep(0.05 * (2 ** attempt))
>                 continue
>             raise
>             
>     # Step 3: Commit reservation
>     session.commit()
> ```
>
> When the retry triggers in production, the second attempt crashes with:
> `sqlalchemy.exc.InternalError: (psycopg2.errors.InFailedSqlTransaction) current transaction is aborted, commands ignored until end of transaction block [SQLSTATE 25P02]`.
>
> Why does the statement retry fail, and how should this be fixed?"

**Context**
The database is PostgreSQL running under `REPEATABLE READ` or `SERIALIZABLE` isolation. In PostgreSQL, when an error occurs during an open transaction (such as a serialization conflict `40001` or deadlock `40P01`), PostgreSQL aborts the entire transaction block. Any subsequent command sent on that connection without an intervening `ROLLBACK` will fail immediately with `SQLSTATE 25P02: InFailedSqlTransaction`.

**Desired reasoning behavior**
Explain the fundamental database protocol mechanism (I8 and [references/persistence.md](../../../senior-python-engineer/references/persistence.md)):
1. PostgreSQL transaction state machine: When a statement fails with serialization failure (`40001`), PostgreSQL immediately transitions the backend transaction state to `ABORTED` (state `25P02: InFailedSqlTransaction`). It refuses to execute any further SQL statements in that transaction block until the client issues a `ROLLBACK`.
2. Statement-level retry is a flaw: Retrying `session.execute(...)` inside the same transaction block is guaranteed to fail with `25P02`.
3. Whole-transaction retry required: The retry boundary must encompass the *entire unit of work*. The failed transaction must be rolled back (`session.rollback()`), and all steps (creating the `Reservation`, flushing, updating `Seat`, and committing) must be re-executed from the beginning within a fresh transaction under a consistent new snapshot.
4. Idempotency analysis (I8): Verify that retrying the entire function is safe and does not create duplicate external side effects.

**Acceptable outcomes**
1. Explains the PostgreSQL `25P02 InFailedSqlTransaction` mechanism: any statement error aborts the transaction, requiring a full rollback before any new queries can run.
2. Identifies that statement-level retries are fundamentally invalid for PostgreSQL transaction conflicts; places the retry loop around the entire `reserve_seats` unit of work, with `session.rollback()` on error and a fresh transaction per attempt.
3. Notes backoff and jitter for serialization retries to reduce thundering-herd contention on contested seats.

**Failure modes**
- Suggesting clearing the error without issuing a rollback or savepoint.
- Suggesting switching isolation level to `READ UNCOMMITTED` (which PostgreSQL doesn't even have, mapping it to Read Committed) without addressing concurrency overselling.
- Believing the error is a SQLAlchemy bug rather than a core PostgreSQL transaction semantic.

**Critical mistakes**
- Claiming that statements can be retried inside an active PostgreSQL transaction after an error without rolling back (invented transaction mechanics).

