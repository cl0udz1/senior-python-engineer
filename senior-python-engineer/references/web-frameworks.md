# Web Frameworks

## Contents

- [ASGI vs WSGI STANDARD](#asgi-vs-wsgi-standard)
- [FastAPI / Starlette FRAMEWORK](#fastapi--starlette-framework)
- [Litestar FRAMEWORK](#litestar-framework)
- [Django FRAMEWORK](#django-framework)
- [Flask FRAMEWORK](#flask-framework)
- [Choosing by constraint (not fashion)](#choosing-by-constraint-not-fashion)
- [Request lifecycle concerns](#request-lifecycle-concerns)
- [Background tasks vs real queues](#background-tasks-vs-real-queues)
- [Streaming, WebSockets, SSE](#streaming-websockets-sse)
- [Serving stack](#serving-stack)

Operational reference for Python web frameworks and server interfaces. Framework claims are
[FRAMEWORK]-tagged and local to that framework (I10); ASGI/WSGI are [STANDARD]. Version-sensitive facts
live only in [modern-python-baseline.md](modern-python-baseline.md). Cross-refs:
[web-api playbook](../playbooks/web-api.md), [deployment.md](deployment.md), [reliability.md](reliability.md).

## ASGI vs WSGI [STANDARD]

- **WSGI**: synchronous request→response interface, one request per worker thread/process at a time.
  Mature, simple mental model, huge deployment history.
- **ASGI**: async interface supporting long-lived connections (WebSockets, SSE, HTTP/2 streams) and
  high concurrent wait-bound I/O in one process. Adoption is now standard practice [ECOSYSTEM], but
  ASGI is not automatically faster — it's a concurrency model, not a speed dial
  ([asyncio-concurrency.md](asyncio-concurrency.md)).
- Choose by constraint: do you need long-lived connections or massive concurrent waiting (→ ASGI)? Or
  is a simple synchronous request model enough with a mature WSGI stack (→ WSGI)? A WSGI app behind
  modern servers and containers is a fine, boring system.

## FastAPI / Starlette [FRAMEWORK]

- ASGI-first. Starlette provides the ASGI toolkit (routing, middleware, WebSockets); FastAPI adds
  dependency injection, request validation, and OpenAPI generation on top.
- The **dependency model** is the central design surface: dependencies declare per-request (or scoped)
  resources — DB sessions, auth context, clients. Requests declare what they need; the graph is visible
  in signatures.
- **Truly-async deps vs blocking deps** (the common production defect):
  - `async def` dependencies/handlers must not block the loop (I5): a synchronous DB driver, sync HTTP
    client, or `time.sleep` inside `async def` stalls every task on the loop.
  - IF the dependency is blocking: use an async-native driver, declare a sync endpoint or dependency
    so FastAPI runs that code in its threadpool, or offload the blocking call explicitly with bounded
    capacity [FRAMEWORK]. Calling a sync driver directly on the event loop is the defect.
  - Threadpool offload has limits: it bounds concurrency and still needs a session-per-request model
    (I7, [persistence.md](persistence.md)).
- Validation boundary (I1): Pydantic models at request/response edges are the runtime validation layer;
  annotations alone do not validate ([typing.md](typing.md)). Keep validated shapes flowing inward.

## Litestar [FRAMEWORK]

- ASGI-first framework with a similar async-first posture, its own DI/serialization layer and schema
  generation; datastores/DTO layers and controller-style organization differ from FastAPI's router/
  dependency style [FRAMEWORK].
- Choosing between it and FastAPI is a fit question (existing team experience, DI style, ORM
  integration, schema tooling), not a quality ranking. Repository evidence wins: never migrate
  FastAPI→Litestar (or reverse) without a named problem ([existing-codebase playbook](../playbooks/existing-codebase.md)).

## Django [FRAMEWORK]

- Batteries-included: ORM, migrations, admin, auth, templating, forms, email — an integrated
  application stack, not just a request router. Choose when the app needs that stack out of the box
  ([web-api playbook](../playbooks/web-api.md) has the decision table).
- Sync/async caveats: Django supports async views and async ORM query/model methods, while transaction
  handling still requires a synchronous section bridged with `sync_to_async` in current Django
  documentation [FRAMEWORK]. Calling a synchronous ORM operation directly from async code is unsafe
  (and Django may raise `SynchronousOnlyOperation`); inspect the actual dependency path (I5).
- Deployment model: Django supports WSGI with process and/or thread workers and ASGI for async
  request handling and long-lived connections. Capacity advice follows the configured serving stack,
  not a universal process-per-request assumption ([deployment.md](deployment.md)).

## Flask [FRAMEWORK]

- Small, WSGI-oriented, unopinionated: routing + request/response + extension ecosystem (ORM choice,
  auth, etc. are third-party). Choose for small services, sync simplicity, or existing Flask estates.
- **Async in Flask** [FRAMEWORK]: an `async def` view is tied to a worker for its duration — it does
  not give you an event loop multiplexing thousands of connections. Async views there are for
  compatibility with async libraries at small scale, not a concurrency strategy. For real async
  concurrency, ASGI frameworks are the honest fit — but migrating Flask→FastAPI needs a named problem
  first (repository evidence rule).

## Choosing by constraint (not fashion)

| Constraint | Lean toward | Against when |
|---|---|---|
| Full app stack (admin, auth, ORM, migrations) | Django | You want to compose your own stack |
| Async-first API, WebSockets, high concurrent waits | FastAPI/Starlette or Litestar | Stack is sync; async adds a second execution model |
| Minimal, sync, small surface | Flask (or stdlib for tiny tools) | Need batteries or async concurrency |
| Existing repo framework | Keep it | Concrete defect it causes is named |
| Ecosystem/hiring/team familiarity | That ecosystem | — |

- Framework conventions are not universal Python architecture (I10). The framework is a request
  lifecycle tool; domain and use-case logic should not entomb itself in framework objects
  ([architecture.md](architecture.md)).

## Request lifecycle concerns

- **Validation boundary (I1)**: validate at the edge (request models, serializers), pass validated
  shapes inward; never trust query params, headers, or raw body downstream.
- **Authn/authz**: authenticate at a known middleware/dependency boundary; authorize each resource or
  operation where its context is available, whether that is a small handler or a shared use case
  ([security.md](security.md)). Distinguish unauthorized from unauthenticated errors without leaking
  resource existence.
- **Error visibility (I13)**: unhandled exceptions → structured error response + logged with context
  ([observability.md](observability.md)); never return stack traces to clients. Global exception
  handlers translate, they don't silence. Validation errors return field-level detail without echoing
  secrets (I15).
- Middleware ordering is real: auth before handlers, logging capturing full request lifecycle, CORS/
  security headers at the edge. Each middleware adds per-request cost — measure if hot.

## Background tasks vs real queues

- FastAPI `BackgroundTasks` run after the response in the serving process [FRAMEWORK]. Django
  `transaction.on_commit()` runs after a successful DB commit (or immediately outside a transaction);
  it is a commit hook, not a durable worker. Flask `after_request` runs while preparing the response,
  not as an after-response job [FRAMEWORK]. Do not group these under one lifecycle claim.
- In-process callbacks are appropriate only when losing the work on process restart is acceptable.
  Durable follow-up work needs a queue or equivalent persisted intent plus an idempotency answer
  ([reliability.md](reliability.md); [workers-jobs playbook](../playbooks/workers-jobs.md); I8).

## Streaming, WebSockets, SSE

- ASGI supports streaming responses, SSE (server-sent events), and WebSockets [STANDARD]. For
  long-lived streams, plan keepalive as needed, bound producer buffers, and define who closes the
  connection on shutdown ([reliability.md](reliability.md)); own per-connection state (I4).
- WSGI can stream responses (chunked) but no native WebSocket. Don't bolt WebSocket emulation onto
  WSGI; use ASGI or a dedicated service.
- Backpressure: a slow consumer + unbounded producer = memory growth. Bound queues between producer
  and connection ([reliability.md](reliability.md)).

## Serving stack

- Framework ≠ server: production serving topology (uvicorn workers, gunicorn supervision, containers,
  probes) is [deployment.md](deployment.md). One rule that crosses over: request timeouts and graceful
  shutdown live in the serving layer, not the framework config alone.
