# Testing Review

## Contents

- [Scope & trigger](#scope--trigger)
- [Review contract](#review-contract)
- [Procedure](#procedure)
- [Checklist](#checklist)
- [Finding format](#finding-format)
- [False positives / legitimate exceptions](#false-positives--legitimate-exceptions)
- [Output expectations](#output-expectations)

Review of test suites and test strategy. Philosophy: **confidence per maintenance cost** — the goal is
the most risk-reduction per hour of test maintenance, not the most tests ([references/testing.md](../references/testing.md)).
This review judges what the suite gives confidence *in*; it does not demand coverage percentages as a proxy.

## Scope & trigger

Use when: a test suite is being designed or restructured ([TEST] tasks); a refactor needs a safety net
([REFACTOR] tasks); tests are flaky, slow, or constantly broken by unrelated changes; a critical behavior
looks untested ("who would catch it if this broke?"); or before trusting a suite as evidence for a
release ([production-readiness.md](production-readiness.md)). Test code inside a diff is reviewed at
[code-review.md](code-review.md) depth too; this file covers the suite as a system.

## Review contract

Follow the shared [review contract](code-review.md#review-contract) for task scope,
priority, severity, evidence, finding format, and a valid clean-review outcome.

## Procedure

1. **Build the risk coverage map first.** List the behaviors that would cause real damage if wrong
   (money movement, auth decisions, data writes, schema migrations, public API contracts). For each:
   which test would fail if it broke?
2. **Identify the confidence mechanism per risk**: unit test, integration test at the real boundary,
   contract test, migration test, property/state-machine test ([references/testing.md](../references/testing.md)).
3. **Check for inverted architecture**: mock-dominated suites where real boundaries (DB, serialization,
   HTTP contracts, migrations) are exactly what is mocked away.
4. **Check the failure paths**: does the suite exercise timeouts, partial failure, cancellation,
   malformed input — or only the happy path?
5. **Check determinism**: time, randomness, ordering, network, and shared state in tests; flakiness is
   a maintenance tax that erodes trust in every result.
6. **Check maintenance cost**: fixture graphs, mock setups, and duplication as architecture; a test that
   breaks on every unrelated refactor is a design signal about both the test and the code.
7. **Check assertions test behavior, not implementation** — private method calls, exact call orders on
   internals, and struct echoes couple tests to shape instead of behavior.
8. **Report** in the standard format; recommend the smallest suite change that closes the biggest
   confidence gap.

### Risk coverage map (worked shape)

| Risk (damage if wrong) | Confidence mechanism | Status |
|---|---|---|
| Double charge on retried payment | Integration test: first attempt times out after success | Missing → High |
| Migration corrupts order totals | Migration test on 10k-row fixture with before/after assertion | Present |
| Authz bypass on `/admin` routes | Contract test: non-admin token rejected per route | Missing → High |
| CSV export wrong on empty/UTF-8 input | Unit tests with parametrized examples | Present |
| Queue consumer duplicates jobs after crash | Failure-path test: kill mid-job, assert re-delivery semantics | Partial → Medium |

## Checklist

| Check | Mechanism | Evidence to look for |
|---|---|---|
| Risk coverage map | High-damage behaviors have a named confidence mechanism that would catch a break | Money/auth/data-write/migration paths with no such check; grade by reachable damage and other controls |
| Inverted test architecture | Real boundaries mocked while mocks are asserted on | 200 unit tests over a service layer; zero tests touching the actual DB/serializer/API contract |
| Excessive mocking | Mocks substitute for boundaries the code actually crosses | `MagicMock` wrapping the ORM/HTTP client whose real behavior (SQL shape, status handling) is the risk |
| Real-boundary tests | Integration/contract tests at DB, HTTP, serialization, filesystem seams | A test running real SQL against a real (possibly containerized) DB; contract fixtures for external APIs |
| Failure-path tests | Timeouts, partial failure, cancellation, malformed input exercised | Retry/compensation code with no test where the first attempt fails; async code with no cancellation test |
| Migration tests | Migrations and their recovery path run on realistic data | `alembic upgrade`/Django migration tests; backfill correctness tested at meaningful volume; rollback tested where reversible, forward recovery where not ([migration-plan](../templates/migration-plan.md)) |
| Concurrency tests | Where races are possible: targeted interleaving/stress tests | Shared-state code with only sequential tests; note limits honestly — tests reduce but do not prove race-freedom |
| Deterministic tests | Time, randomness, and unspecified ordering controlled | `sleep()`-based synchronization, unseeded randomness, dependence on set iteration order or insertion order that comes from nondeterministic input, wall-clock assertions. `dict` preserves insertion order [LANGUAGE] |
| Test maintenance cost | Fixture graphs and mocks are themselves architecture | 15-fixture dependency chains for one test; a mock change breaking dozens of tests |
| Behavior assertions | Tests assert observable behavior, not implementation shape | Assertions on private attributes, exact internal call sequences, "the mock was called with…" replacing outcome checks |
| Run and CI evidence | Suite runs in CI with stated command; failures block | Green badge with tests skipped/`xfail`-ed silently; suite not in CI at all |

**Not checked here: coverage percentages.** Coverage is a weak proxy — a suite can reach 100% with
mock-dominated tests that prove nothing. What matters is which risks have a test that would actually
fail ([references/testing.md](../references/testing.md)).

## Finding format

Per [templates/code-review.md](../templates/code-review.md):
`Severity:` `Evidence:` `Why it matters:` `Recommended change:` `Trade-off:` `Verification:`.

Grade missing tests and test defects by the reachable regression they leave undetected, not by test
count or the invariant's MUST/SHOULD label. A missing test for a reachable payment duplication path
may be High; a low-risk helper gap may be Low or no finding. Evidence names the behavior and why no
existing test would catch its breakage.

### Example finding (shape only)

- **Severity:** High
- **Evidence:** `tests/test_transfer.py` mocks `db.session` and asserts `session.commit` was called;
  no test executes real SQL for the transfer use case; the production DB is PostgreSQL but tests run
  against nothing (SQLite not used either).
- **Why it matters:** the suite proves the mock arrangement, not the transaction behavior — the
  balance invariant and the commit/rollback boundary have zero failing-test coverage (false confidence).
- **Recommended change:** add one integration test at the real DB boundary (testcontainers or CI
  service) covering transfer success + insufficient-funds rollback; keep the fast unit tests.
- **Trade-off:** integration tests add CI time and an infra dependency; one boundary test buys more
  confidence than the mock tests it supplements.
- **Verification:** deliberately break the invariant (commit before validation) and confirm the new
  test fails; CI runs it on every PR.

## False positives / legitimate exceptions

- **Unreachable error-path isolation** (simulating OOM, simulating a driver bug) legitimately uses
  mocks/substitution — the boundary is genuinely out of reach.
- **Pure functions and tiny utilities** need little ceremony; example-based tests may suffice
  ([principles §7](../core/engineering-principles.md)).
- **A mocked external API with a maintained contract fixture** is not the inverted-architecture smell;
  the smell is mocking the boundary *and* never testing the contract.
- **Some nondeterminism is inherent** (time-based expiry logic); the fix is injection/controlling time
  where it matters, not flagging every `datetime.now`.
- **Fast unit suites without integration tests** can be correct for libraries with pure cores — the risk
  map decides, not a quota.
- **`xfail`/skip with a stated reason** is legitimate; silent skips are the finding.
- **Do not demand new tests for every refactor** — existing behavior coverage is the safety net; tests
  scale with risk, not with diff size.

## Output expectations

- Lead with the risk coverage map result: which dangerous behaviors have real confidence and which have
  none. That gap list is the deliverable.
- "No significant issue found." is valid — including "the suite adequately covers its named risks".
  Never invent coverage gaps or demand tests for test theater.
- Recommendations name the single test (and its boundary) that would close each gap, plus its cost;
  prefer one integration test at the real boundary over ten more mock tests.
- State honestly what tests cannot prove (race-freedom, absence of security flaws) so the suite is not
  oversold as evidence ([evidence-rules §6](../core/evidence-rules.md)).
