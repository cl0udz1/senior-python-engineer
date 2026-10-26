# Testing

## Contents

- [Test types: when each earns its cost](#test-types-when-each-earns-its-cost)
- [pytest: fixtures and parametrization](#pytest-fixtures-and-parametrization)
- [Property-based and stateful testing (Hypothesis)](#property-based-and-stateful-testing-hypothesis)
- [The inverted-test-architecture failure mode](#the-inverted-test-architecture-failure-mode)
- [Fakes vs mocks](#fakes-vs-mocks)
- [Testing real boundaries where practical](#testing-real-boundaries-where-practical)
- [What needs confidence per domain](#what-needs-confidence-per-domain)
- [Deterministic tests](#deterministic-tests)
- [CI test lanes](#ci-test-lanes)
- [Test maintenance cost](#test-maintenance-cost)

Testing philosophy: **confidence per maintenance cost**. A test suite exists to make specific changes
safe; tests whose maintenance cost exceeds the defect risk they cover are debt. Version-sensitive facts
live only in [modern-python-baseline.md](modern-python-baseline.md). Invariants I1–I16 in
[python-invariants.md](../core/python-invariants.md); review procedure in
[testing-review.md](../reviews/testing-review.md).

## Test types: when each earns its cost

| Type | Buys confidence in | Earns cost when | Skips when |
|---|---|---|---|
| Unit (pure logic) | Fast rules/algorithms/invariants | Logic has branches worth pinning | Trivial glue code |
| Integration (real DB/real boundary) | SQL, serialization, migrations, ORM behavior | Data correctness matters (most services) | Pure computation with no I/O |
| Contract (external API shape) | Third-party APIs, provider drift | You depend on someone else's schema | Fully controlled internal calls |
| E2E (through real stack) | Wiring, auth, config, lifecycle | Release confidence needs the full path | Slow suite replacing unit coverage |
| Property-based (Hypothesis) | Invariants over input space | Domain rules hold for *all* values (money, parsing, serialization) | Behavior is example-table simple |
| Stateful (Hypothesis stateful) | State machines, workflow invariants | Multi-step operations with invariants (orders, sessions, queues) | One-shot transforms |
| Concurrency | Races, ownership, cancellation | Multiple threads/tasks touch shared state (I4–I6) | Single-threaded code |
| Failure-path | Timeouts, retries, partial failure, crash mid-job | External dependencies exist (all production services) | Local pure scripts |
| Migration | Schema change safety on real data shapes | Any production database with real data | Disposable local DBs |

- Coverage percentage is a smell-detector, not a goal: 100% of trivial getters ≠ confidence in
  transactions. The question is always "what failure does this test make impossible to ship unnoticed?"

## pytest: fixtures and parametrization

- Fixtures give **explicit setup/cleanup** with scope control (`function`/`class`/`module`/`session`) and
  `yield` teardown. Keep scopes honest: a `session`-scoped fixture holding DB state leaks between tests
  unless designed for sharing; default to `function` scope and widen only with a stated reason.
- **pytest-asyncio loop scoping** [FRAMEWORK] (1.x docs, including 1.4): async tests use a function-scoped
  loop unless `asyncio_default_test_loop_scope` or `@pytest.mark.asyncio(loop_scope=...)` says otherwise.
  An async fixture's loop scope defaults to that fixture's cache scope while `asyncio_default_fixture_loop_scope`
  is unset; the project documents that unset default as moving to `function`, so set it explicitly.
  The fixture's loop scope must be at least as wide as its cache scope. A test and the async fixtures it
  uses have to share one loop: widening only the fixture loop while tests stay on function loops asks for
  two loops and errors. The `event_loop` fixture was removed in pytest-asyncio 1.0 — do not reintroduce it.
  A session-scoped database container can stay a normal fixture; only the async connection needs a loop,
  and that loop has to match the tests that await it.
- Parametrization covers systematic example sets (`@pytest.mark.parametrize`) without copy-paste; use
  for boundary values, error codes, and format variations. Parametrize *inputs*, assert *behavior*.
- Review fixture complexity when it hides the behavior under test, couples unrelated tests, or makes
  failures hard to diagnose. Setup length alone is not a defect; real resource integration may need
  substantial setup. Use factories or clearer boundaries when they improve those concrete problems.
- Prefer `yield` for a simple acquire/use/release lifecycle. If setup can fail after partial acquisition,
  register cleanup immediately after each successful acquisition with `request.addfinalizer`, or use
  an `ExitStack`/separate resource fixtures. Code after `yield` does not run if setup fails before that
  yield. Register finalizers only once their resource needs cleanup. See
  [pytest safe teardown](https://docs.pytest.org/en/stable/how-to/fixtures.html#safe-teardowns).

## Property-based and stateful testing (Hypothesis)

- Property-based testing earns its cost on **invariants**: "serialize∘deserialize is identity",
  "sort output is a permutation of input and ordered", "total never negative", "parser accepts all
  valid inputs in grammar G". Hypothesis generates edge cases humans forget (empty, huge, unicode,
  duplicates) and shrinks failures to minimal repros [ECOSYSTEM].
- Stateful testing (Hypothesis state machines) targets multi-step invariants: "checkout → pay → ship"
  sequences never violate "paid implies order not cancelled". Model the *rules*, not the API surface.
- When NOT to use: example tables that are clearer as explicit parametrize lists; UI layout; anything
  where shrinking produces misleading minimal cases (use targeted integration examples instead).
- Property tests still need a deterministic seed story for CI flake diagnosis (below).

## The inverted-test-architecture failure mode

- Symptom: hundreds of mock-dominated unit tests, and the database, serialization formats, migrations,
  queue semantics, and external contracts are untested. The suite verifies mock arrangements, not
  behavior; refactors break tests while real defects pass.
- This is the **excessive mocking smell** ([catalogs/smells.md](../catalogs/smells.md)). Root cause:
  mocks are cheap to write and give a green checkmark per test, so suites drift toward testing the
  wiring instead of the risk.
- Fix direction: test real boundaries where practical (test DB, local file, recorded HTTP contract),
  keep mocks at the outermost unstable edge, and re-balance the pyramid toward integration for
  data-critical paths ([persistence.md](persistence.md)).

## Fakes vs mocks

- **Mock**: configured to verify interactions (`assert_called_with`). Brittle — couples tests to
  implementation detail (how it was called) rather than behavior (what resulted).
- **Fake**: simplified real implementation (in-memory dict store, fake clock, stub HTTP server).
  Behavior-compatible, testable against the same contract tests as the real one [HEURISTIC].
- Rule of thumb: prefer fakes for boundaries you own or that are simple (clock, store, mailer); reserve
  mocks for verifying *external* interaction contracts (did we call the payment API once?) where the
  interaction *is* the behavior. Assertion style: assert outcomes first, interactions only when the
  interaction is the requirement (retries, calls-per-request limits).

## Testing real boundaries where practical

- Database logic: test against a real DB engine (not SQLite if you deploy to PostgreSQL — dialect
  differences are real); use transaction rollback or per-test schemas for speed; test migrations on
  realistic data volumes at least in CI ([persistence.md](persistence.md)).
- Serialization: round-trip property tests; schema evolution tests (old payload → current code).
- External APIs: contract tests against recorded/stubbed schemas with version drift alerts
  ([reliability.md](reliability.md) on schema compatibility).
- Concurrency: tests that use barriers/timeouts to force interleavings (racy code tested only by happy
  paths is untested); beware flakiness — a flaky concurrency test is often finding a real race
  ([asyncio-concurrency.md](asyncio-concurrency.md)).

## What needs confidence per domain

| Domain | Highest-value confidence |
|---|---|
| WEB_API | Validation boundaries (I1), auth/authz, error mapping, serialization |
| WORKERS_JOBS | Idempotency (I8), crash mid-job, retries, queue semantics |
| DATA_ENGINEERING | Schema evolution, data volume behavior, backfill correctness |
| AI_ML | Data pipeline determinism, metric computation, serialization safety ([ai-ml.md](ai-ml.md)) |
| LIBRARY_PACKAGE | Public API contract across versions, typed surface ([typing.md](typing.md)) |

Route per domain to the matching [playbook](../playbooks/web-api.md) (web-api, workers-jobs, data-engineering, ai-ml, library-package).

## Deterministic tests

- **Time**: inject a clock/fake time source; never `sleep` to wait for behavior (use synchronization
  primitives or virtual clocks). Timezone-dependent logic gets explicit TZ in tests.
- **Randomness**: seed explicitly; when testing seed-sensitive code (ML), test the property (distribution
  shape, range) rather than exact values.
- **Concurrency**: design tests to be deterministic where possible (barriers, fakes); where
  nondeterminism is inherent, run with repetition and quarantine flaky tests with a tracking issue —
  never delete a flaky test that found a real race.
- **Ordering**: tests must pass in any order (no cross-test state); if they don't, that's hidden shared
  state (I4) leaking through fixtures or globals.

## CI test lanes

- Split the suite by cost and dependency: **unit lane** (no I/O, seconds) runs on every push;
  **integration lane** (real DB/files, [persistence.md](persistence.md)) runs on every merge/PR;
  **slow lane** (E2E, load, migration-on-real-data) runs pre-release or nightly. The lane assignment
  is a property of the test, not of the branch.
- Each lane is deterministic in isolation ([deterministic tests](#deterministic-tests) above); a flaky
  integration lane gets quarantined with a tracking issue, not retried into green.

## Test maintenance cost

- Tests scale with risk ([SKILL.md](../SKILL.md)); a script gets smoke coverage, a payment path gets
  property + failure-path + integration coverage. Every test states the failure it prevents; suites
  that accumulate tests "to raise coverage" accumulate maintenance cost without confidence.
- When refactoring breaks many tests without changing behavior, the tests are coupled to
  implementation shape (too many mocks, over-specific assertions). Fix the tests' coupling, don't
  contort the design to satisfy the suite.
