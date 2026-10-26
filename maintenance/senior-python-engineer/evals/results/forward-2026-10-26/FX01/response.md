# Dashboard fix

`dashboard` now starts all three calls before awaiting results and explicitly owns their lifetimes. A `BillingError` from a non-profile call enables the existing profile-only result and immediately cancels work that is no longer needed. Profile remains required, including when it raises `BillingError` itself. Completed children are checked together so a billing failure cannot hide an unrelated failure.

Every exit cancels remaining work and awaits all children. Each owned cancellation is sent once; shielding the cleanup wait prevents repeated caller cancellation from interrupting a child's asynchronous cleanup. Caller cancellation still propagates after cleanup. An ordinary error raised during fallback cleanup also propagates instead of producing a successful fallback. The public signature, `BillingError`, and successful result shape are preserved; only stdlib is used.

## Verification performed

Ran an inline `unittest.IsolatedAsyncioTestCase` suite on **Python 3.12.14**: **14 tests passed**. Event-controlled checks covered concurrent startup and success; fallback waiting for profile and cleanup; cancellation of unneeded recommendations; profile failures; unexpected failures from each child; simultaneous billing and recommendation failures; cleanup failure; caller cancellation; repeated cancellation; cancellation during fallback cleanup; unexpected child cancellation; exception objects returned as ordinary data; and the existing fallback behavior when recommendations raises `BillingError`.

The checks asserted that owned children had finished and their asynchronous cleanup was not interrupted. Python 3.11 was not separately exercised. No dependencies were installed.

## Skill resources consulted

- `SKILL.md`
- `core/python-invariants.md`: lifecycle and concurrency sections, especially I2 and I6.
- `references/asyncio-concurrency.md`: task lifetime, cancellation, and deadlines.
- `reviews/async-review.md`: targeted heading and keyword search for ownership, cancellation, and early `gather` failure.
