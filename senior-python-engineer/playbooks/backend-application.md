# Backend Application

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

**Modes:** DESIGN, IMPLEMENT, REVIEW · **Concerns:** REFACTOR · **Domains:** BACKEND_APPLICATION
Procedure for full applications: domain logic, persistence, background work, and admin surfaces.
Governing rule: **one deployable until distribution earns its cost**; each layer must name the problem it solves
([Decision Model](../core/decision-model.md) §3, [I11](../core/python-invariants.md)).

## 1. Typical system shape

- For an application with several cohesive domain areas, start with **one deployable modular monolith** — modules named after those areas, each owning its data and exposing use-case functions. A smaller application can remain a few modules; shared infrastructure need not become a "kernel" layer.
- Layers only where they pay: IF use cases span multiple collaborators (persistence + external API + events) with transaction/permission boundaries → a use-case/service layer earns its keep. IF it is one store and CRUD → functions over the ORM are the architecture.
- Background work can share the application's code and use-case functions while running in a separate worker process or deployment for its own lifecycle ([workers-jobs.md](workers-jobs.md)). A separate service boundary needs independent scaling, fault, deployment, or ownership evidence.
- Admin/ops surfaces (CLI, admin UI, internal API) are thin adapters over the same use-case functions; never a parallel business-logic implementation.
- Error taxonomy: one domain-exception hierarchy (or error-result style) crossing module boundaries; adapters translate to their protocol (HTTP codes, exit codes, job failures).

## 2. Important constraints

- **State ownership** ([I4](../core/python-invariants.md)): every mutable collection, cache, and connection has one named owner; shared state without an owner is a defect.
- **Transaction boundary at the use case** ([I7](../core/python-invariants.md)): what commits or rolls back together is visible in use-case code; a Session is session-per-thread, an AsyncSession per-task, never shared across concurrent threads/tasks [FRAMEWORK].
- **Config ownership**: load and validate configuration at a known boundary; scattered import-time `os.environ` reads can make behavior depend on import order ([I3](../core/python-invariants.md)). Use one settings object only when it remains a clear fit.
- Persistence model: ORM vs raw SQL is conditional ([Decision Model](../core/decision-model.md) §4) — mixed use inside one system is normal [HEURISTIC].
- Choose the execution model per entrypoint and dependency path, per [Decision Model](../core/decision-model.md) §1. A sync CLI, async web handler, and process worker may coexist; make their resource and transaction boundaries explicit.

## 3. Recommended discovery questions

Ask only what changes a structural decision:
- Which use cases mutate shared state, and what must be atomic together? (Transaction boundaries, [I7](../core/python-invariants.md).)
- Who owns each piece of mutable state — request, task, process, external store? (Synchronization strategy, [I4](../core/python-invariants.md).)
- What runs in the background today, and what happens when the process dies mid-unit? ([workers-jobs.md](workers-jobs.md).)
- Which external systems are called, and are calls idempotent/retriable? ([I8](../core/python-invariants.md).)
- Is there more than one interface over the same logic (API + CLI + admin)? (Justifies use-case layer.)
- Team/module ownership map? (Module boundaries follow ownership when teams are separate.)
- Compliance/audit on data changes? (Event/audit logging at the use-case boundary.)
- Which use cases must survive partial failure (multi-store writes, external side effects)? (Compensation/outbox decisions, [I8](../core/python-invariants.md).)
- How is the app deployed and rolled back? (Migration and compat constraints, §10.)

## 4. Common architecture choices

- **Layering**: IF use cases span multiple collaborators → api/adapter → use-case → persistence, transaction at the use case. BUT IF single-store CRUD → keep handlers thin over ORM calls and grow a layer only when a second consumer appears ([I11](../core/python-invariants.md)).
- **Module boundaries**: IF domain areas have distinct data + vocabulary → one module per area with explicit public functions. BUT IF a boundary exists only because two nouns sound different → don't split; module boundaries should align with change and ownership, not taxonomy [HEURISTIC].
- **Hexagonal/ports-adapters**: IF infrastructure dependencies are volatile or genuinely dual-implemented (two cloud providers, swappable brokers) or a strong test policy demands fakes at stable boundaries → ports earn their cost. BUT IF the port has one implementation forever → plain function calls ([Decision Model](../core/decision-model.md) §3, [Anti-Patterns](../catalogs/anti-patterns.md)).
- **Session/transaction management**: explicit unit-of-work scope per use case ([I7](../core/python-invariants.md)); ORM Session never shared concurrently [FRAMEWORK]. PostgreSQL serialization failures: retry the whole transaction ([I8](../core/python-invariants.md)).
- **Direct call vs queue** per [Decision Model](../core/decision-model.md) §4: queue only for buffering, independent retries, or decoupled scheduling; otherwise a direct call has simpler failure semantics.
- **Events**: domain events for within-process decoupling/audit only when direct calls create real coupling problems; event buses across services = distribution decision ([Decision Model](../core/decision-model.md) §3).
- **Read vs write paths**: IF reporting/query shapes differ radically from transactional shapes → separate read queries (raw SQL/views) inside the same process; do not reach for CQRS as an architecture label (§5).

## 5. What not to overengineer

- Hexagonal architecture for a CRUD app; repository layers whose only implementation wraps the ORM it hides.
- God services: one `XxxService` class owning every use case until it is the new `utils.py` — split by use-case cohesion, not by one-class-per-table ceremony.
- DI containers for an object graph that is fixed at startup; plugin systems without a second consumer ([I11](../core/python-invariants.md)).
- Domain-driven-design ceremony (aggregate roots, specification objects) for what are plain transactional functions.
- Sagas, CQRS, and event sourcing need a named coordination or domain problem; one process and one database rarely justify them. A transactional outbox can still be useful in one codebase when a database commit and external message publish must be coordinated durably.
- Per-module micro-frameworks, metaclass registries, import-time wiring graphs ([I3](../core/python-invariants.md)).

## 6. Failure modes

Domain-relevant subset of [Failure Modes](../catalogs/failure-modes.md):
- **Hidden transactions** — commit buried in a helper; callers get partial writes or phantom commits ([I7](../core/python-invariants.md) violation; make the boundary visible).
- **Scattered configuration** — module A reads env at import, module B at call time; behavior depends on import order (centralize; [I3](../core/python-invariants.md)).
- **Import side effects** — DB connections, network calls, or large data loads at import time break tests, multiprocessing, and startup ([I3](../core/python-invariants.md)).
- **Session misuse** — Session/AsyncSession shared across threads/tasks; lazy-loading N+1 in loops ([Decision Model](../core/decision-model.md) §4; [persistence](../references/persistence.md)).
- **Dual write paths** — CLI and API implement the same rule differently; drift becomes data corruption.
- **Background work without ownership** — jobs that touch app state with no transaction/idempotency answer ([workers-jobs.md](workers-jobs.md)).
- **Cache as second database** — app-level cache with no owner/TTL becomes the de-facto source of truth ([Decision Model](../core/decision-model.md) §4).
- **Test-only behavior drift** — dev/CI use SQLite while prod runs PostgreSQL; engine semantics differ (isolation, constraints) and defects surface in production only [HEURISTIC].

## 7. Performance considerations

- For performance restructuring, profile a representative use case end to end when it exists
  ([I9](../core/python-invariants.md), [Evidence Rules](../core/evidence-rules.md) §3,
  [Performance](../references/performance.md)). Correctness or ownership fixes need their own evidence,
  not a performance profile.
- The dominant costs in backend apps are data access and external I/O: N+1 patterns, unbounded result loads, per-row writes instead of bulk, chatty external calls. Fix those before concurrency or native work ([Decision Model](../core/decision-model.md) §6).
- ORM vs raw SQL is a measured question: switch only with a query/round-trip profile or a concrete productivity defect ([Evidence Rules](../core/evidence-rules.md) §3).
- Caching requires defined key, TTL/invalidation, and stated cost-of-stale ([Decision Model](../core/decision-model.md) §4) — an app-level cache without an owner becomes a second, worse database.

## 8. Testing strategy

- Follow [Testing](../references/testing.md); the confidence targets here:
  - **Use-case logic**: unit tests with fakes at stable boundaries (external APIs), real logic for transactional rules.
  - **Persistence**: integration tests against the real DB engine for transactions, constraints, and migration behavior — mocked sessions prove nothing about commit semantics.
  - **Wiring**: one smoke test per entrypoint (web app boots, worker processes one job, CLI runs).
- Property-based tests for invariants-heavy domain rules ([Testing](../references/testing.md)); avoid mock-dominated suites that validate arrangements rather than behavior ([Anti-Patterns](../catalogs/anti-patterns.md)).
- Run the suite in CI as it runs locally; state commands and results ([Evidence Rules](../core/evidence-rules.md) §6).

## 9. Security concerns

- Proportional to risk ([Security](../references/security.md)): authorize each operation/resource where its context is available; shared use cases need a consistent policy across entrypoints. Validate input at trust boundaries ([I1](../core/python-invariants.md)); parameterize data access ([persistence](../references/persistence.md)).
- Secrets via config/secret boundary ([I15](../core/python-invariants.md)); admin surfaces are high-value targets — same authz discipline as public entrypoints.
- Unsafe deserialization (pickle of job payloads/artifacts) and subprocess use get explicit scrutiny ([Security](../references/security.md)); generated code crossing these boundaries is untrusted proposed change ([Code Review](../reviews/code-review.md)).

## 10. Deployment/lifecycle concerns

- State the process model for each entrypoint (web, worker, CLI) and measure capacity where load warrants it ([Deployment](../references/deployment.md)); graceful shutdown drains in-flight work and background jobs ([Reliability](../references/reliability.md), [workers-jobs.md](workers-jobs.md)).
- For rolling deployments where old and new code overlap, migrations must remain compatible with both versions; use expand → migrate → contract where the change requires it ([migration-plan](../templates/migration-plan.md)).
- Observability at use-case boundaries: structured logs with correlation IDs, error tracking, metrics per use case ([Observability](../references/observability.md)) — this is the substitute for "just read the code" once several entrypoints share logic.
- Rollback story per change: code rollback and data-migration rollback stated separately ([migration-plan](../templates/migration-plan.md)).
- IF the app runs on a container platform → probes and drain follow [production-service.md](production-service.md).

## 11. References for unresolved questions

Read only the section that answers an active question; this list is a menu, not a reading sequence.

- [core/decision-model.md](../core/decision-model.md) §2–§4 — layering, service abstraction, ORM/SQL, queue-vs-call frames.
- [core/python-invariants.md](../core/python-invariants.md) — I3, I4, I7 dominate this domain.
- [references/persistence.md](../references/persistence.md) — Session model, transaction scoping, query patterns.
- [references/architecture.md](../references/architecture.md) — module boundaries, monolith patterns, when layers pay.
- [references/testing.md](../references/testing.md) — unit/integration balance for use-case logic.
- [references/security.md](../references/security.md), [references/reliability.md](../references/reliability.md) — proportional risk and failure behavior.
- [workers-jobs.md](workers-jobs.md) — when background work is in scope.
- [catalogs/anti-patterns.md](../catalogs/anti-patterns.md) — god services, unjustified layers, hidden globals.
- [reviews/architecture-review.md](../reviews/architecture-review.md), [reviews/database-review.md](../reviews/database-review.md) — when structure or persistence changes.

## 12. Exit/readiness criteria

Apply the [mode-specific completion rules](../SKILL.md#task-modes) to the relevant criteria below.
Operational checks are release gates only when release readiness is in scope. Report actual evidence
and label proposed or unavailable checks.

Observable checklist:
- [ ] State-ownership map exists: each mutable state/cache/connection has a named owner and synchronization strategy ([I4](../core/python-invariants.md)).
- [ ] Transaction boundaries visible in use-case code; no Session sharing across threads/tasks ([I7](../core/python-invariants.md)).
- [ ] Configuration loaded and validated at an owned boundary; no harmful import-time side effects ([I3](../core/python-invariants.md)).
- [ ] Each added layer names the problem it solves; layers without a consumer removed ([I11](../core/python-invariants.md)).
- [ ] Dual entrypoints (API/CLI/worker) share use-case functions — no duplicated business rules.
- [ ] Persistence behavior verified by integration tests (transactions, constraints); suite results stated.
- [ ] Failure questions answered at each external boundary ([I14](../core/python-invariants.md)): retries idempotency-analyzed, shutdown behavior defined.
- [ ] Error taxonomy crosses module boundaries consistently; adapters translate, core does not raise protocol-specific errors.
- [ ] Rollback or recovery stated for material code and schema changes; test engine matches production semantics where those differences matter.
