# Architecture

## Contents

- [Module and package structure](#module-and-package-structure)
- [When each architecture style is justified](#when-each-architecture-style-is-justified)
- [Composition vs inheritance](#composition-vs-inheritance)
- [Change, cohesion, and patterns HEURISTIC](#change-cohesion-and-patterns-heuristic)
- [Protocol vs ABC](#protocol-vs-abc)
- [Plugin boundaries](#plugin-boundaries)
- [Repository / service layers: the rent rule](#repository--service-layers-the-rent-rule)
- [Dependency injection: restraint](#dependency-injection-restraint)
- [Import-time effects and application initialization](#import-time-effects-and-application-initialization)
- [Ownership of state and resources](#ownership-of-state-and-resources)
- [Domain and framework leakage](#domain-and-framework-leakage)
- [Review questions for architecture](#review-questions-for-architecture)

Operational reference for structuring Python systems. Decision criteria: [Decision Model §3](../core/decision-model.md);
the governing principle is [Engineering Principles §1](../core/engineering-principles.md) — complexity
must pay rent (also invariant I11). Version-sensitive facts live only in
[modern-python-baseline.md](modern-python-baseline.md). Invariants I1–I16 in
[python-invariants.md](../core/python-invariants.md).

## Module and package structure

- **src layout** is often useful for distributed packages ([packaging.md](packaging.md)): `src/<package>/` prevents
  accidentally importing the working directory instead of the installed package. Flat layout is
  acceptable for internal apps where the repo root import is understood and test discipline is good
  [HEURISTIC].
- When using layers, package boundaries follow **dependency direction**: lower layers (domain, shared
  contracts) should not depend on upper layers (web handlers, job runners). If two modules import each
  other, inspect the cycle and its effect on initialization ([language-semantics.md](language-semantics.md));
  a local import can be a deliberate solution when the dependency itself is sound.
- Sizing heuristic [HEURISTIC]: a module is the right size when its name describes one concept and its
  imports describe its dependencies honestly. Split when a file has multiple unrelated reasons to
  change; merge when "managers" and "utils" have no single owner. `utils.py`/`helpers.py` are naming
  debts — rename to what they do.
- Top-level structure that scales down as well as up: `domain/` (pure business objects/rules),
  `services/` or use-case functions, `adapters/` (DB, APIs, filesystems), `entrypoints/` (CLI, web,
  workers). A three-file script needs none of these folders — structure is proportional to size
  ([Decision Model §3](../core/decision-model.md)).

## When each architecture style is justified

| Style | Justified when (named conditions) | Not justified when | Complexity it pays for |
|---|---|---|---|
| Layered (handler → service → data) | Several entrypoints share use-case logic | One entrypoint, few use-cases | Reuse of use-case logic |
| Modular monolith | Multiple domains, one deployment is enough | Single domain or very small system | Internal boundaries without distributed cost |
| Hexagonal / ports & adapters | Infrastructure is unstable or must be swappable (two clouds, fake payment gateway in prod tests) | One stable stack, one deployment | Test/replace seams |
| Event-driven (in-process bus) | Multiple independent reactions to one fact, proven decoupling need | Synchronous flow would do | Fan-out decoupling |
| Workers + queues | Work needs buffering, independent retries, decoupled scheduling | A direct call preserves simpler failure semantics | Backpressure + retry domains ([reliability.md](reliability.md)) |
| Microservices | Independent ownership, deployment cadence, scaling, or fault domains are **real** | Boundaries are conceptual or political | Independent deploy/scale/fail |

- Banned slogan: "microservices scale better." For one team and one deployment need, a modular monolith
  often avoids premature distribution; converting a module-boundary problem into a distributed-systems problem adds
  network failure modes, serialization, and ops load without the payoff
  ([failure-modes.md](../catalogs/failure-modes.md)).
- Event buses and CQRS are the same rule: each names a scaling/ownership problem it solves. If you
  cannot name it in one sentence, don't build it.

## Composition vs inheritance

- Use inheritance when there is a genuine substitutable subtype: the subtype must accept at least what
  the base accepts and deliver at least what the base promises. Subclassing `list` or `dict` and then
  rejecting ordinary item operations fails that test; hold the collection and expose the operations that
  keep its invariant. In contract terms: do not strengthen preconditions or weaken postconditions;
  preserve the base type's relevant invariants and history constraints. Accepting additional inputs is
  compatible if the promised behavior still holds. Source: [Liskov and Wing, behavioral subtyping](https://www.cs.cmu.edu/~wing/publications/LiskovWing94.pdf).
  Use **composition** when the goal is reuse [HEURISTIC] — delegate to a held object instead of
  subclassing for code.
- Cooperative multiple inheritance (`super()` chains, C3 MRO) is deterministic but fragile at depth
  ([language-semantics.md](language-semantics.md)); keep hierarchies shallow, mixins single-purpose.
  Framework base classes ([FRAMEWORK] — Django views, SQLAlchemy declarative bases) are that framework's
  local convention (I10), not a license for deep hierarchies elsewhere.

## Change, cohesion, and patterns [HEURISTIC]

Decision procedure for [Decision Model §2](../core/decision-model.md). A green test run does not show
that the next change stays in one place.

### Where a change should land

- A caller that wants an outcome should not know the collaborator's steps. If changing how the work is
  done forces edits in those callers, the procedure leaked. Put the steps behind the outcome.
- Do not hide a step that callers must vary. Pass that step as a function or a small object. A new
  class hierarchy waits until two real variants are painful in the simpler shape.
- A caller that walks another object's internals (`order.customer.address.normalize()`) changes whenever
  those internals do. That is a leak when the walk is not the caller's job. It is fine when the path is
  the public model the caller is supposed to read.
- Encapsulate a change you can already name. Do not encapsulate "someday."
- Build the smallest slice that meets the current requirements, then change it. If the next real variant
  does not fit the axis you chose, collapse that axis. Do not add another subclass to save it.

### Cohesion and duplication

- A class earns its place when it owns state and the operations that keep that state valid. A module of
  functions is enough when there is no state to protect. One responsibility is not one method, and it
  is not one class per noun in a requirement.
- Split a type when two reasons to change already come from different callers. Leave it together when
  the split would only move the same change across more files.
- Extract a duplicate when the same rule must stay true in more than one place: a fix in one copy is
  wrong if the other copy keeps the old rule. Shared use-cases across entrypoints are this case
  ([anti-patterns](../catalogs/anti-patterns.md)).
- Leave the copies when they will change for different reasons, or the shared text is a few lines with
  no rule. A base class whose only commonality is its name costs more than the duplication.

### Surprises, storage, and state

- Public behavior matches its name and the units callers already use. A calendar month that is silently
  zero-based, while day and year are calendar numbers, is a defect even when a test locks in the
  surprise. `datetime.date` months are 1–12 [STANDARD]; a custom date type should not invent a second
  convention without saying so in the constructor's contract.
- An operation whose name sounds cheap but scans a growing collection on every call will surprise a
  caller who put it in a loop. Name that cost or measure it ([performance.md](performance.md)). Hiding
  it behind a prettier method is not a design improvement.
- A leading underscore means "use the operation, not the storage." It is a convention, not access
  control [LANGUAGE]. A property earns its place when a write must keep an invariant or a read must
  hide a stored representation. A getter and setter that only assign are noise.
- Name the modes and the legal transitions when the next action depends on mode and an illegal
  combination is easy to represent. An enum plus `apply(state, event)` is enough while each mode is a
  few branches. A class per state pays rent when the behaviors or the collaborators actually differ.

### When a pattern earns rent

- Use a pattern for a problem you can point at in the current code: a stable sequence with one varying
  step; whole algorithms that must be swapped; an external API the caller should not navigate; several
  independent reactions to one fact; illegal transitions that keep being patched in conditionals.
- In Python that shape is usually a function, a callable, a module, or a `Protocol`. A factory function
  is justified when construction varies and callers must not name the concrete type. `Thing(...)` does
  not need a factory. A process-wide object belongs at the composition root, not behind `get_instance()`.
- An abstract factory or a class per state is not the first design. If removing the extra types leaves
  the behavior and the change locality intact, they were ceremony (I11).

## Protocol vs ABC

- `Protocol` (structural): fits by shape; ideal at library boundaries where implementations aren't
  controlled ([typing.md](typing.md)). `ABC` (nominal): shared implementation plus an explicit base
  the subclasses must be. Both beat inventing "interface classes" without methods.
- Decision detail in [Decision Model §2](../core/decision-model.md). Default: plain functions and
  parameters first; introduce a protocol only when two+ implementations already exist or a boundary
  needs a shape contract now.

## Plugin boundaries

- A plugin system is justified by a named extension need: third-party extensions, per-customer
  integrations, independently deployed extensions. Costs: a stable API contract, discovery/registration
  mechanism, versioning, and a security review of loaded code ([security.md](security.md) — dynamic
  import is code execution).
- Keep the plugin API small and semantic-versioned ([packaging.md](packaging.md)); use entry points or
  explicit registration ([language-semantics.md](language-semantics.md) on import effects). A registry
  populated at import is acceptable only when registration is cheap and side-effect-controlled (I3).

## Repository / service layers: the rent rule

- A repository layer is justified when: persistence must be swapped (real second implementation
  planned/contracted), tests must substitute persistence wholesale at a stable seam, or domain logic is
  genuinely persistence-agnostic and worth that purity. It is **not** "best practice" (banned slogan:
  "repositories are best practice") — wrapping a clean ORM/API in an interface with one implementation
  is indirection without isolation (I11).
- A service layer is justified when multiple entrypoints (web + CLI + worker) must share transaction
  boundaries and use-case logic; it is where transaction scope becomes visible (I7) and where the unit
  of work is named. One entrypoint with thin handlers may not need it.
- Evidence test: "removing this layer would create this concrete problem: ___." If the blank is empty,
  remove the layer.

## Dependency injection: restraint

- Plain parameters and constructor injection cover nearly everything. A DI **container** earns its
  place only when: object graphs are large and repetitive to assemble, lifecycle scopes (per-request,
  per-tenant) are managed centrally, or plugin composition is dynamic. Python's module system plus
  factories is a fine "container" ([Decision Model §2](../core/decision-model.md)).
- Anti-pattern: framework-global service locators (`get_service()` hidden inside functions) — hidden
  dependencies that can't be seen from signatures. Prefer explicit parameters so the signature states
  the dependency (and [typing.md](typing.md) can check it).

## Import-time effects and application initialization

- Import is executable initialization (I3). Architecture consequence: the **composition root**
  (app factory / explicit bootstrap function) is where connections, pools, and registries are created —
  not module top levels. This keeps tests, multiprocessing workers, and tooling from opening connections
  just by importing ([deployment.md](deployment.md) for worker boot behavior).
- Application factory pattern (create the app/configured graph per process) beats import-time singletons
  wherever more than one configuration must coexist (tests, multiple entrypoints).

## Ownership of state and resources

- Every piece of mutable state and every resource has a clear owner or coordinated access policy and a
  documented lifetime ([Engineering Principles §4](../core/engineering-principles.md), I4/I2). Architecture diagrams should
  make ownership legible: who opens the DB session (I7), who owns the queue consumer, who closes the
  file, what happens on shutdown ([reliability.md](reliability.md)).
- Shared mutable global state is an architecture smell regardless of how the modules are arranged; fix
  it with explicit ownership, not more layers.

## Domain and framework leakage

- Framework objects (Django `HttpRequest`, FastAPI `Request`, SQLAlchemy `Session`) belong to adapter
  layers; domain code that takes them is coupled to that framework forever (I10). The cheap test: can
  the domain function run in a unit test with no framework imported?
- The reverse leak matters too: don't abstract a framework out of existence ("universal ORM wrapper")
  until there is a second real framework to support — that's complexity without rent (I11).

## Review questions for architecture

- What concrete problem does each layer solve? What would removing it break?
- Is dependency direction acyclic and downhill (entrypoints → services → domain)?
- Where is transaction scope visible (I7)? Where is state owned (I4)?
- Does any framework convention leak across its boundary (I10)?
- Does structure scale *down*? (A small feature should stay a small change.)
