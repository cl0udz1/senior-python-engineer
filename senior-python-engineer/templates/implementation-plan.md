# Implementation Plan — Scoped Change

Purpose: order a scoped change so each step is verifiable and the failure behavior of the change is
explicit before code is written. Use for a requested implementation plan (DESIGN), or as a short
working plan during IMPLEMENT with refactoring/modernization concerns. Follow [task modes](../SKILL.md#task-modes):
a plan-only request finishes with proposed steps and checks; an implementation request continues to
the authorized changes and actual verification.

When to use: when the change touches more than one module, changes data or failure behavior, or needs
sign-off. **Anti-ceremony note:** a small change can be 10 lines in this shape — Goal, one current-behavior
sentence, 2 steps, test line, done. If the plan outweighs the diff, cut the plan. A one-file fix with a
test needs no plan at all; just do it.

Judgment inputs: [Decision Model](../core/decision-model.md), [Failure Modes](../catalogs/failure-modes.md),
[Invariants](../core/python-invariants.md).

---

## Fill-in structure

# <change title>

## Goal & non-goals
**Goal:** *one sentence — the observable outcome.*
**Non-goals:** *what this deliberately does NOT do. Non-goals are what stop scope creep; name at least
the tempting adjacent thing.*

## Current behavior (evidence)
*What the code does today, with pointers: file:line, existing tests, a measured number, a failing
reproduction. Evidence outranks memory — run the test/observation and cite it
([Evidence Rules](../core/evidence-rules.md) §1). If current behavior is unknown, finding out is step 0.*

## Proposed change
*Ordered steps; each step independently verifiable (compiles, test passes, behavior observable). Prefer
smallest reversible steps first. Mark which step is the no-return point, if any.*

1. <step — what changes, how to verify it>
2. …

## Data & migration impact
*Schema changes? Backfills? If data is touched, use [Migration Plan](migration-plan.md) — expand-contract,
idempotent backfill (I8). If no data impact: "None." is a complete answer.*

## Failure behavior changes
*How do failures look different after the change? New retries/idempotency needs (I8)? Changed timeout
or cancellation semantics (I6)? What happens on partial success — before vs after? If unchanged: "None."
and say what you checked.*

## Test plan
*What runs to prove it: exact commands, which suites, what new test covers the new behavior. Tests scale
with risk ([Testing](../references/testing.md)) — a risky change with no test plan is not a plan.*

## Rollback
*How to undo: revert commit? feature flag? data restore? For each step past the no-return point, the
rollback path and its cost. "Revert the commit" is a real answer when it is true — and it must be true
for data too, or the data step needs [Migration Plan](migration-plan.md) rollback.*

## Risk & mitigations
*What could go wrong (top 2–4), likelihood/impact in one word each, and the mitigation or detection
(monitoring/alert that would catch it). Missing risk = missing thought.*

## Open questions
*Unresolved facts that change the plan, with the cheapest way to close each. If there are none: "None."
— do not invent questions to look thorough.*

---

## Filled fragment (adding retry-with-idempotency to a webhook sender)

*Illustrative example only: replace its names, values, and reported outcomes with project evidence.*

```markdown
## Goal & non-goals
Goal: outbound webhook delivery survives transient 5xx/timeouts without duplicate receiver effects.
Non-goals: no queue broker yet; no inbound webhook changes.

## Current behavior (evidence)
`webhooks/sender.py:44` calls `httpx.post(...)` once; on exception the event is lost (reproduced by
test_run.py::test_sender_drops_on_timeout, which asserts current drop behavior). The receiver's
published contract says it deduplicates repeated `Idempotency-Key` values for this endpoint.

## Proposed change
1. Add `Idempotency-Key` header from `event.id`; verify the receiver honors it and test a repeated
   delivery against a deduplicating fake receiver. A sent header alone is not an idempotency guarantee.
2. Wrap the call in bounded retry: `httpx.TransportError` + 5xx only, 3 attempts, exp backoff+jitter,
   total deadline 30s. Verify: unit test with failing-then-succeeding transport.
3. On final failure, record the event as unresolved for reconciliation/replay with the same key.
   Verify: test asserts the durable row and replay behavior.

## Failure behavior changes
Retries added only for idempotent-with-key sends (I8). Non-retried: 4xx and validation errors.

## Rollback
Steps 1–2 revert by commit; step 3 writes a table — additive-only, revert keeps table (contract step
lazily, see migration-plan if we drop it).
```
