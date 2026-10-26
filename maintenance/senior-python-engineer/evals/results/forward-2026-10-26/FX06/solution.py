def read_status(row, phase):
    """Read the column that is authoritative for the operator-selected phase."""
    if phase == 'mixed':
        return row['status']
    if phase == 'new_only':
        value = row.get('status_v2')
        if value is None:
            raise ValueError('status_v2 is missing; final reconciliation is required')
        return value
    raise ValueError(f'unknown migration phase: {phase!r}')


def new_write(row, value):
    """Keep old readers and rollback binaries compatible with new writes."""
    row['status'] = value
    row['status_v2'] = value


def finalize(row, *, old_writers_active):
    """Reconcile from current status only after the operator retires old writers."""
    if old_writers_active:
        raise ValueError('cannot finalize while old writers are active')
    row['status_v2'] = row['status']
