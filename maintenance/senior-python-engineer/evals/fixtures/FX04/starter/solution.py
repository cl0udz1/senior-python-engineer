import uuid
def checkout(order_id,cents,store,provider):
    key=str(uuid.uuid4())
    receipt=provider.charge(key,cents)
    record={'key':key,'cents':cents,'status':'paid','receipt':receipt}
    store.save(order_id,record)
    return record
