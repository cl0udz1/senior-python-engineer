# Greenfield Project

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

**Modes:** DESIGN (BLUEPRINT), IMPLEMENT · **Concerns:** new-system design · **Domains:** any new system
Procedure for shaping a new Python system before and during its first implementation. Governing rule: the
simplest correct solution first; sophistication only for a named constraint ([Decision Model](../core/decision-model.md) §0).

## 1. Typical system shape

- Start with the **minimum set of components**: entrypoint, core logic, boundary adapters (I/O), config. Everything else waits for a trigger.
- IF the system fits one module with a `main()` and an `if __name__ == "__main__":` guard → ship one file.
- Possible growth path for a long-lived application — move only when a named trigger fires [HEURISTIC]:
  1. **One file** — one use case, one consumer, state confined to calls.
  2. **Package** (`src` layout when useful for distribution) — triggers: second entrypoint or consumer, mixed concerns, or tests that cannot import the logic cleanly.
  3. **Modular monolith** — triggers: several use cases over shared domain state, use cases spanning multiple collaborators, or team ownership boundaries.
- A long-lived multi-use-case application often fits a **modular monolith in one deployable** ([Decision Model](../core/decision-model.md) §3). A small CLI or library may never need that shape.
- Composition root: wire dependencies (DB session, clients, config) in one place at startup; modules receive what they need as parameters rather than importing globals ([Anti-Patterns](../catalogs/anti-patterns.md)).

## 2. Important constraints

- **Requirements are early and unstable** → favor reversibility [HEURISTIC]: pick the option cheapest to unwind, and record what would flip the choice.
- Separate what the system must do from the constraints that change its shape (latency, consistency,
  security, which part is expected to change next). An obligation nobody wrote down — failure behavior,
  audit, idempotency — is still a requirement when missing it would corrupt state or surprise a caller
  ([architecture.md](../references/architecture.md)). Do not turn requirement nouns into a class list.
- Defer or ADR the low-reversibility set: datastore, public API shape, service split, native-code boundary ([Evidence Rules](../core/evidence-rules.md) §7 → [Architecture Decision Record](../templates/architecture-decision-record.md)).
- Choose a supported Python version compatible with the target environment and dependencies; check
  [modern-python-baseline.md](../references/modern-python-baseline.md) before citing current versions.
  A pre-release may be appropriate for explicit compatibility testing, not an unstated production default.
- Team size and async experience constrain execution-model and typing choices more than domain fashion ([Decision Model](../core/decision-model.md) §1, §5).
- Deployment target (laptop, cron, container, serverless) constrains process model, config, and shutdown behavior; name it early ([Deployment](../references/deployment.md)).

## 3. Recommended discovery questions

Ask only what changes a shape decision; otherwise state the working assumption and proceed ([Evidence Rules](../core/evidence-rules.md) §8):
- Who runs this, and who consumes its output — one person, one team, external users? (Determines API-stability needs.)
- Expected load: roughly how many operations/day, and what data size at peak? (Determines whether a plain database call suffices.)
- What data must survive a crash, and does it have relations/transactions? (Determines store class — [Decision Model](../core/decision-model.md) §4.)
- Where do trust boundaries sit — which inputs come from users, files, networks, other services? (Determines validation boundary, [I1](../core/python-invariants.md).)
- What is the deployment target and who operates it? (Determines observability and lifecycle depth.)
- What must never happen? (Lost payment, leaked secret, duplicate side effect — drives failure questions, [I14](../core/python-invariants.md).)
- What already exists to reuse (internal libraries, auth, deployment platform)? ([I12](../core/python-invariants.md): the incumbent stack wins absent a gap.)
- What is the expected lifetime — a week of analysis, or years of service? (How much durability/maintainability the shape owes.)
- Which integrations already exist (auth provider, DB, queue, cloud SDK)? (Prefer the stack already in the org — [I12](../core/python-invariants.md).)

## 4. Common architecture choices

- One file, package, and modular monolith are available shapes, not mandatory stages; choose the smallest one that fits §1.
- IF several cohesive use cases share one deployable and team → consider a modular monolith with boundaries that clarify ownership. BUT IF independent deploy/scale/fault/ownership domains are real and named (not "someday") → consider services, with distributed-failure analysis and an [ADR](../templates/architecture-decision-record.md). A small script or package needs neither shape.
- IF the workload is one process, low concurrency, wait-bound → straightforward sync code ([Decision Model](../core/decision-model.md) §1). BUT IF many concurrent waits with async-native dependencies end to end → async/ASGI; the choice is whole-program, so make it before the dependency graph hardens.
- IF use-case code spans multiple collaborators with a transaction/permission boundary → name the transaction boundary at the use case ([I7](../core/python-invariants.md)). BUT IF it is CRUD over one store → plain functions over the ORM; no service layer yet.
- IF external data arrives (HTTP, file, queue, CLI args) → validate at the boundary and pass validated shapes inward ([I1](../core/python-invariants.md); [typing](../references/typing.md) for the tool choice: TypedDict/dataclass/Pydantic-style model).
- Consequential design decisions get: dominant constraint, chosen option, signals that would flip it,
  evidence, and reversibility ([Decision Model](../core/decision-model.md)).
- **Error model chosen once**: one exception hierarchy or error-result style at boundaries; silent `except Exception: pass` is banned from day one ([I13](../core/python-invariants.md)).
- **Logging chosen to match the run mode**: a service needs consistent structured context; a one-shot local script may need only clear stderr and exit status ([Observability](../references/observability.md)).

## 5. What not to overengineer

Complexity must pay rent ([I11](../core/python-invariants.md); [Anti-Patterns](../catalogs/anti-patterns.md)) — each of these needs a named problem *today*:
- Microservices for imagined scale; event buses where a direct call has simpler failure semantics; queues without a named buffering/decoupling need.
- DI containers and plugin systems with one implementation and one call site; factories-of-factories.
- Repository + service + DTO stacks "for later" over a simple ORM app with one consumer.
- Hexagonal/ports-and-adapters when the only boundary is conceptual.
- Grand-bang strict typing, custom frameworks, CQRS/event sourcing, hand-rolled ORMs, and premature async conversion.
- Building architecture to look senior is an explicit forbidden behavior ([SKILL.md](../SKILL.md#core-decisions)); if a reviewer cannot name the problem a layer solves, remove it.

## 6. Failure modes

Ask the relevant subset of [Failure Modes](../catalogs/failure-modes.md) at each boundary; for greenfield the recurring ones are:
- **Premature abstraction** locking in the wrong model while requirements are still moving (mitigate: reversibility-first, §2).
- **Unvalidated day-one boundaries** — the first "temporary" code path that skips [I1](../core/python-invariants.md) becomes the permanent one.
- **Un-answered failure questions at external boundaries** ([I14](../core/python-invariants.md): what if the DB is gone? the call times out? it runs twice?).
- **Scattered configuration** and import-time side effects ([I3](../core/python-invariants.md)) discovered only at deployment.
- **Hidden resource lifetimes** ([I2](../core/python-invariants.md)) — files/transactions closed by GC luck instead of context managers.

## 7. Performance considerations

- Evidence-first ([I9](../core/python-invariants.md), [Evidence Rules](../core/evidence-rules.md) §3): greenfield performance work is *not* optimization — it is (a) picking a plausible execution model for the stated load, and (b) keeping measurement reachable (representative workload runnable, timings loggable).
- IF load estimates are unknown → do not optimize; pick the simple model and record the assumption + the cheapest check to close it ([I9](../core/python-invariants.md) exception: cheapest reversible option, assumption recorded).
- Leave the seams where cost concentrates (DB access, external calls, hot loops) behind small functions so a later profile can attribute cost (Python/native/DB/wait) before any rewrite ([Performance](../references/performance.md)).
- For speed, start with workload and cost evidence before a native extension or Rust rewrite
  ([Decision Model](../core/decision-model.md) §6). A concrete safety or interoperability requirement
  can justify a native component independently of speed.
- IF a hot path is suspected → keep it behind a small, replaceable function boundary so the future fix is local [HEURISTIC].

## 8. Testing strategy

- Follow [Testing](../references/testing.md): confidence scales with risk, not with ceremony.
- For implementation, choose checks for the actual risks: core logic, integration behavior at used external boundaries, and entrypoint wiring. Combine checks when one exercises several risks; design-only work specifies this verification rather than running it.
- IF domain invariants are the risk (money, quotas, state machines) → property-based tests ([Hypothesis](../references/testing.md)) and test-first for those rules.
- Skip mocking what does not exist yet; do not build a test architecture grander than the system it tests.
- IF the shape is a CLI/script → test the pure core directly; assert exit codes for the boundary cases.

## 9. Security concerns

- Proportional to risk, but the trust-boundary map is non-negotiable day one: which inputs are external ([I1](../core/python-invariants.md)), where secrets enter ([I15](../core/python-invariants.md) — config/secret boundary, never code/logs/diffs).
- IF any auth, secrets, subprocess, serialization, SQL, or filesystem/network boundary exists → that code is reviewed as **untrusted proposed change**, including agent-generated code ([Security](../references/security.md), [Code Review](../reviews/code-review.md)).
- Never pickle untrusted data; prefer data formats with schema validation ([Security](../references/security.md)).
- Dependency additions state their value case ([I12](../core/python-invariants.md)); PyPI attestations improve provenance but do not prove code safe.

## 10. Deployment/lifecycle concerns

- Name the deployment target in the blueprint ([Deployment](../references/deployment.md)); it decides process model, worker counts, and config style.
- Config/secret boundary centralized from the start (env/secret manager → one validated settings object); scattered `os.environ` reads are the seed of config drift.
- IF long-running → define graceful shutdown and what must finish before exit ([Reliability](../references/reliability.md)); IF batch/cron → define overlap behavior and failure alerting.
- IF data survives the process → back up/restore story named before first real data lands; a store with no recovery path is a future incident.
- The new-system design prompts are in [templates/blueprint.md](../templates/blueprint.md) — choose the relevant sections and scale depth to size and risk; a one-file utility gets a few sentences.

## 11. References for unresolved questions

Read only the section that answers an active question; this list is a menu, not a reading sequence.

- [core/decision-model.md](../core/decision-model.md) — execution model, architecture, data frames used above (§0, §1, §3, §4).
- [core/python-invariants.md](../core/python-invariants.md) — I1–I16 guardrails the design must satisfy.
- [core/evidence-rules.md](../core/evidence-rules.md) — what may be asserted, what must be measured, ADR triggers.
- [templates/blueprint.md](../templates/blueprint.md) — design prompts to select and scale to risk, not a requirement to fill every section.
- [templates/architecture-decision-record.md](../templates/architecture-decision-record.md) — record low-reversibility decisions.
- [references/architecture.md](../references/architecture.md) — module/monolith/distribution patterns in depth.
- [references/typing.md](../references/typing.md) — boundary validation tooling (TypedDict vs dataclass vs runtime-validation models).
- [references/testing.md](../references/testing.md), [references/security.md](../references/security.md), [references/deployment.md](../references/deployment.md) — load only the sections the shape needs.
- [catalogs/anti-patterns.md](../catalogs/anti-patterns.md) — the overengineering set to avoid in §5.
- Consult a domain playbook (e.g. [web-api.md](web-api.md), [cli-automation.md](cli-automation.md)) only if an unresolved domain decision needs more detail; do not reread an equivalent procedure.

## 12. Exit/readiness criteria

Apply the [mode-specific completion rules](../SKILL.md#task-modes) to the relevant criteria below.
Operational checks are release gates only when release readiness is in scope. Report actual evidence
and label proposed or unavailable checks.

### DESIGN / BLUEPRINT completion

- [ ] State the dominant constraint and the smallest correct shape, with named growth triggers.
- [ ] Specify relevant trust boundaries, state/resource owners, transaction boundaries, and failure behavior.
- [ ] Explain consequential decisions, assumptions, trade-offs, and evidence that would change the answer.
- [ ] Identify unresolved risks and the cheapest proposed check; record low-reversibility decisions when useful.
- [ ] Specify relevant implementation acceptance checks. A running skeleton, installed dependencies, and
      executed CI are not required to finish a design request.
- [ ] Use the applicable sections of [Blueprint](../templates/blueprint.md); omit irrelevant sections without filler.

### IMPLEMENT completion

- [ ] Deliver the requested working slice with its entrypoint, configuration, and ownership boundaries.
- [ ] Run relevant checks for behavior, failure paths, and wiring; report exact results and unavailable checks.
- [ ] Review trust-boundary code and state material residual risks or deployment requirements.
- [ ] Require CI or release evidence only when the repository gate or requested delivery scope calls for it;
      do not imply that local verification proves production readiness.
