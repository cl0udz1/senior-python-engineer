def read_status(row,phase):return row.get('status_v2') or row['status']
def new_write(row,value):row['status_v2']=value
def finalize(row,*,old_writers_active):row.setdefault('status_v2',row['status'])
