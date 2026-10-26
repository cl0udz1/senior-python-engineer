# Library / Package

## Contents

- [1. Typical system shape](#1-typical-system-shape)
- [2. Important constraints](#2-important-constraints)
- [3. Recommended discovery questions](#3-recommended-discovery-questions)
- [4. Common architecture choices](#4-common-architecture-choices)
- [5. What not to overengineer](#5-what-not-to-overengineer)
- [6. Failure modes](#6-failure-modes)
- [7. Performance considerations](#7-performance-considerations)
- [8. Testing strategy](#8-testing-strategy)
- [9. Security concerns](#9-security-concerns)
- [10. Deployment/lifecycle concerns](#10-deploymentlifecycle-concerns)
- [11. References for unresolved questions](#11-references-for-unresolved-questions)
- [12. Exit/readiness criteria](#12-exitreadiness-criteria)

**Modes:** DESIGN, IMPLEMENT, REVIEW · **Concerns:** PACKAGE · **Domains:** LIBRARY_PACKAGE
Procedure for reusable packages consumed by other code. Governing rule: the public API is a contract;
everything else is implementation ([Decision Model](../core/decision-model.md) §7).

## 1. Typical system shape

- **Public API surface first**: identify the supported import paths and behavior; a package-root facade
  is useful when it simplifies consumers, but submodule imports can also be the intended API [ECOSYSTEM].
- `pyproject.toml` [STANDARD] as the single metadata/config center: `[build-system]`, `[project]`, optional `[project.optional-dependencies]`, tool config. Executable `setup.py` workflows are [LEGACY].
- Tests organized against the *public* API (import the package the way users do), plus targeted internal
  tests where logic warrants; test supported Python versions at a depth proportionate to the consumer
  contract and release process.
- IF code serves one application only → it may still be an installable Python package for imports and deployment; it does not need a separately versioned, stable library API without consumers who rely on one.
- Logging policy: the library emits no unconfigured log noise by default; uses `logging.getLogger(__name__)` and lets consumers configure handlers [ECOSYSTEM].

## 2. Important constraints

- **API stability is the product** for independently consumed libraries: removals/renames can break consumers. State the chosen versioning policy and what counts as breaking [ECOSYSTEM]; docs and tests define the public surface, with `__all__` where useful.
- **Dependency ranges**: libraries declare ranges (what they work with), applications pin exact versions ([packaging](../references/packaging.md)). Every dependency is part of *consumers'* dependency trees — directness and transitive weight are cost ([I12](../core/python-invariants.md)).
- **Back-compat**: when consumers cannot upgrade in lockstep, deprecate before removal with a migration note and an appropriate warning window; test supported Python versions rather than merely claiming them.
- **Docs**: the README example is the first test a user runs; API reference for every public name.
- Import cost is borne by every consumer: import-time work stays cheap ([I3](../core/python-invariants.md)).

## 3. Recommended discovery questions

Ask only what changes the contract:
- Who are the consumers, and what do they actually use today? (The real API surface vs the aspirational one.)
- What Python versions and platforms must be supported? (CI matrix, syntax floor.)
- Which third-party types appear in public signatures? (They become part of your dependency contract.)
- Does the library need runtime validation of its inputs, or does it trust caller types? ([I1](../core/python-invariants.md), [typing](../references/typing.md).)
- Extension points: do consumers need to plug in behavior now, or is that speculation? (Protocol vs nothing.)
- Distribution: PyPI, private index, vendored? (Build/publish provenance requirements.)
- Stability expectations: internal package with coordinated deploys vs unknown external consumers? (Versioning strictness.)
- Do consumers need async as well as sync entry points? (Dual surface is permanent API cost — add only with a real consumer.)
- What platforms/OS/architectures are actually in use? (Wheels, pure-Python vs built.)

## 4. Common architecture choices

- **Typed public API** ([typing](../references/typing.md)): IF the package has external consumers or is refactored often → annotate the public surface, run a type-checker in CI, ship `py.typed` [STANDARD]. BUT IF annotation machinery would exceed the logic it describes → annotate signatures, keep internals simple ([Decision Model](../core/decision-model.md) §5).
- **Extension points**: IF third parties must substitute behavior → `Protocol` [STANDARD] (structural, no inheritance burden) at the call site. BUT IF consumers subclass for reuse rather than substitutability → composition helpers instead ([Decision Model](../core/decision-model.md) §2). ABC only where runtime enforcement or shared implementation is genuinely needed.
- **Runtime validation**: validate at the API boundary where misuse is likely and silent ([I1](../core/python-invariants.md)); do not double-validate trusted internal calls.
- **Versioning policy**: choose a policy consumers can use (semantic versioning is one option) and define which behavior and signature changes count as breaking [ECOSYSTEM]; raise the supported-Python floor on a stated consumer-impact basis.
- **Records in public API**: TypedDict/dataclass/NamedTuple for data shapes ([Decision Model](../core/decision-model.md) §5); a dataclass is a record, not a domain model [HEURISTIC].
- **Build backend**: any PEP 517 backend that fits the workflow [STANDARD]; the choice is tooling, not identity ([packaging](../references/packaging.md)).
- **Errors**: library-defined exception types callers can catch without string-matching; never raise bare `Exception`; document each public error condition.

## 5. What not to overengineer

- Plugin systems without a second consumer; abstract base classes where one function serves; registries and factories for a linear call graph ([I11](../core/python-invariants.md)).
- Stable-API promises for internals "just in case" — premature surface area is forever debt.
- Exotic typing machinery (higher-kinded emulation, deep generic hierarchies) that reviewers must decode; prefer the weakest contract that callers need ([Decision Model](../core/decision-model.md) §2).
- Supporting every Python version ever released, and every platform nobody uses; support what consumers need.
- Public config objects with dozens of knobs before a consumer needs them; every public parameter is forever.
- Optional-dependency matrices nobody exercises; multi-backend abstractions for one implementation.

## 6. Failure modes

Domain-relevant subset of [Failure Modes](../catalogs/failure-modes.md):
- **Leaking internals as API** — anything importable gets imported; deep imports of private modules break silently on refactor (mitigate: `__all__`, private naming, public-API-only tests).
- **Import-time heavy work** ([I3](../core/python-invariants.md)) — a library that opens connections, reads data, or compiles at import punishes every consumer's startup and tests.
- **Accidental transitive deps** — importing an undeclared package that only arrives via a friend's dependency tree; declare what you import, test in a clean environment ([packaging](../references/packaging.md)).
- **Silent behavior changes** — patch releases changing semantics; behavior changes are breaking ([Security Review](../reviews/security-review.md) not required; [Code Review](../reviews/code-review.md) is).
- **Type-surface drift** — annotations that lie (runtime behavior ≠ annotation); annotations are not validation [STANDARD].
- **Mutable shared defaults / module-level mutable state** ([Anti-Patterns](../catalogs/anti-patterns.md)) shared across consumers' processes.

## 7. Performance considerations

- Evidence-first ([I9](../core/python-invariants.md), [Performance](../references/performance.md)): a library has *consumers'* workloads — profile with a representative consumer scenario, not microbenchmarks of trivia.
- Known library-level costs to control by design: import time ([I3](../core/python-invariants.md)), per-call overhead in hot paths (batching APIs over one-call-per-item), and lazy loading of heavy optional features.
- IF a consumer reports "your library is slow" → demand the workload and a profile before restructuring ([Evidence Rules](../core/evidence-rules.md) §3); the dominant cost is often the consumer's usage pattern (N calls instead of one batch).
- Native acceleration (Numba/Cython/PyO3) imposes build/ABI/platform costs on consumers. Justify it by
  measured workload needs or a concrete interoperability/safety requirement; the candidate options in
  [Decision Model](../core/decision-model.md) §6 are not mandatory sequential steps.
- Public API design is itself a performance constraint: per-call overhead and eager data copying in convenience wrappers show up in consumer hot loops [HEURISTIC].

## 8. Testing strategy

- Follow [Testing](../references/testing.md):
  - **Public-API tests** import the package externally; these are the contract suite.
  - **Version coverage**: test the supported Python range, with full CI matrix depth based on the
    release contract and available automation ([packaging](../references/packaging.md)).
  - **Integration in a clean env**: install from built artifact (wheel) to catch undeclared dependencies.
  - **Property-based tests** for parsers/transformers/invariant-heavy logic ([Testing](../references/testing.md)).
- Type-check the public surface in CI (mypy or Pyright — checker differences exist [STANDARD/ECOSYSTEM], pick one and pin behavior).
- Snapshot/contract tests where output shapes are consumed programmatically.
- **Deprecation tests**: a deprecated path warns as documented and still works until the stated removal version.

## 9. Security concerns

- Proportional to blast radius — a library's bugs ship into consumers' processes ([Security](../references/security.md)):
  - Validate boundary inputs where misuse is plausible ([I1](../core/python-invariants.md)); never `eval`/pickle untrusted consumer data.
  - Dependency surface minimization ([I12](../core/python-invariants.md)); publish provenance (Trusted Publishing/attestations) improves supply chain but does not prove code safe.
  - No secrets in examples, tests, or docs ([I15](../core/python-invariants.md)); no surprising network/file access on import or call without docs.
- Vulnerability handling policy: how consumers report, how fast you patch, how it is announced.

## 10. Deployment/lifecycle concerns

- Release mechanics: build artifact reproducibly from `pyproject.toml`; test the built wheel, not just the checkout ([packaging](../references/packaging.md)).
- CHANGELOG policy: every user-visible change gets an entry, categorized (added/changed/removed/fixed/security).
- Version bump policy: what forces major/minor/patch; deprecation timeline with warnings.
- Support window: which versions stay patched after a new major; documented in README.

## 11. References for unresolved questions

Read only the section that answers an active question; this list is a menu, not a reading sequence.

- [references/packaging.md](../references/packaging.md) — `pyproject.toml`, build backends, dependency ranges vs pins, publishing.
- [references/typing.md](../references/typing.md) — public-surface annotation policy, Protocol/TypedDict choice, `py.typed`.
- [core/decision-model.md](../core/decision-model.md) §2, §5, §7 — contract design, records vs domain objects, package-vs-app split.
- [core/python-invariants.md](../core/python-invariants.md) — I1, I3, I12 dominate this domain.
- [references/testing.md](../references/testing.md) — matrix testing, contract tests, property-based tests.
- [references/security.md](../references/security.md) — dependency surface and safe API boundaries.
- [catalogs/anti-patterns.md](../catalogs/anti-patterns.md) — mutable defaults, import side effects, leaked internals.
- [reviews/dependency-review.md](../reviews/dependency-review.md) — before adding dependencies to the public contract.

## 12. Exit/readiness criteria

Apply the [mode-specific completion rules](../SKILL.md#task-modes) to the relevant criteria below.
Operational checks are release gates only when release readiness is in scope. Report actual evidence
and label proposed or unavailable checks.

### DESIGN completion

Specify the public contract, supported-environment policy, compatibility/deprecation choices,
dependency rationale, and proposed consumer-facing tests. Record assumptions and release risks.
A built wheel, published package, or executed CI matrix is not required for design completion.

### IMPLEMENT / release evidence

For a scoped implementation, check the changed public behavior and record actual results. Use the
full artifact and compatibility checks below when package/release readiness is in scope:

- [ ] Public API documented and tested through consumer-style imports; private naming and compatibility policy make the boundary clear (`__all__` where useful).
- [ ] Supported Python range defined; actual tested interpreters and type-check results recorded.
      Full matrix success is a release gate when required by the support contract, not an assumed fact.
- [ ] CHANGELOG policy written and followed; versioning definition of "breaking" stated; deprecation path demonstrated.
- [ ] Dependency constraints reflect tested compatibility rather than incidental pins; any exact pin has a concrete reason. A clean-environment install of the built artifact passes (no undeclared transitive deps).
- [ ] Import time cheap and side-effect-free ([I3](../core/python-invariants.md)); README example runs verbatim.
- [ ] Public exceptions defined and documented; logging is quiet-by-default and configurable.
- [ ] Release process reproducible: built wheel tested, CHANGELOG entry written, version bump policy applied.
- [ ] Security posture stated: input validation at API boundaries, vulnerability reporting path, no secrets in the package.
