# A status-column migration
Repair the three helpers in solution.py for an in-memory model of a rolling migration. Old binaries
write only row['status']. While any old writer can run, phase='mixed' reads MUST use status even if a
backfill already populated status_v2. New writers update both columns during the compatibility
period, retaining rollback compatibility. `finalize(row, old_writers_active=...)` is an operator-
controlled final reconciliation: reject while old writers remain; after retirement copy the current
status into status_v2. In phase='new_only', read status_v2 and raise ValueError if missing/None (the
final reconciliation has not completed). Reject unknown phases. Calls are sequential; transaction,
locking and fleet retirement checks belong to the real deployment, not this dictionary fixture.
Keep signatures. Explain the stale-writer case and rollback boundary in response.md.
