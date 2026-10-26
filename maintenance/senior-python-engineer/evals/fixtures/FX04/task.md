# Retried checkout acceptance
Repair `checkout(order_id, cents, store, provider)` for sequential delivery/retry of the SAME order.
The store has get(order_id)->dict|None and save(order_id, record); completed saves survive process
restart. Records must contain key, cents, status ('pending' or 'paid'), and receipt (None until paid).
The provider has charge(key, cents)->receipt: the same key and cents returns the same accepted receipt
without another charge for this fixture's entire retry period; key reuse with a different amount is
an error. TimeoutError may occur AFTER acceptance. Persist a pending intent BEFORE calling the
provider. On timeout return the pending record. A later call may retry with the same identity.
Persist and return paid on acknowledgement. Reject a changed amount for an existing order without
calling the provider. A store failure may crash the attempt; redelivery must recover without a
second accepted charge. Return a paid stored order without charging again. Inputs are trusted
positive cents/nonempty order IDs. Concurrent orders/workers and expiry of retention are out of
scope, and no exactly-once final payment-delivery claim is requested. Keep the API. Explain in
response.md which boundary is not made atomic by a local DB transaction.
