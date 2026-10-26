# Code Review

## Contents

- [Scope & trigger](#scope--trigger)
- [Review contract](#review-contract)
- [Procedure](#procedure)
- [Checklist](#checklist)
- [Finding format](#finding-format)
- [False positives / legitimate exceptions](#false-positives--legitimate-exceptions)
- [Output expectations](#output-expectations)

The default review: does this diff do what it claims, safely, on all paths? Every other file in
[reviews/](architecture-review.md) is a specialization of this one. When scope is ambiguous, start here
and route out on a clear match.

## Scope & trigger

Use for: PRs and diffs; generated code before it is called done ([principles §5](../core/engineering-principles.md));
"review this change" requests; refactors where behavior must be preserved ([REFACTOR] tasks). Route to a
specialist review when the scope is clearly: system design → [architecture-review.md](architecture-review.md);
threads/shared state → [concurrency-review.md](concurrency-review.md); asyncio internals →
[async-review.md](async-review.md); queries/transactions → [database-review.md](database-review.md);
trust boundaries → [security-review.md](security-review.md); speed claims →
[performance-review.md](performance-review.md); test suites → [testing-review.md](testing-review.md);
new dependencies → [dependency-review.md](dependency-review.md); release gate →
[production-readiness.md](production-readiness.md). Routing out does not excuse this review from its
correctness pass over the diff itself.

## Review contract

Use this contract for every specialist review. Follow the requested [task mode](../SKILL.md#task-modes):
a review does not authorize applying the proposed fixes. State the inspected surface and material limits.
Give each finding concrete evidence, plausible impact, an actionable change, its trade-off, and a
verification path ([finding template](../templates/code-review.md)). A clean review is a valid result.
Grade severity by reachability and consequence, not the strength of an invariant or a catalog label.

### Priority order

1. correctness · 2. security · 3. data integrity · 4. concurrency/state ownership · 5. resource lifecycle ·
6. failure behavior · 7. performance · 8. maintainability · 9. readability/style.

Lead with consequential findings. Omit style commentary when it would distract from them; a minor
readability note may follow only when it helps the author and stays proportionate.

## Procedure

1. **Understand intent.** Read the PR description, commit message, and the issue behind them. If intent
   is genuinely ambiguous and the diff does not resolve it, ask one precise question; otherwise state
   the working assumption and review against it.
2. **Map the changed surface.** Files touched, callers affected, public API changes, config/schema
   changes, dependency changes. Review the blast radius, not just the changed lines.
3. **Correctness first.** Does every path do what intent says? Edge values, empty inputs, ordering,
   off-by-one, error paths. Work the correctness rows of the checklist below.
4. **Data, concurrency, resources.** Mutable state touched by the diff (I4), resource lifetimes (I2),
   transaction/session scope (I7), cancellation (I6). If this dominates the diff, route to the matching
   specialist review.
5. **Failure behavior.** What happens when each new dependency call, I/O, or parse fails (I13, I14)?
   Does anything retry, and is the retry safe (I8)?
6. **Tests.** Does the change carry tests proportional to its risk ([references/testing.md](../references/testing.md))?
   Do they assert behavior rather than implementation? Were they actually run (command + result)?
7. **Generated-code scrutiny.** A green run is not a design review: leaked steps and a type that
   cannot stand in for its base still count ([architecture.md](../references/architecture.md)). If the
   diff is agent-generated and touches authentication,
   authorization, secrets, subprocesses, shell, serialization/deserialization, SQL, filesystem, network,
   privilege, or concurrency structures, re-review those lines at [security-review.md](security-review.md)
   depth before approving ([principles §5](../core/engineering-principles.md)). AI-authored
   security-critical code must not serve as its own only validation.
8. **Style last and minor.** Only readability issues that tax the maintenance interface (I16); mechanical
   style belongs to the repo's lint/format tooling. Never demand reformatting as a review comment.

## Checklist

| Check | Mechanism | Evidence to look for |
|---|---|---|
| Hidden mutable defaults | Default argument objects are created once at `def` time and shared across calls | `def f(x=[])`/`{}`/`set()`, mutable class attributes in the diff; intentional shared state must be documented |
| Exception swallowing (I13) | Broad `except Exception` with no recover/translate/retry/record; bare `except:`; error→`None` silently | Every `except` in the diff: where is the failure visible, and what is the consequence? |
| Validation at boundaries (I1) | External/persistence data has a risk-appropriate contract; annotations are not runtime validation [STANDARD] | Request payloads, files, API responses, env vars flowing into logic without an adequate boundary check |
| Resource lifecycle (I2) | Files, sockets, locks, subprocesses, sessions, transactions released by context managers/`finally` | New resources without `with`/`finally`/`aclose`; `__del__`-based release = finding ([LANGUAGE] does not promise prompt GC) |
| Import side effects (I3) | Top-level code stays cheap and predictable | Module-level network clients, data loads, env-dependent initialization added by the diff |
| Cancellation (I6) | Timeouts/cancellation reach I/O; `CancelledError` is not swallowed into a normal result | Async diffs: bare `except`, `except BaseException`, or explicit `CancelledError` suppression; unowned `create_task` |
| Scope of changes | Diff fixes the stated problem and little else | Drive-by rewrites, tooling swaps, dependency bumps smuggled into a bug fix |
| Dependency adds (I12) | Each new dependency has a value case proportional to its cost | `pyproject.toml`/lockfile changes without a stated reason; inspect consequence before grading |
| Retry safety (I8) | Every retry answers "can this safely happen twice?" | Retry around charge/send/increment/insert without an effect-level idempotency or reconciliation plan |
| Data integrity | Partial failure cannot corrupt state | Multi-step writes without a transaction or compensation path |
| Concurrency/state (I4) | Shared mutable state touched by the diff has an owner and a synchronization story | New globals, caches, class-level state, shared sessions |
| Tests present and run | Behavior tests at risk depth; run result stated | A consequential path left untested; "should work" without a run where the environment permits testing ([evidence-rules §6](../core/evidence-rules.md)) |
| Leaked procedure or broken substitution | Callers that only want an outcome do not encode the steps; a subtype still supports the operations its base exposes | Tests pass while every caller lists the same steps; a `list`/`dict` subclass tested only through its new methods ([architecture.md](../references/architecture.md)) |
| Style (I16) | Readability of what changed; clever compression flagged only when it taxes readers | Deeply nested comprehensions doing real work, metaprogramming where plain code suffices |

## Finding format

Per [templates/code-review.md](../templates/code-review.md), every finding states:
`Severity:` `Evidence:` `Why it matters:` `Recommended change:` `Trade-off:` `Verification:`.

- Severity follows the reachable consequence in this codebase, not the invariant's MUST/SHOULD label.
  Reserve **Critical** for severe reachable harm; a rule breach with negligible effect may be Low or
  not a finding. See [invariants](../core/python-invariants.md#using-these-in-reviews).
- `Evidence:` cites file/line, test, config, or observed behavior. No evidence → not a finding.
- `Verification:` names the cheapest check that confirms the fix (test, command, reproduction).

### Example finding (shape only)

- **Severity:** High
- **Evidence:** `jobs/sync.py:57` wraps `charge(customer, amount)` in a 3-attempt retry loop; the
  charge API has no idempotency key and `payments/record.py` inserts a row per attempt.
- **Why it matters:** a timeout after the charge succeeded but before the response arrives produces a
  double charge on retry (I8) — a correctness defect with money impact.
- **Recommended change:** pass a stable idempotency key to a charge API that honors it. If the gateway
  cannot dedupe, stop automatic retries and reconcile unknown outcomes before sending again; queue
  redelivery is also a retry.
- **Trade-off:** the payments API must honor the key; reconciliation without that support adds state
  and operational work.
- **Verification:** with a fake gateway that honors keys, test a successful charge whose response times
  out; assert one effect per key and an unresolved result until confirmation arrives.

### Review depth scaling

Depth follows risk × blast radius ([principles §7](../core/engineering-principles.md)): a two-line
script fix gets the correctness rows and little else; a diff touching auth, money, schema, or
subprocesses gets the full checklist plus [security-review.md](security-review.md) treatment. State in
the output which depth was applied so the reader can calibrate trust.

## False positives / legitimate exceptions

- **Documented shared default state** (explicit memoization, sentinel registries) is legitimate when the
  sharing is the intent and it is named.
- **A top-level worker boundary that records failure and isolates a job** is correct broad exception
  handling (I13 exception) — provided it logs/records the failure.
- **Process-lifetime singletons released via shutdown handlers** satisfy I2; GC timing is not involved.
- **Tiny nonblocking CPU work in async code** with a measured upper bound is not an I5 violation.
- **Repository conventions are the starting point.** The repo's formatter, ORM, typing depth, and package manager
  should be inspected first ([existing-codebase](../playbooks/existing-codebase.md)); propose change only with a
  named problem.
- **Test-only and throwaway script code** gets less ceremony than production paths (I1 exceptions,
  [principles §7](../core/engineering-principles.md)).
- **Suppression comments** are signals to inspect: report a finding only when the suppressed check
  conceals a concrete defect or maintenance consequence. A missing explanation alone is not a defect.

## Output expectations

- Report findings in priority order, highest first. Anything High/Critical leads; nothing is buried
  under style commentary.
- "No significant issue found." is a valid complete review result. State the surface checked and what
  was out of scope; never invent findings to appear thorough.
- Recommend changes the author can act on; do not rewrite the diff inside the review.
- For code crossing trust boundaries, state explicitly which checks were performed versus assumed
  ([principles §5](../core/engineering-principles.md), [evidence-rules §6](../core/evidence-rules.md)).
- If the review could not run the tests/type-checkers that exist in the repo, say so — verification is
  part of the work ([principles §9](../core/engineering-principles.md)).
