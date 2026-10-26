# Web API

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

**Modes:** DESIGN, IMPLEMENT, REVIEW · **Concerns:** OPTIMIZE · **Domains:** WEB_API
Procedure for HTTP APIs. Governing rule: framework choice follows constraints, not fashion
([Decision Model](../core/decision-model.md) §1, §3); framework conventions are local ([I10](../core/python-invariants.md)).

## 1. Typical system shape

- Minimal layering that the domain forces: **routing → validation at the boundary → use-case logic → persistence**. Authenticate at a known edge; authorize each resource or operation where its context is available, in the handler or a shared use case.
- IF the app is mostly CRUD over one store → route handlers + ORM + validation models is a complete architecture; nothing else is owed.
- IF use cases span multiple collaborators with transaction/permission boundaries → extract a service/use-case layer, with the transaction boundary visible there ([I7](../core/python-invariants.md)).
- State: request-scoped by default; long-lived state (pools, caches) owned explicitly at app startup/shutdown ([I2](../core/python-invariants.md), [I4](../core/python-invariants.md)).
- Response contracts: bound list sizes where they can grow; use pagination when clients need to traverse large results. Define a stable error shape and a versioning/deprecation policy when clients rely on them.

## 2. Important constraints

- **Latency and concurrency requirements** dominate the execution model — measure existing traffic or
  state a credible estimate for a new API, then validate it ([Decision Model](../core/decision-model.md) §1).
- **Validation boundary** ([I1](../core/python-invariants.md)): consumed body/query/path/header values are validated and normalized to the contract before use-case code sees them. Annotations are not validation [STANDARD].
- **Authn/authz**: authentication at the edge; authorization at the resource/use-case level. Never rely on "the route is unlisted" for security.
- Sync vs async follows the workload and dependency path: async fits high concurrent waits when I/O is async-capable or blocking calls are explicitly offloaded with bounded capacity ([Decision Model](../core/decision-model.md) §1). A blocking call directly on the loop stalls other tasks ([I5](../core/python-invariants.md)).
- Bound potentially slow outbound operations (DB, HTTP, cache) with call timeouts or a deadline that reaches the I/O; otherwise request latency can grow beyond the intended budget.
- Operations with side effects that may be retried by clients/proxies need an idempotency answer ([I8](../core/python-invariants.md)). HTTP method semantics alone do not prove an implementation is safe to repeat; payment-style POST endpoints commonly need idempotency keys.

## 3. Recommended discovery questions

Ask only what changes an architecture choice:
- Latency/throughput targets and peak concurrency? (Sync vs async, worker topology.)
- What is the request mix — read-heavy CRUD, or computation/aggregation per request? (Where the CPU goes.)
- Who are the callers — browsers, server-to-server, public internet? (Auth model, abuse surface, error verbosity.)
- What data stores and external services sit behind the API? (Async-driver availability, transaction shape.)
- Long-lived connections needed (WebSocket/SSE/streaming)? (ASGI-specific features.)
- Is there an existing framework/repo convention? ([Existing Codebase](existing-codebase.md) rules apply.)
- Compliance/audit requirements on data access? (Logging, authorization granularity.)
- Are there existing clients with fixed contracts? (Versioning/deprecation policy.)
- Payload sizes and list sizes at peak? (Pagination, body limits, serialization cost.)

## 4. Common architecture choices

- **Framework** ([web-frameworks.md](../references/web-frameworks.md)): IF an ASGI-first API with async concurrency, streaming, or OpenAPI-from-code is the need → FastAPI/Starlette/Litestar [FRAMEWORK]. BUT IF a large integrated application stack (admin, ORM, auth, templating) dominates → Django [FRAMEWORK]. BUT IF a small WSGI service with minimal composition fits the load → Flask [FRAMEWORK]. The framework is a dependency choice, not an architecture.
- **Sync vs async** per [Decision Model](../core/decision-model.md) §1: IF most handler time is waiting on async-capable I/O at high concurrency → async. BUT IF handlers are CPU-bound or low-concurrency → a sync path may be simpler; synchronous drivers may run in a framework threadpool or bounded offload where justified. Do not convert to async on an unsupported speed claim; use measured or projected concurrency needs ([Evidence Rules](../core/evidence-rules.md) §3).
- **Layering**: IF one consumer and CRUD → handlers over ORM directly. BUT IF multiple interfaces (HTTP + CLI + worker) share use cases, or use-case logic spans collaborators → service layer where the transaction boundary lives ([I7](../core/python-invariants.md); [Decision Model](../core/decision-model.md) §3).
- **Validation tooling** ([typing](../references/typing.md)): framework-native schema models (runtime-validating) at the boundary; typed internal records inward. Static types alone never validate [STANDARD].
- **Error semantics**: one defined mapping — domain errors → status codes + stable error body; internal details never leak to clients (§6).
- **Pagination & bulk**: IF lists can grow large → enforce a result bound and offer pagination where callers need the full collection; unbounded JSON arrays can become latency and memory failures ([Failure Modes](../catalogs/failure-modes.md): unbounded growth).

## 5. What not to overengineer

- Repository + service + DTO layers over a simple one-consumer ORM app — indirection without isolation ([I11](../core/python-invariants.md), [Anti-Patterns](../catalogs/anti-patterns.md)).
- Premature async conversion of a working sync app: it is a whole-program migration ([Evidence Rules](../core/evidence-rules.md) §4) requiring a named concurrency problem.
- GraphQL/gRPC/event buses because they are sophisticated; API gateways and service meshes in front of one service.
- Custom middleware frameworks, hand-rolled DI containers, per-endpoint micro-frameworks, response-envelope machinery no client consumes.
- Microservice split of "the API" from "the workers" without independent deploy/scale/ownership evidence ([Decision Model](../core/decision-model.md) §3).

## 6. Failure modes

Domain-relevant subset of [Failure Modes](../catalogs/failure-modes.md):
- **N+1 query patterns** from lazy relationship access in handlers/serializers ([Decision Model](../core/decision-model.md) §4; inspect the SQL, use eager/select-in loading or joins).
- **Blocking call on the event loop** ([I5](../core/python-invariants.md)) — a sync driver or CPU-heavy work invoked directly in an async handler stalls other tasks on that loop.
- **Missing timeouts** on outbound calls → thread/worker exhaustion cascading into full outage.
- **Validation gaps** ([I1](../core/python-invariants.md)) — partially validated payloads reaching state changes; mass-assignment-style over-posting.
- **Error leakage** — stack traces, SQL, internal hostnames in 5xx bodies or logs exposed to clients.
- **Unbounded concurrency** (thread-per-request, unbounded task spawn) without backpressure ([I6](../core/python-invariants.md)); connection-pool sized for a different concurrency than the server runs ([Deployment](../references/deployment.md)).

## 7. Performance considerations

- Evidence-first ([I9](../core/python-invariants.md), [Evidence Rules](../core/evidence-rules.md) §3, [Performance](../references/performance.md)): define the workload (request mix, payload sizes, concurrency) → measure p50/p95/p99 → attribute cost (DB vs serialization vs external calls vs Python CPU) → fix the dominant term.
- The dominant API costs are usually data access (N+1, unbounded result sets, missing pagination) and external-call latency — fix those before touching the runtime ([Decision Model](../core/decision-model.md) §6).
- Worker/process counts and pool sizes are measured against CPU, memory, and latency targets — never copied from a formula [ECOSYSTEM] ([Deployment](../references/deployment.md)).
- Caching only with defined key, TTL/invalidation, and a stated cost-of-stale ([Decision Model](../core/decision-model.md) §4).
- Serialization/deserialization of large payloads is a real cost center at high RPS; measure it before blaming the framework [HEURISTIC].
- IF a "Python/FastAPI is slow" claim appears → profile the actual request path first; the interpreter is frequently not the dominant term ([Evidence Rules](../core/evidence-rules.md) §3).

## 8. Testing strategy

- Follow [Testing](../references/testing.md); the confidence targets here:
  - **Validation boundary**: rejected/accepted payload cases per endpoint contract ([I1](../core/python-invariants.md)).
  - **Authz**: permission matrix per role/resource — denial paths tested, not just happy paths.
  - **Use-case logic**: unit tests over service layer where it exists; handler tests over the framework test client otherwise.
  - **Persistence contract**: at least integration tests against a real store for query patterns and transactions (mocked DB proves nothing about N+1 or isolation).
- Contract tests if external consumers depend on the schema; migration tests if the DB schema moves ([Testing Review](../reviews/testing-review.md)).

## 9. Security concerns

- Proportional to exposure: a public API gets full treatment ([Security](../references/security.md), [Security Review](../reviews/security-review.md)):
  - Authenticate at the boundary; authorize each resource/operation where its identity and ownership context is available (IDOR class bugs live here).
  - Input validation ([I1](../core/python-invariants.md)); parameterized SQL only ([persistence](../references/persistence.md)); no `eval`/unsafe deserialization of client data.
  - Secrets in config/secret boundary, never in code/logs/error bodies ([I15](../core/python-invariants.md)).
  - Rate limiting/abuse controls where the caller is untrusted; CORS/CSRF per the browser-caller case.
- Generated endpoint code crossing these boundaries is untrusted proposed change — review before calling done ([Code Review](../reviews/code-review.md)).

## 10. Deployment/lifecycle concerns

- Process model stated: workers per container, sync/async server choice, and how they were measured ([Deployment](../references/deployment.md)).
- Graceful shutdown: stop accepting traffic, finish in-flight requests within a deadline, close pools ([Reliability](../references/reliability.md); [I2](../core/python-invariants.md)).
- Readiness ≠ liveness ([Deployment](../references/deployment.md)): readiness removes the instance from traffic (e.g. pool warmed, migrations done); liveness restarts it — aggressive liveness under overload causes cascading failure.
- Health endpoints reflect real dependency state at a coarse level; observability: request logs with correlation IDs, latency/error metrics per route ([Observability](../references/observability.md)).

## 11. References for unresolved questions

Read only the section that answers an active question; this list is a menu, not a reading sequence.

- [references/web-frameworks.md](../references/web-frameworks.md) — framework lifecycle, sync/async behavior, dependency models ([FRAMEWORK] rules stay local).
- [core/decision-model.md](../core/decision-model.md) §1 — sync vs async evidence requirements.
- [references/typing.md](../references/typing.md) — boundary validation vs static annotations.
- [references/persistence.md](../references/persistence.md) — session/transaction ownership, N+1 control ([I7](../core/python-invariants.md)).
- [references/security.md](../references/security.md), [references/testing.md](../references/testing.md) — risk-proportional depth.
- [references/asyncio-concurrency.md](../references/asyncio-concurrency.md) — only if async is chosen (task structure, cancellation).
- [references/deployment.md](../references/deployment.md), [references/reliability.md](../references/reliability.md), [references/observability.md](../references/observability.md) — running it for real.
- [reviews/async-review.md](../reviews/async-review.md), [reviews/database-review.md](../reviews/database-review.md) — when the change touches those areas.

## 12. Exit/readiness criteria

Apply the [mode-specific completion rules](../SKILL.md#task-modes) to the relevant criteria below.
Operational checks are release gates only when release readiness is in scope. Report actual evidence
and label proposed or unavailable checks.

Observable checklist:
- [ ] Request validation is explicit per endpoint at the boundary; downstream code consumes validated shapes only ([I1](../core/python-invariants.md)).
- [ ] Error semantics defined: domain-error → status/body mapping; no internal detail in client-visible errors.
- [ ] Authn/authz placement stated; permission denials tested.
- [ ] Execution model chosen with evidence (concurrency requirement + dependency audit) or explicitly deferred ([Evidence Rules](../core/evidence-rules.md) §3).
- [ ] Potentially slow outbound calls have effective time bounds and defined failure behavior; retries are idempotency-analyzed ([I8](../core/python-invariants.md)).
- [ ] Load path measured or a capacity estimate recorded: p95 target vs measured, pool/worker counts justified ([Deployment](../references/deployment.md)).
- [ ] Query patterns inspected for N+1 on the hot path; shutdown/drain behavior defined.
- [ ] List sizes bounded and pagination available where needed; body/timeout limits stated; API versioning/deprecation policy recorded when clients depend on it.
- [ ] Observability minimum: per-route latency/error metrics and correlated request logs ([Observability](../references/observability.md)).
