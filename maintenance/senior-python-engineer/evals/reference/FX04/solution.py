def checkout(order_id,cents,store,provider):
    record=store.get(order_id)
    if record is None:
        record={'key':'order:'+order_id,'cents':cents,'status':'pending','receipt':None}
        store.save(order_id,record)
    if record['cents']!=cents:raise ValueError('amount differs from stored intent')
    if record['status']=='paid':return record
    try:receipt=provider.charge(record['key'],cents)
    except TimeoutError:return record
    record={**record,'status':'paid','receipt':receipt};store.save(order_id,record)
    return record
