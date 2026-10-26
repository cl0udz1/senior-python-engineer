# Overengineering Traps

Simplicity-first under "best practice" pressure. Each case names the **simplest correct shape** in its
Acceptable outcomes — credit requires reaching it (or a clearly better simple shape) and naming what
would justify more. Invariants in play: **I11** (indirection pays rent), **I12** (dependencies justify
themselves), **I9** (evidence before optimization), **I16** (readable and predictable). Routing:
[catalogs/anti-patterns.md](../../../senior-python-engineer/catalogs/anti-patterns.md),
[core/decision-model.md](../../../senior-python-engineer/core/decision-model.md) §2. Grading per
[expected-behavior.md](expected-behavior.md); the banned behaviors most likely here: cargo cult,
architecture to look senior, generic best-practice dumps.

---

### Case OE1 — Plugin architecture for three config keys

**Input**
> "Design the configuration loader for our service. It needs to read three settings: `port` (int),
> `log_level` (string), `worker_count` (int). My plan: a plugin-based config system — a `ConfigSource`
> ABC, implementations for YAML/JSON/env/Consul/etcd, a registry, a validation layer, and a settings
> class with descriptors. We'll be ready for any config scheme."

**Context**
Deployment is one container with three env-var-configurable settings. No Consul/etcd exists in the
stack. No other consumers. The team is 3 people.

**Desired reasoning behavior**
Name the simplest correct shape first: read three env vars (or one small config file) into a frozen
dataclass/namedtuple with `int(...)`/validated conversion and sane defaults — ~20–40 lines total,
validation at the boundary where env strings become typed values (I1), errors fail fast at startup
(I13: a bad `worker_count` should crash at boot, not at 3am). Then apply I11 to each proposed layer:
`ConfigSource` ABC — one source exists (env); registry — no dynamic discovery need; descriptors —
metaprogramming for three fields; Consul/etcd adapters — speculative infrastructure. The name of the
game: future config schemes get added when they arrive, as a plain function; the design should make
*that* change cheap (one obvious place), not pre-build the machinery. Name the condition that earns a
plugin system: genuinely multiple deployed config mechanisms or third-party extension, committed now.

**Acceptable outcomes**
1. Simplest shape delivered: env-based typed settings dataclass + fail-fast validation at startup; explicitly rejects ABC/registry/descriptors per-item with the named problem each fails to solve; names the trigger for a pluggable source later.
2. Same, with a `from_env()` / `load()` function seam so a future source is one added function — cheap future change, zero current ceremony.
3. If the user insists on the plugin design after trade-offs are laid out: implements minimally but records the cost (I11/ADR note) and strips what has no consumer.

**Failure modes**
- Building the full ABC + registry + 5 source classes + descriptor machinery (cargo cult; "ready for anything" is the smell).
- Alternatively, hard-coding three constants with no validation (under-engineering the *actual* need: env strings are external data — I1).
- A 6-framework comparison of config libraries and recommending three dependencies (I12).

**Critical mistakes**
- Skipping validation entirely while claiming "the type hints handle it" (I1 MUST violation: annotations are not runtime validation).

---

### Case OE2 — Caching layer for unmeasured performance

**Input**
> "Let's add a caching layer for performance. Every service call will go through a cache manager with
> TTLs, and we'll back it with Redis. It'll make everything faster and reduce DB load."
>
> The service: an internal task tracker with ~20 users, ~50k rows total, queries currently 5–20ms, no
> measured load problem, no latency SLO stated.

**Context**
DB is local Postgres; dataset comfortably in cache at the DB layer already (shared buffers hold it).
Reads are frequent but cheap. Writes must be visible immediately (users edit tasks and refresh).

**Desired reasoning behavior**
Evidence bar first ([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §3 "add a cache": measured
repeated expensive work + defined invalidation/staleness semantics + hit-rate expectation). Nothing
here passes it: 5–20ms queries, no measured problem, and the correctness cost is concrete (a
read-through cache means a user edits a task and refreshes into a stale screen unless invalidation is
exact — "what is the cost of stale?" has a real answer here: user-visible inconsistency). Redis adds
an operational dependency (new failure mode: cache down → does the service fail open or closed?), I12
surface, and serialization code. Simplest correct shape: no cache; if DB load ever becomes measured,
options start with DB-side (better queries/indexes) before a distributed cache. If a cache is
eventually justified, the design must name key, TTL/invalidation owner, staleness cost, and failure
behavior when the cache is unavailable.

**Acceptable outcomes**
1. Declines the cache with the evidence-bar reasoning + the staleness correctness argument; proposes measurement first (if ever) and DB-layer improvements first.
2. Designs a minimal in-process cache for exactly the one measured-hot value *after* obtaining a measurement — with invalidation owner and staleness cost stated (conditional credit: measurement must actually be demanded).
3. Accepts Redis only behind stated conditions (measured DB saturation + read-heavy + staleness SLO defined) and delivers the full design (keys, invalidation on write, fail-open/closed behavior) — with the current facts clearly said to not meet those conditions.

**Failure modes**
- Building the cache manager + Redis integration "for performance" (architecture to look senior + I9 skip).
- Caching with TTLs chosen by feel and no invalidation story (the classic stale-data bug factory).
- Suggesting microservices/sharding "while we're at it" for the same unmeasured scaling worry.

**Critical mistakes**
- Claiming a benchmark proved the cache improves this service when none was run (fabricated evidence).
- Presenting stale reads after a task edit as consistent with the stated immediate-visibility requirement (fabricated assurance about this system's behavior).

---

### Case OE3 — Abstract factory hierarchy for two call sites

**Input**
> "Refactor this notification code. Current code calls `send_email(...)` and `send_sms(...)` where
> needed. Proposal from a design-patterns enthusiast: `NotificationFactory` ABC,
> `EmailNotificationFactory`, `SmsNotificationFactory`, `Notification` product hierarchy with
> `EmailNotification`/`SmsNotification`, plus a `NotificationFactoryFactory` selecting by config."

**Context**
Two channels, two call sites total, no third channel on any roadmap, one maintainer. Each `send_*`
function is ~10 lines around an SDK call. Behavior differences: address field, payload shape, retry
policy (SMS has none).

**Desired reasoning behavior**
Apply the function-vs-class and composition frames ([decision-model](../../../senior-python-engineer/core/decision-model.md) §2):
the requirement is "send a notification over a chosen channel" — the existing two direct functions
may already be the simplest correct shape. If a caller truly chooses a channel dynamically, a small
`send_notification(channel, ...)` dispatch may clarify that call site. Factory + product hierarchies
earn their rent only when object
creation varies independently of use, products have polymorphic behavior at call sites, or channels are
plugin-supplied — none of which holds. Name the cost: 6+ classes where 2 functions did the job; every
reader must learn the pattern to change a retry policy. Also handle the retry asymmetry honestly in
the simple shape (per-channel policy constants), and name the trigger for more structure (a third
channel with real behavioral variety, or third-party channel plugins).

**Acceptable outcomes**
1. Keeps the existing `send_email` and `send_sms` functions and rejects the proposed hierarchy; checks that each channel's retry policy and test coverage remain distinct.
2. Adds one small `send_notification(channel, ...)` dispatch only if a caller chooses a channel dynamically, with the channel-specific retry behavior visible and tested.
3. Considers a single `Protocol` for the two senders if a concrete consumer benefits (such as uniform testing), explicitly keeping it one level deep — acceptable if it names the value.

**Failure modes**
- Implementing the full factory/product/abstract-factory chain including the "factory factory" (architecture astronautics).
- A lecture on Abstract Factory pattern applicability instead of a design decision (EXPLAIN where decision was requested; slogan-adjacent).
- Conversely: one god-function with nested conditionals and no per-channel test (under-engineering the *testing* of the two behaviors).

**Critical mistakes**
- Claiming a third channel or plugin consumer is committed when the context says neither exists (fabricated requirement).

---

### Case OE4 — The Under-engineering Trap: Dogmatic refusal of a domain/service layer across multi-entrypoint workflows

**Input**
> "I pride myself on absolute simplicity and zero abstractions. We have an e-commerce checkout flow: validate cart inventory, apply coupon discounts, create order record, deduct stock, and dispatch a payment charge. Currently, all 80 lines of this logic live right inside our FastAPI route handler `checkout_endpoint`. Now our PM asked us to trigger the exact same checkout workflow from a Celery background worker (for recurring subscriptions) and a CLI command (for back-office phone orders). Another dev suggested creating a `CheckoutService` or `checkout_order()` function in a domain module, but I said no—services and use-case layers are unnecessary enterprise bloat. I'm just going to copy-paste the checkout logic into the Celery task and CLI script to keep things simple. Review my decision."

**Context**
The checkout workflow changes inventory and orders in one database and also calls a separate payment provider. A database rollback cannot undo an accepted remote charge. The provider supports stable idempotency keys and querying charge status within a documented retention window. A timeout may happen after provider acceptance. The workflow is now needed from HTTP, Celery, and CLI; the team needs one consistent policy for pending, paid, and failed orders.

**Desired reasoning behavior**
Reject the user's premise. The user has conflated "simplicity" with dogmatic refusal of an architectural boundary (anti-pattern 28: under-engineered controller / anemic handler coupling). When multiple entrypoints (API, background worker, CLI) execute identical multi-step transactional business workflows, inlining logic into transport handlers creates severe failure modes:
1. Business logic drift: Bug fixes, tax calculation updates, discount rules, or validation logic made in the API handler will not reach the worker or CLI, causing split-brain business rules.
2. Inconsistent transaction boundaries and failure handling: Duplicated raw session/transaction management across three different execution models (asyncio FastAPI, prefork Celery, sync Click/Typer CLI) risks connection leaks, missing rollbacks, or inconsistent isolation.
3. Testing friction: Transport-coupled workflows can make focused domain tests harder; do not claim the code is literally untestable without seeing its tests.
Explain the senior engineering standard: the goal is the **least complex design that correctly satisfies actual constraints and expected evolution**. A cohesive `checkout_order(session, ...)` service function or use-case object is not "enterprise bloat"—it is the minimum necessary architectural boundary that eliminates triple code duplication, makes local transaction ownership visible, and makes transport controllers thin protocol adapters. Extraction alone does not make the payment and database atomic: require a proportionate durable intent/state, stable payment identity, and reconciliation or compensation policy for unknown outcomes. The shared workflow must own that policy consistently; avoid holding database locks across a slow remote call without an explicit reason.

**Acceptable outcomes**
1. Firmly rejects copy-pasting into handlers; recommends extracting a cohesive `checkout_order(...)` domain/service function or unit-of-work coordinator in a domain module, with API, worker, and CLI acting as thin callers that pass parsed parameters and handle protocol-specific errors.
2. Recommends the service function extraction and explicitly outlines the transaction boundary contract: the caller provides/owns the DB session (or the service manages a unit of work context), ensuring the database changes commit atomically, while separately stating the remote-payment consistency and recovery policy.
3. Notes that rejecting unnecessary class hierarchies or DI containers was good instinct, but refusing a shared functional domain seam across 3 entrypoints is severe under-engineering that creates data integrity and maintenance debt.

**Failure modes**
- Claiming a shared function or database transaction makes remote payment atomic with local state.
- Validating the user's dogma: "You're totally right, services are bloat; copy-pasting is simpler than creating a service layer."
- Proposing extreme enterprise over-engineering in response: proposing a full Clean Architecture / DDD setup with 8 layers, repository interfaces, abstract factory beans, and a CQRS event bus.
- Focusing on style or DRY formatting instead of transactional integrity, split-brain drift, and testability risks.

**Critical mistakes**
- **C2 — harmful invariant violation presented as fine:** recommending blind retries of potentially accepted charges without idempotency or reconciliation, while calling the flow safe (I8).
- **C4 — invented contract fact:** claiming database rollback reverses a remote provider charge.
- Copying the workflow or violating I11 (a SHOULD) is a scored maintenance/scope failure by itself, not an instant-fail category. Every acceptable outcome must address the payment boundary as well as shared workflow ownership.

---

### Case OE5 — Type-level machinery explosion in a 30-line transform

**Input**
> "Here's my typed version of our row transform. Review the typing design:
>
> ```python
> T = TypeVar("T", bound=SupportsRow)
> S = TypeVar("S", covariant=True)
> P = ParamSpec("P")
>
> class Transform(Generic[T, S], Protocol):
>     def __call__(self, row: T, /, **opts: Unpack[TransformOpts]) -> S: ...
>
> def transform_rows(
>     rows: Iterable[T],
>     fn: Transform[T, S],
>     *,
>     on_error: Callable[[T, Exception], S | Literal["skip"]] = lambda r, e: "skip",
> ) -> Sequence[S | Literal["skip"]]: ...
> ```
>
> (The actual transform is 30 lines: reads a row dict, computes two derived fields, writes a dict.)
> The team is 3 people; nobody on it has used `Unpack` or `ParamSpec` before."

**Context**
Internal transform in a data pipeline (short-lived: expected to churn with the pipeline, not a public
API); one caller. Rows are `dict[str, Any]`-shaped coming from JSON
(I1: validated at the pipeline boundary, not by these annotations). Errors currently can't happen
except from bad rows (already validated). The type machinery took the author a day and needs a
30-line comment to explain.

**Desired reasoning behavior**
Typing proportionality ([decision-model](../../../senior-python-engineer/core/decision-model.md) §5, [references/typing.md](../../../senior-python-engineer/references/typing.md)):
annotations are static metadata, not validation (I1) — the trust boundary already validated rows;
here typing serves *maintainers*. Cost/benefit: `ParamSpec`, `Unpack`, covariant TypeVars, and
`Literal["skip"]` unions encode a call contract far more complex than the runtime behavior; for a
30-line internal transform with one caller and a 3-person team, the annotation complexity exceeds the
defect-prevention value — the reading cost lands on every future change (I16: readability is the
maintenance interface). Simplest correct shape: `def transform_rows(rows: Iterable[Row], ...) -> list[Row]`
with `Row = TypedDict` or `dict[str, Any]`, plain `Callable[[Row], Row]`, and error handling that
matches the real requirement (fail fast on invalid rows — they're already validated upstream).
Where typing *does* pay: the pipeline's public boundary, shared row schema (TypedDict), exported
library functions — say so, so the answer is not "typing bad".

**Acceptable outcomes**
1. Simplifies to `Callable[[Row], Row]` + `TypedDict`/alias shapes; explains per-element why the ParamSpec/Unpack/covariance machinery buys nothing here; names where heavier typing pays (public/shared boundaries).
2. Same, plus distinguishing fact layers: generics syntax is real [STANDARD] power, the failure is applying it where defect-prevention value < comprehension cost (not "Python typing is broken").
3. Middle option: keeps `Protocol` for the transform callable (one construct, real value: named contract) but drops ParamSpec/Unpack/covariance/Literal machinery — justified per construct.

**Failure modes**
- Praise-the-ratchet: "excellent typing, more strictness everywhere" (automatic strict typing).
- Ripping out *all* annotations including useful TypedDict boundary types ("typing is bloat") — opposite extreme.
- Rewriting the transform's runtime logic while leaving the type design unaddressed (scope-blind).

**Critical mistakes**
- Claiming annotations validate the rows at runtime ("type safety") (I1 MUST violation shape; annotations are not runtime validation).
- Claiming the typing spec requires/forbids this design (invented [STANDARD] fact — strictness and machinery depth are policy).

---

### Case OE6 — Shared base for two calculations that change apart

**Input**
> "These two functions look the same. DRY says pull them into a template-method base:
>
> ```python
> def invoice_tax(lines):
>     return sum(line.amount * line.rate for line in lines if line.taxable)
>
> def shipping_estimate(parcels):
>     return sum(p.weight_kg * zone_rate(p.zone) for p in parcels if p.billable)
> ```
>
> Proposed: `class Reducer(ABC)` with abstract `include` and `measure`, plus `TaxReducer` and
> `ShippingReducer`. Please implement that refactor."

**Context**
Tax rates change when the statute changes. Shipping rates change when the carrier contract changes.
Neither team edits the other function. Each function has one caller. There is no third reducer on
the roadmap. The bodies are the comprehensions above, not a shared policy.

**Desired reasoning behavior**
Duplication is the cheaper design here ([architecture.md](../../../senior-python-engineer/references/architecture.md),
[decision-model](../../../senior-python-engineer/core/decision-model.md) §2). The similar shape is a sum of selected terms; the
rules will change for different reasons, so a shared base would make a tax change look like a
shipping change. Leave the two functions. A private helper that only factors `sum(...)` is optional
and low value. A template-method hierarchy does not pay rent (I11). This is not the multi-entrypoint
checkout case (OE4): there the rule itself must stay the same.

**Acceptable outcomes**
1. Rejects `Reducer` and leaves the two functions, naming the different reasons they will change.
2. Same, and contrasts OE4: extract when one rule must stay true across entrypoints; do not extract when only the spelling matches.
3. Extracts a tiny local helper only if it keeps tax and shipping policies in their own functions and does not introduce a class.

**Failure modes**
- Implementing `Reducer`, `TaxReducer`, and `ShippingReducer` because the comprehensions look alike.
- Merging both calculations into one function with a `kind` flag, so a tax edit can break shipping.
- Citing "DRY" or "open/closed" as a requirement to add the hierarchy before a third calculation exists.

**Critical mistakes**
- Claiming Python or the packaging standards require DRY or a template-method base (invented [STANDARD]/[LANGUAGE] fact).
