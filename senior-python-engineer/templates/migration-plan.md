# Migration Plan — Data / System Change

Purpose: move schema or system behavior from state A to state B without silent data loss, with
verification and a recovery path suited to each step. For a stack migration, first name the concrete
problem, evidence that the change addresses it, cost, and recovery story
([Evidence Rules](../core/evidence-rules.md) §4).

Use for consequential schema changes, backfills, cutovers, and stack/tool migrations. Scale sections
to risk. Follow the requested [task mode](../SKILL.md#task-modes): a migration plan specifies actions
and acceptance checks; it does not authorize running a backfill, changing production, or deploying.
In implementation work, distinguish commands actually run from proposed steps and pending gates.
Pair with [Implementation Plan](implementation-plan.md) and [Failure Review](failure-review.md) when useful.

## Contents

- [Fill-in structure](#fill-in-structure)
- [Worked example: replacing an order status representation](#worked-example-replacing-an-order-status-representation)

## Fill-in structure

### What changes

State the observable difference and the concrete problem. Name the affected stores, APIs, producers,
and consumers. Separate a representation change from a change in business meaning.

### Authority and compatibility by phase

For each phase, record:

| Phase | Permitted readers | Every permitted writer | Authoritative representation | Entry/exit evidence | Rollback target |
|---|---|---|---|---|---|
| Expand | | | | | |
| Compatible rollout / backfill | | | | | |
| Read cutover | | | | | |
| Contract | | | | | |

Include old service versions, workers, scheduled jobs, admin tools, direct SQL, and replay/backfill jobs.
If some writer cannot update both representations, keep reads on the authoritative representation
until it retires and reconciliation completes, or name a synchronization mechanism whose lag and
failure semantics meet the read contract. Dual-writing in new code does not update old writers.

### Step plan

1. **Expand:** add the new representation compatibly. Check the combinations of code and schema that
   can actually coexist during deployment or rollback. A coordinated maintenance window may use a
   simpler sequence when its interruption cost is acceptable.
2. **Compatible rollout and backfill:** define mapping, write ownership, and the atomicity or conflict
   detection that prevents a backfill from overwriting a newer live update. Backfill in restartable
   batches. Retire incompatible writers before final reconciliation, unless the design supplies a
   suitable synchronization contract. Avoid adding CDC or triggers when retiring writers suffices.
3. **Switch reads:** require evidence that each new read is current under concurrent writes. A non-null
   new value is not proof of freshness. Set the tolerated mismatch/lag threshold and abort condition.
4. **Contract:** remove old code and representation only when no permitted deployment or rollback path
   needs them. Treat destructive removal as a separate step with its own recovery cost.

### Backfill and reconciliation

Specify key range/checkpoint, rate limit, retry behavior, and restart semantics. Count both missing
values and mismatches against the authoritative representation. State how old writes after an early
backfill and new writes during a batch are handled. A count of nulls alone cannot detect stale values.
Verify domain invariants and mapping coverage as well as row counts.

### Verification per step

Choose checks for the actual migration: mixed-version behavior; old write after a populated new value;
new write racing backfill; interruption/restart; reconciliation; read cutover; rollback and redeploy.
Use the actual database's concurrency semantics where they matter. Record commands, environment, and
observed results for completed checks; label proposed or unavailable checks explicitly.

### Rollback and cutover

For each phase, identify code revert, read-flag change, reconciliation, forward fix, or data restore.
A flag flip is safe only when the target representation still carries the required information and
all readers/writers tolerate the resulting mixed state. State which changes close the rollback window.
Name cutover owner, abort signals, and any communication required by the project. Rehearse recovery
where consequences warrant it; report measured recovery time rather than inventing RTO/RPO numbers.

### Cleanup

Give each temporary writer, reader, column, flag, and compatibility path a removal condition and owner.
Remove only after supported consumers and rollback targets have retired; an elapsed date alone is not
proof that a compatibility path is unused.

## Worked example: replacing an order status representation

**Illustrative assumptions:** replace free-text `orders.status` with constrained `status_v2` in one
transactional database. `normalize(status)` is a validated mapping for all accepted old values. Keep
new values representable in the old format throughout the rollback window. All writers are known and
can be upgraded or stopped. If these assumptions do not hold, revise the sequence before execution.

| Phase | Readers | Writers | Authority and gate |
|---|---|---|---|
| A: expand | Read `status` | Old writers update `status` | `status` remains authoritative; `status_v2` may be absent or stale. |
| B: compatible rollout | Both versions read `status` | Old writers update `status`; new writers update both atomically | Read only `status`. Early backfill is optional and cannot establish cutover readiness. |
| C: reconcile | Continue reading `status` | Only compatible dual writers remain | Prove old services, workers, scheduled jobs, admin tools, and replay paths retired; then reconcile every mismatching row. |
| D: read cutover | New readers use `status_v2`; old-compatible readers may still use `status` | Continue atomic dual writes | Cut over after reconciliation and concurrency checks; preserve old-format compatibility for rollback. |
| E: contract | Read `status_v2` | Writers use `status_v2` only | Close the old-version rollback window explicitly before stopping old writes or dropping `status`. |

### Backfill rule

A dual writer updates `status` and `status_v2 = normalize(status)` in one transaction from the same
new business value. During phase C, each backfill update derives `status_v2` from the row's current
`status` under the database's verified row-update/locking semantics. Alternatively, use a row-version
compare-and-update and retry conflicts. Do not compute from an earlier unlocked snapshot and overwrite
a newer value. Batch by stable primary-key ranges, checkpoint committed batches, and let reruns converge.

Reconcile **all mismatches**, including non-null `status_v2` values, after the last old-only writer has
retired. Verify both `status_v2 IS NULL` count and `status_v2 != normalize(status)` count are zero under
the supported value mapping; separately account for unmapped old values. Run concurrent-writer checks
and inspect errors/constraint violations before phase D.

### Counterexample the sequence must prevent

An early backfill sets `(status='pending', status_v2='PENDING')`. An old writer later changes only
`status` to `'paid'`. The non-null `status_v2` remains `'PENDING'`; null fallback would return the wrong
state. Phase B therefore keeps reads on `status`. Phase C retires that writer and repairs the populated
mismatch before any reader relies on `status_v2`.

### Rollback and redeploy

- Through phase C, keep reading `status`; reverting to an old-only writer invalidates any previous
  reconciliation certificate. Repeat writer retirement and reconciliation before a later cutover.
- During phase D, prefer reverting to the compatible dual-write release. To reintroduce an old-only
  writer, first move **all** readers back to `status` and verify that transition. Preserve atomic dual
  writes until the reader transition completes, then treat `status_v2` as potentially stale again.
- After phase E stops maintaining `status`, an old binary cannot safely resume merely by flipping a
  flag. Reconstruct and validate the old representation if lossless recovery is possible, or use the
  defined forward-fix/restore plan. Dropping data may make rollback lossy; test the actual recovery path.

**Acceptance:** exercise an old write after early backfill, a new write during reconciliation, a
restarted batch, mixed readers at cutover, and rollback/redeploy. The authoritative representation
must preserve the declared business state at each permitted phase.
