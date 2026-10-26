def read_status(row,phase):
    if phase=='mixed':return row['status']
    if phase!='new_only':raise ValueError('unknown phase')
    value=row.get('status_v2')
    if value is None:raise ValueError('final reconciliation incomplete')
    return value
def new_write(row,value):row.update(status=value,status_v2=value)
def finalize(row,*,old_writers_active):
    if old_writers_active:raise ValueError('old writers still active')
    row['status_v2']=row['status']
