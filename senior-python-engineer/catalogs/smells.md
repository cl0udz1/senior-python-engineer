# Design & Architecture Smells — Quick List

## Contents

- [Structure and size](#structure-and-size)
- [Interfaces and parameters](#interfaces-and-parameters)
- [Behavior and control flow](#behavior-and-control-flow)
- [Layer and boundary leakage](#layer-and-boundary-leakage)
- [Control flow and signals](#control-flow-and-signals)
- [Smell interactions (clusters)](#smell-interactions-clusters)
- [Triage rule: comment or leave it?](#triage-rule-comment-or-leave-it)

Lighter-weight heuristics than the [Anti-Pattern Catalog](anti-patterns.md): these are *design* smells —
signals that structure may be fighting the problem. Each entry is **clue → why → nudge**, not a defect
verdict. **A smell is not automatically a defect.** Most entries are [HEURISTIC]; where a mechanism is a
language/framework fact, it is tagged.

Load this during design and architecture review ([Architecture Review](../reviews/architecture-review.md)),
or when refactoring ([Existing Codebase](../playbooks/existing-codebase.md)). Implementation-level
mechanisms (mutable defaults, N+1, shared sessions) live in [anti-patterns.md](anti-patterns.md).

---

## Structure and size

### God module / god class
- **Clue:** one file or class owns several unrelated concerns; most changes touch it; its test file is a thicket.
- **Why:** it concentrates coupling; ownership of state/transactions inside it becomes ambiguous.
- **Nudge:** split by things-that-change-together; shrink the public surface first. Detail: [anti-patterns](anti-patterns.md) §20.

### Over-normalized / over-abstracted module tree
- **Clue:** 40 modules averaging 15 lines; `models/`, `services/`, `utils/`, `managers/`, `handlers/` with one item each; you must open 6 files to follow one call.
- **Why:** navigation cost with no reuse payoff — the tree encodes imagined future growth, not current change patterns (I11).
- **Nudge:** merge by domain concept until each module is worth a name; directory structure should mirror change frequency, not job titles.

### Shotgun surgery (scattered changes)
- **Clue:** one feature request touches 10 files across unrelated directories; the same constant/logic duplicated in three places.
- **Why:** the module boundaries don't match the axes of change; every feature pays a scatter tax and drifts.
- **Nudge:** gather the scattered pieces behind one owner (module/function) before adding the next variant.

### Feature envy
- **Clue:** a function/class that mostly reads another object's data (`other.a`, `other.b`, `other.c()` to do its work).
- **Why:** behavior lives next to the wrong data; every change to the data's shape breaks the envious code.
- **Nudge:** move the behavior to where the data lives, or extract the shared concept explicitly.

### Dead abstraction
- **Clue:** an interface/layer whose "flexibility" has never been used; a base class with one descendant; indirection that reviewers keep asking "why does this exist?" about.
- **Why:** pure navigation tax; abstraction without a consumer is ceremony (I11).
- **Nudge:** inline it now; re-abstract when the second real case arrives. Detail: [anti-patterns](anti-patterns.md) §18.

### Speculative generality
- **Clue:** config knobs/parameters/plug-in points with exactly one value; "for future extensibility" in comments with no near-term second consumer.
- **Why:** the guessed axis of variation is usually wrong; every reader pays to understand an option that can't be chosen.
- **Nudge:** delete the knob; when the need is real it will arrive with a concrete requirement (record the trigger in an [ADR](../templates/architecture-decision-record.md) if it's a big bet).

## Interfaces and parameters

### Primitive obsession
- **Clue:** `def charge(amount_cents: int, currency: str, account_id: str, ...)` — raw strings/ints carrying domain meaning; validation repeated at every call site.
- **Why:** invariants live in callers' heads; units and formats silently mix (dollars vs cents, IDs vs names).
- **Nudge:** where repeated mix-ups cause defects, introduce a small value object with runtime checks
  at the trust boundary (I1). `NewType` and `TypedDict` help static checking but do not validate at
  runtime; a frozen dataclass is only shallowly immutable.

### Long parameter list vs missing object
- **Clue:** 5+ parameters that always travel together; callers build the same tuple repeatedly.
- **Why:** the parameter group *is* a concept without a name; change requires editing every signature.
- **Nudge:** group into a dataclass/TypedDict named after the concept — the name is the payoff, not the class.

### Boolean-parameter ambiguity
- **Clue:** `process(order, True, False)` at call sites; `def sync(data, force=False, recursive=False, dry_run=False)` where readers must check the signature to decode.
- **Why:** positional booleans encode meaning invisibly; adding a third flag silently changes call-site meaning.
- **Nudge:** keyword-only args, or split into two named functions (`def preview(...)` / `def apply(...)`).

### Boolean blindness
- **Clue:** functions return `bool` and callers immediately re-derive *why* (`if is_valid(x): use(x.reason())` — where the reason had to be recomputed).
- **Why:** the boolean discards information the caller needs; logic duplicates the classification.
- **Nudge:** return a small enum/result object carrying the reason; let the caller branch on the reason.

### Stringly-typed config/flags
- **Clue:** `if mode == "fast"` scattered through code; `"off"/"Off"/"0"` all meaning disabled; typos fail silently at runtime.
- **Why:** strings are not a closed set [LANGUAGE]; no tooling catches the typo until production.
- **Nudge:** `Literal[...]`/`Enum` at the config boundary + validation at startup (I1); parse once in the settings module.

### Silent fallback defaults
- **Clue:** `os.getenv("TIMEOUT", "30")` where 30 was chosen casually; `cfg.get("retries") or 3`; a missing key silently selects behavior.
- **Why:** misconfiguration becomes invisible; the default encodes an unstated policy decision.
- **Nudge:** distinguish *required* (fail fast at startup) from *explicitly defaulted* (documented policy next to the default). See [anti-patterns](anti-patterns.md) §21.

## Behavior and control flow

### Temporal coupling (call-order dependency)
- **Clue:** `obj.init(); obj.load(); obj.run()` where any other order raises or corrupts; state machine enforced only by convention.
- **Why:** the API allows invalid sequences, so every caller must memorize the ritual; bugs look like "works in tests, fails in prod".
- **Nudge:** make illegal states unrepresentable — constructor takes what it needs, or one entry method does init+load+run; use a context manager for setup/teardown (I2).

### Hidden time / I/O in innocent-looking functions
- **Clue:** `def get_name(self)` that hits the network; `calculate()` that reads a file; no `await`/doc hint of I/O in the name or signature.
- **Why:** callers can't reason about latency, retries, or failure; async boundaries get violated (I5) precisely because the I/O is disguised.
- **Nudge:** name/annotate the I/O (`fetch_*`, `load_*`, async signature), or return cached data and make the fetch explicit at the boundary.

### Deep nesting doing real work
- **Clue:** 4+ indentation levels with business logic inside; early-return opportunities visibly unused.
- **Why:** each level multiplies the state-space a reader must hold; error paths hide at the bottom.
- **Nudge:** guard clauses / extract the inner block into a named function; flatten once, don't restructure the design.

### Clever compression
- **Clue:** nested comprehensions with side effects, `getattr`/`globals()` tricks, decorator stacks that rewrite signatures, metaprogramming used for brevity.
- **Why:** readability is the maintenance interface of the code (I16); "Pythonic" means readable and predictable, not compact [STANDARD] (PEP 20 is informational).
- **Nudge:** expand to a loop with names; keep the clever version only if the expanded version is genuinely worse *and* a comment/explanation is cheaper than either.

### Tests as specification of implementation
- **Clue:** tests assert private attributes, call orders into mocks, exact log strings; renaming internals breaks tests without behavior change.
- **Why:** the suite freezes structure instead of behavior; refactoring cost explodes (see [anti-patterns](anti-patterns.md) §14).
- **Nudge:** re-assert at the public boundary; replace implementation-assertions with behavior-assertions when the test next breaks.

## Layer and boundary leakage

### Wrong layer leakage
- **Clue:** framework request/response objects inside domain logic; ORM session objects passed into pure business functions; domain rules imported into views/templates.
- **Why:** domain behavior becomes untestable without the framework, and framework migration touches the core (I10).
- **Nudge:** translate at the boundary (framework type → plain/domain type); keep the dependency direction pointing inward. Test: can the domain function run with no framework imported?

### Controller-as-domain (inlined use-case smell)
- **Clue:** HTTP route handlers, CLI commands, or background tasks contain 50+ lines of raw SQL, transaction scopes, business validation, and external dispatches; similar transactional sequences are duplicated across entrypoints.
- **Why:** Dogmatic refusal of a domain layer under-engineers complex workflows; business logic becomes tightly coupled to transport protocols, untestable in isolation, and prone to transaction/consistency drift.
- **Nudge:** Extract the multi-step transaction and business logic into a cohesive service function or domain object; keep controllers thin and focused on protocol adaptation (request parsing, status codes, serialization).

### Cross-service / cross-module time-shape coupling
- **Clue:** module A's correctness depends on module B being fast; a "quick" call in a loop "for now"; assumptions like "this table is small" living in a distant caller.
- **Why:** implicit performance contracts break silently as data grows (the N+1 family at design level).
- **Nudge:** make the assumption explicit (bounded pagination, batch API, documented size limit) or move the loop into the owner.

## Control flow and signals

### Exception-driven control flow
- **Clue:** exceptions raised for most items in a hot loop merely to steer an ordinary branch, or
  `StopIteration` manually used where a loop would be clearer.
- **Why:** frequent exception construction/unwinding can add cost and obscure the path being handled.
  `try/except KeyError` is often idiomatic and may avoid a double lookup; judge by clarity and workload.
- **Nudge:** use `dict.get` (with a sentinel if `None` is a value), `next(it, default)`, or plain branching
  when it makes common cases clearer. Keep `try/except` when it states the intended behavior directly.

### Environment-branching in production code
- **Clue:** `if TEST`, `if DEBUG`, `if os.getenv("CI")` sprinkled through business logic; a behavior matrix nobody can enumerate.
- **Why:** tested behavior diverges from production behavior along an unbounded axis; this is scattered configuration's cousin ([anti-patterns](anti-patterns.md) §21).
- **Nudge:** inject the differing dependency (clock, client, filesystem) instead of branching on environment; test seams belong at boundaries.

### Hidden ordering / bookkeeping flags
- **Clue:** `self._initialized` / `self._loaded` flags guarding methods; half-enforced rituals like `if not self._setup: raise`.
- **Why:** temporal coupling dressed as defensive coding — invalid states remain representable and the flags drift out of sync with reality.
- **Nudge:** fold setup into construction or a context manager (I2); make the phase part of the type or the call sequence, not a boolean.

### Misleading names & comment rot
- **Clue:** function name contradicts current behavior; comments restating the next line; commented-out code blocks "kept just in case".
- **Why:** readers trust names first; a rotting name actively misleads — worse than a missing one.
- **Nudge:** rename in the very diff that changes behavior; delete restating comments; recover old code from version control, not from corpses in the file.

### Public surface without intent
- **Clue:** `import *`; external code importing `_private` modules; everything reachable treated as API; no deliberate exported-names list.
- **Why:** internals become de-facto API; every internal refactor breaks an unknown consumer.
- **Nudge:** export deliberately (`__init__`/`__all__` as the contract); treat out-of-contract imports as boundary bugs; a library states its API ([library-package playbook](../playbooks/library-package.md)).

### Mixed paradigms without reason
- **Clue:** classes in one module, dicts-in-functions in the next, global mutables in a third, for the same kind of problem; style visibly switches mid-file.
- **Why:** conventions exist to cut the reader's context-switch cost; gratuitous variety taxes everyone (I16).
- **Nudge:** pick one convention per problem kind and follow the repo's existing style; a novel style needs a reason, not just variety.

### Write-only observability
- **Clue:** logs/metrics no dashboard, alert, or query references; `log.debug` forests nobody enables; metrics with permanent zero readers.
- **Why:** signals have real cost (volume, cardinality, noise); write-only instrumentation buries the signals someone actually reads.
- **Nudge:** wire each signal to the decision it should drive, or delete it; observability exists to trigger actions ([Observability](../references/observability.md)).

## Smell interactions (clusters)

Smells multiply; the product is what matters:

- **God module + shotgun surgery** → change-risk concentration: every feature both touches it and is slowed by it.
- **Primitive obsession + stringly-typed flags** → validation debt at every boundary (I1 violations waiting to happen).
- **Temporal coupling + hidden I/O** → latency and failure become un-reasonable from the signature alone (I5/I6 hazards).
- **Dead abstraction + speculative generality** → pure navigation tax; delete before redesigning.
- **Tests-as-implementation + excessive mocking** → a suite that resists the exact refactors it should enable.

When a review finds 3+ smells in one area, stop listing smells: name the underlying cause once (missing
ownership boundary? wrong module split?) — that is the finding.

---

## Triage rule: comment or leave it?

The review priority order governs: correctness → security → data integrity → concurrency/state ownership →
resource lifecycle → failure behavior → performance → maintainability → readability/style
([SKILL.md](../SKILL.md)). **Style and smell findings never outrank correctness.** A review that leads
with three abstraction complaints while missing a swallowed exception has failed.

| Situation | Action |
|---|---|
| Smell + demonstrated concrete harm (bug, outage risk, measured perf, security surface) | Comment as a finding in [finding format](../templates/code-review.md), severity from the harm |
| Smell without demonstrated harm, but change is 5 minutes and clearly net-positive | One-line suggestion in Minor notes; never block |
| Smell without harm, fix is structural | Note as a named risk with the condition that would make it real ("if a second backend appears, extract the port"); do not demand speculative restructuring |
| Taste disagreement with working repo convention | Leave it. Local convention outranks personal preference (I16) |
| Smell inside code the change doesn't touch | Mention once at most, as context; not a finding on this diff |

Rule of thumb: **comment when the reader's next decision would change; leave it when it only satisfies
taxonomy.** "This is a god class" with no consequence is taxonomy; "this god class now owns both the
transaction and the retry policy, so the double-charge path has no owner — here's the failing scenario"
is a finding.

### Worked triage examples

**Comment (as a finding):** *"`service.py:120` takes `is_async: bool` and branches the whole write path;
the call at `views.py:44` passes it positionally after two other args. If the flag is inverted the charge
runs twice. Severity Medium (correctness risk from boolean-parameter ambiguity) — split into
`apply()`/`preview()` or make it keyword-only."* — the smell and the concrete failure are both named.

**Leave it:** a 220-line module with one cohesive concern and stable tests, in a repo where every other
module is 200–300 lines. "God module" by line-count taxonomy, zero demonstrated harm, splitting would
fight local convention (I16). At most a passing note; never a blocking finding.

**Comment once, not as a finding:** a deep-inheritance hierarchy in untouched code that this diff now has
to decorate. Note the context cost in the PR description; file the restructuring as its own change with
its own tests.
