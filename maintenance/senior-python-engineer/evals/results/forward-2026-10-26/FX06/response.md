# Status-column migration repair

Implemented the three helpers in `solution.py` without changing their signatures.
The task's sequential dictionary model needs an explicit source of truth for each
phase; additional locks, transaction wrappers, or fleet tracking would not solve
the stale-column problem within this fixture.

## Behavior

| Operation | Result |
| --- | --- |
| `read_status(row, 'mixed')` | Always reads `row['status']`, regardless of whether `status_v2` exists or has a value. |
| `read_status(row, 'new_only')` | Reads only `status_v2`; raises `ValueError` when it is absent or `None`. Other falsy values are returned unchanged. |
| `read_status(row, unknown_phase)` | Raises `ValueError`. |
| `new_write(row, value)` | Updates both `status` and `status_v2`, retaining the old column for old binaries and rollback. |
| `finalize(row, old_writers_active=True)` | Raises `ValueError` before modifying the row. |
| `finalize(row, old_writers_active=False)` | Unconditionally copies the current `status` into `status_v2`, replacing any stale backfill value. |

The two mutating helpers retain their implicit `None` return value. Finalization
preserves the old column and unrelated row data. Repeating it without intervening
writes leaves the same result.

## Why the stale-writer case matters

Consider this sequential history:

1. The row starts with `status='pending'`.
2. A backfill copies `'pending'` to `status_v2`.
3. An old binary writes `status='complete'` without updating `status_v2`.

The populated new column now contains stale data. A mixed-phase read must return
`'complete'` from `status`; preferring a non-null `status_v2` would incorrectly
return `'pending'`. Once old writers are retired, finalization must overwrite the
backfilled value with `'complete'`. The former `setdefault` implementation would
leave the stale value untouched.

The operator must retire old writers, reconcile every affected row, and only then
select `phase='new_only'`. A missing or `None` new value is rejected explicitly,
but a populated new value cannot prove that final reconciliation happened: it may
have come from an earlier backfill. The caller owns this phase ordering and the
truth of `old_writers_active`.

## Rollback boundary

Dual writes keep `status` current, so old binaries can still read new writes.
Neither finalization nor switching reads to `new_only` removes that compatibility
by itself. Before allowing old writers to run again, return readers to `mixed`;
otherwise an old write can make new-only readers stale. A subsequent cutover must
again retire old writers and perform final reconciliation.

The direct rollback boundary is the later contraction step: dropping `status` or
stopping writes to it. After that step, restoring old binaries can require
restoring the old column and reconciling it from the authoritative current data.
This fixture performs neither contraction step. Real deployment code must own
transactions, coordinated cutover, and writer-retirement checks; these helpers
model only the specified sequential row operations.

## Verification actually performed

Ran `python -B -` from this project with an inline standard-library `unittest`
program loading `solution.py` through `runpy.run_path`.
Result: **8 tests passed; exit status 0**. The checks covered:

- Mixed reads with absent, null, and stale new-column data, without mutating rows.
- Dual writes, preservation of unrelated data, and rollback reads through `status`.
- Rejected finalization without mutation while old writers remain active.
- Backfill followed by an old write, final reconciliation, and a later new write.
- Finalization with absent, null, or stale `status_v2`, including repetition.
- New-only rejection of missing and `None` values without fallback or mutation.
- Preservation of non-None falsy values and new-only reads without `status`.
- Rejection of unknown phases.

A separate focused review found no contract issue and independently exercised the
critical migration sequences using standard-library checks. No database,
concurrency, or fleet deployment tests were performed; those systems are outside
the supplied model. No dependencies were installed.

## Skill resources used

Read the supplied `senior-python-engineer/SKILL.md` and relevant sections of:

- `playbooks/existing-codebase.md`: constraints, scope, testing, and migration lifecycle.
- `references/persistence.md`: migrations and expand/contract ordering.
- `core/python-invariants.md`: state ownership (I4), transaction boundaries (I7), and visible failure behavior (I13-I14).
- `core/evidence-rules.md`: claim classification and verification of generated work.
