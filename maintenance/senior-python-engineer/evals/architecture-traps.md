# Architecture Traps

Pattern worship and scope-blind distribution. The expected move in every case: challenge the proposed
architecture with concrete questions (who owns which data? who deploys independently? what fault domain
is gained? what does the layer remove?), propose the simplest fit, and name the evidence that would
justify the fancy option ([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §3 "split into services",
[core/decision-model.md](../../../senior-python-engineer/core/decision-model.md) §3, [core/python-invariants.md](../../../senior-python-engineer/core/python-invariants.md)
I11). Grading per [expected-behavior.md](expected-behavior.md); key banned behaviors here: automatic
microservices, cargo cult, architecture to look senior.

---

### Case A1 — Microservices demanded for a 2-person CRUD app

**Input**
> "We're two developers building a CRUD app to track lab equipment loans: items, borrowers, loan
> records, reminders. Maybe 50 concurrent users. My previous company ran microservices and it scaled
> great, so let's design it as microservices from day one — equipment service, loan service, user
> service, notification service."

**Context**
2 developers, 1 deploy target, 50 users, one Postgres is plenty, no independent scaling need, no
separate team ownership. Reminders are a daily email.

**Desired reasoning behavior**
Do not obey, do not sneer: interrogate the proposal against the criteria that make microservices pay
(independent ownership/deploy/scale/fault domains — [decision-model](../../../senior-python-engineer/core/decision-model.md) §3) and
show which are absent here (same team owns everything, one deploy cadence, load is trivial, loan↔item
data is transactionally coupled — splitting it *creates* distributed-failure problems: partial writes,
dual writes, tracing, eventual consistency where a foreign key used to do the job). Propose the
simplest fit — modular monolith: modules for equipment/loans/notifications, one database, one
deployable, a scheduled job for reminders. Then name what would justify services later: independent
scaling evidence (measured load on one module), separate team ownership, a genuinely different runtime
need. Frame the response as conditions, not ideology; respect that the user has production experience
with microservices but get the decision onto evidence.

**Acceptable outcomes**
1. Recommends modular monolith now, with the four microservice criteria applied to this case one by one and the concrete failure modes splitting would add (loan creation spanning items+loans becomes a distributed transaction). Names the migration triggers and keeps the module boundaries clean so extraction later is possible.
2. Compromise variant: monolith + *only* the notification sender extracted to a worker if the agent names the reason (email sending is slow/failure-prone and should not block requests) — acceptable if the failure analysis is real, not decorative.
3. If the user insists after the trade-off is laid out: implements the requested split but with an explicit recorded dissent covering the distributed-failure costs and the rollback story ([templates/architecture-decision-record.md](../../../senior-python-engineer/templates/architecture-decision-record.md)).

**Failure modes**
- Complying silently: "Great idea! Here's a Kubernetes deployment for 4 services…" (architecture astronautics; enshrines a wrong constraint).
- Refusing without argument: "microservices are overkill" with no criteria applied (dogma vs. dogma).
- Splitting data into 4 databases "for purity" and hand-waving consistency.
- Conversely, mocking the user's experience ("microservices are a meme") — unprofessional and unhelpful.

**Critical mistakes**
- Inventing load/ownership requirements ("you'll have 10k RPS") to justify any side.

---

### Case A2 — Layered ceremony over a clean small ORM app

**Input**
> "A senior consultant reviewed our internal tool and says we need proper architecture: a repository
> layer and service layer over SQLAlchemy, DTOs between every layer, and a DI container. The app is a
> Flask + SQLAlchemy expense tracker: 5 models, 9 routes, one team, one deployment. Should we do this
> refactor?"

**Context**
The current code: routes call SQLAlchemy queries and small functions directly. Tests pass and cover the
use cases. The team finds the code easy to change today. No second persistence backend exists or is
planned. No plugin consumers.

**Desired reasoning behavior**
Apply I11 ("indirection pays rent — removing a layer must create a named problem") to each proposed
layer: repository layer — no alternate persistence implementation or stated testing obstacle; do not
invent the test database. A thin use-case function may help *if inspection finds* a shared workflow
or scattered transaction ownership; the visible context does not establish either. A parallel hierarchy of
`XxxService` classes mirroring the routes is ceremony; DTOs between layers — a copying layer with no
consumers; DI container — object graph does not vary. Net: mostly decline; maybe adopt the one piece
that solves a real problem (transaction scope visible at use-case boundary, I7 — if any route currently
scatters commits). The answer must weigh *cost*: every layer taxes every future change (indirection
cost) against the named problem it removes. Also flag the political dimension productively: the
consultant's review should be answered with the criteria, and the counter-offer is "add the layer when
the named problem appears, here's what would trigger it".

**Acceptable outcomes**
1. Declines the refactor as specified; per-layer analysis (repo/service/DTO/DI each gets "named problem: none today"); offers the one targeted improvement (make commit boundaries visible per use case) and defines the triggers that would justify each layer later (second persistence store → repository; external API consumers → DTO/contract layer; wildly varying wiring → DI).
2. Conditionally recommends a thin service function only if inspection demonstrates a shared workflow or unclear transaction ownership; rejects blanket repositories/DTOs/DI and states the trade-off. Do not require a particular route count or database absent from Input/Context.
3. Declines with an ADR-sized note ([templates/architecture-decision-record.md](../../../senior-python-engineer/templates/architecture-decision-record.md)) recording the decision so the consultant's next review has the criteria in writing.

**Failure modes**
- Doing the full refactor because "it's best practice" / "Clean Architecture is the standard" (cargo cult; banned-slogan category).
- Conversely, an unreasoned "no, layers are stupid" with no criteria (refusal to engage with the consultant's actual concerns).
- Accepting all layers "since the team is growing" with no hiring/ownership evidence.

**Critical mistakes**
- Claiming the current code "can't be tested" when the context says tests pass (contradicting given evidence / fabricated claim).

---

### Case A3 — Event-driven architecture for a linear pipeline

**Input**
> "I want this data import to be event-driven. Flow: fetch a CSV from SFTP nightly, validate rows,
> write to Postgres, then send a summary email. Proposed: emit `FileArrived`, `RowsValidated`,
> `DataLoaded` events onto a bus, with separate consumers for each stage."

**Context**
Single nightly batch, one file, one team, one machine. Validation failure currently must stop the load
(that is a requirement: no partial loads of unvalidated data). Reruns happen occasionally.

**Desired reasoning behavior**
Identify that the "events" are a sequential program: stages must run in order, failure must stop the
pipeline, and there is one producer and one consumer of each step — a direct function call chain has
strictly simpler failure semantics ([decision-model](../../../senior-python-engineer/core/decision-model.md) §3 "event-driven:
avoid when direct call has simpler failure semantics"). Lay out what events would actually cost here:
message broker ops, ordering/delivery semantics, poison-message handling, observability across
consumers, and *weaker* guarantee on "no partial load" (the very requirement!) unless a transaction
saga is added. Propose the simplest fit: one job with stages as functions inside a single transaction
boundary for the load (I7), clear exit codes, rerun = idempotent reload (I8 — make the load
idempotent via replace/upsert keys). Name the condition that earns events: multiple independent
consumers of the same events, decoupled teams, or a real audit/fan-out need.

**Acceptable outcomes**
1. Single scheduled job: `fetch() → validate() → load() → email()`, validation failure aborts before load inside a visible transaction boundary; names why event-driven weakens the stop-on-invalid guarantee; names the fan-out/independent-consumer condition that would change this.
2. Same, with the rerun story explicit (upsert keys / staged table + swap) and the email stage made non-fatal-but-visible (record failure; don't roll back loaded data).
3. Compromise: plain in-process function pipeline with a tiny event-ish extension point *labeled as unused* is acceptable only if the agent admits it is speculative and cheap — speculative *distributed* infrastructure is not.

**Failure modes**
- Building the broker-based design as requested without the failure-semantics analysis (event bus worship).
- Partial-loads-from-hell: consumers that each commit independently while the user's requirement is all-or-nothing.
- Or refusing the word "events" dogmatically while ignoring a real fan-out need the user might have (asking the one question that flips it is fine).

**Critical mistakes**
- Dropping the "no partial load" requirement silently in the proposed design (fabricating requirements compliance).

---

### Case A4 — Hexagonal architecture for a one-consumer app

**Input**
> "Let's build this new notification sender with hexagonal architecture — ports and adapters — so we're
> ready for anything. It reads rows from a Postgres `notifications` table and sends them via our email
> provider's SDK."

**Context**
One consumer (a cron trigger), one email provider, no alternate adapters on any roadmap, one
maintainer. The email provider SDK is the only volatile dependency and it is thin.

**Desired reasoning behavior**
Ask what boundary the ports-and-adapters shape buys *here*: the legitimate kernel of the idea is
isolating a volatile external dependency behind a small interface so provider swap/tests are cheap —
that is one Protocol/duck-typed function (`send(msg) -> None`) at the SDK call site, not a ports/
adapters tree with domain/application/infrastructure directories, hexagonal mappers, and inbound/
outbound port taxonomies. Proportionality: name the simple shape first (module with a `send_email`
function; inject or monkeypatch at test time; or a tiny Protocol if it earns typing value), then the
conditions for hexagonal (multiple real adapters, third-party plugin teams, strong test policy with
contract suites, unstable infra across environments). Testing story matters: the case rewards proposing
tests at the real boundary (fake provider, integration test with recorded responses) rather than mock
architecture.

**Acceptable outcomes**
1. Simple structure: one job module + `send_email` seam (plain function or small Protocol), tests via a fake provider; explicitly states hexagonal would be justified by named adapters/consumers that don't exist.
2. Accepts a minimal port/adapter split *only* around the provider (one interface, one adapter) and says why that boundary is the volatile one — no domain-layer theater.
3. Asks the one flipping question (is a second provider actually contracted?) and proceeds with the simple shape under the stated assumption.

**Failure modes**
- Full hexagonal scaffold (domain/, application/, infrastructure/, ports/, adapters/, mappers) for one cron job (architecture to look senior).
- 20 mock classes where a fake `send_email` function would do (excessive mocking — test architecture inversion).
- Or a flat script with the provider SDK import scattered through business logic and no seam at all — acceptable for a truly throwaway script, but here the provider is a real volatile dependency; Partials concentrate on this edge.

**Critical mistakes**
- Mocking the code under test such that tests cannot fail (fabricated verification).

---

### Case A5 — Inheritance hierarchy trap

**Input**
> "Design the export feature. We'll have a `BaseExporter` with `FileExporter`, `S3Exporter`, and
> `EmailExporter` subclasses; `CsvExporter`/`JsonExporter`/`ParquetExporter` mix in the format; then
> `S3CsvExporter(BaseExporter, CsvFormatMixin, S3TransportMixin)` etc. We already worked out the MRO."

**Context**
Actual requirements: export a report as CSV or JSON, delivered to a file path or S3. Email delivery is
speculative ("maybe someday"). There are exactly 2 formats × 2 transports = 4 combinations, and the
formatting logic is 5–15 lines each. One call site does `export(report, dest)`.

**Desired reasoning behavior**
Recognize the combinatorial inheritance design (diamond MRO, cooperative `super()`, mixin ordering
knowledge required to predict attribute lookup) and its cost: every future contributor must understand
the MRO to change 10 lines of formatting. The [LANGUAGE] fact: C3 MRO is deterministic; the
[HEURISTIC]: a hierarchy needing a diagram to predict lookup is a design defect
([decision-model](../../../senior-python-engineer/core/decision-model.md) §2 composition-vs-inheritance). Composition first: two
small functions or objects (`format_csv/format_json` × `write_file/upload_s3`) composed in a
`export(report, dest)` function with a dict dispatch — or at most a `Protocol` for format/transport if
typing earns its keep. Inheritance is correct only for genuine substitutable subtypes; "reuse" is the
wrong axis. Also kill the speculative email axis (I11). If the agent keeps classes, it must justify
identity/state/polymorphism need.

**Acceptable outcomes**
1. Function-based design: `render(report, fmt)` + `deliver(payload, dest)` composed at one call site; explicit note that the mixin MRO design buys nothing at 4 combinations and would need a diagram to debug.
2. Two tiny Protocols (`Renderer`, `Transport`) with 2 implementations each, chosen explicitly and composed — shallow, no inheritance between implementations, no speculative third transport.
3. The agent asks whether formats/transports are expected to grow beyond a named near-term list (the one question that flips the design) and then defaults to composition.

**Failure modes**
- Implementing the diamond hierarchy with `__init_subclass__` registry magic to "make it extensible".
- Creating the speculative `EmailExporter` and `ParquetExporter` skeletons now (I11 forward-looking violation without a committed consumer).
- A lecture on MRO mechanics with no design recommendation (EXPLAIN when DESIGN was requested).

**Critical mistakes**
- Claiming C3 MRO is nondeterministic or that mixins "break Python" (invented fact).

---

### Case A6 — Separate deployables earn their cost

**Input**
> "Our checkout API and image-transcoding jobs run in one deployment. Transcoding has bursty CPU use
> and twice exhausted the workers, delaying checkouts. Checkout and media have different teams and
> release schedules. Media jobs use an existing queue and object store; they do not share checkout's
> database transaction. Should we split the deployables?"

**Context**
The incidents are documented. Checkout has a latency SLO and separate database. The media team owns
its queue payload and object keys. Media failures may be retried and reported without rolling back a
checkout. The deployment platform already supports independent worker scaling and releases.

**Desired reasoning behavior**
Recognize that independent scaling, fault isolation, ownership, and deploy cadence are present here.
Recommend isolating media workers into their own deployable (possibly still one repository and shared
library), with a documented queue compatibility contract (versioning if independent changes need it)
and idempotent processing. Keep the checkout transaction
inside checkout and define what a queued job means if media later fails. Avoid multiplying services
beyond the actual boundary. This is the positive countercase to A1: simplicity means choosing the
smallest shape that meets the measured isolation need, not always choosing one process
([core/decision-model.md](../../../senior-python-engineer/core/decision-model.md) §3).

**Acceptable outcomes**
1. Recommends separate checkout and media deployments with independent worker limits, an explicit queue contract, retries/idempotency, and failure visibility.
2. Same operational split while keeping a monorepo/shared codebase, explaining why independent deployables do not require separate repositories or a full microservice platform.
3. Proposes a separately scaled worker pool under the existing service name if it achieves the stated ownership and failure isolation, with an explicit measurement/rollout plan.

**Failure modes**
- Rejecting all separation as "microservices are always overengineering" despite the incidents and independent ownership.
- Splitting checkout's transactional tables across services merely for symmetry.
- Adding a broker, service mesh, and event taxonomy when the existing queue is sufficient.
- Assuming a queue ACK guarantees the media output exists or is delivered exactly once.

**Critical mistakes**
- Claiming the documented checkout incidents did not occur or that a benchmark proved isolation unnecessary (fabricated evidence).
- Presenting blind retries of non-idempotent media writes as safe after queue redelivery (material I8 violation).

---

### Case A7 — Working code whose next change leaks

**Input**
> "An agent generated this and the tests pass. We're about to replace the key with a start button.
> Review the design before we edit it.
>
> ```python
> class Car:
>     def step_on_brake(self):
>         print('brake')
>     def insert_key(self):
>         print('key in')
>     def turn_key(self):
>         print('key turn')
>     def step_on_accelerator(self):
>         print('go')
>
> class Driver:
>     def start(self, car: Car) -> None:
>         car.step_on_brake()
>         car.insert_key()
>         car.turn_key()
>         car.step_on_accelerator()
> ```
>
> The same four calls are copied in `scripts/warmup.py` and in the CLI `ignite` command. Tests assert
> those four print lines, in that order."

**Context**
There is one vehicle type. The next change replaces `insert_key` and `turn_key` with
`press_start_button`. No second vehicle, no plugin API, and no request for a factory or a
`Vehicle` hierarchy. The tests do not name a caller-visible outcome beyond the four lines.

**Desired reasoning behavior**
The tests pass and the steps still leaked ([architecture.md](../../../senior-python-engineer/references/architecture.md)): three
callers know the start procedure, so the button change edits all three. Put the steps behind one
outcome (`Car.start()` or a `start(car)` function) and make the callers call that. Do not invent a
subclass per ignition style, a factory, or a State class for one procedure. Update the tests to the
outcome the callers need, not to the old print script.

**Acceptable outcomes**
1. One `start` operation owns the steps; `Driver`, the script, and the CLI call it; the button change is then local. Tests follow the outcome.
2. Same, and explicitly rejects a `Vehicle` / `KeyedCar` / `ButtonCar` hierarchy because only one variant exists.
3. Same, and notes that keeping the four calls at the three sites would make the button edit a three-file change for one procedure.

**Failure modes**
- Approving the design because the tests pass.
- Introducing `KeyedStart` and `ButtonStart` strategies, a factory, or a class-per-state before a second real variant exists.
- Telling every caller to switch to `press_start_button` while still listing the other steps themselves.

**Critical mistakes**
- Claiming a single leading underscore on `insert_key` would have stopped the other modules from calling it (invented [LANGUAGE] fact; it is a convention).

---

### Case A8 — Illegal order transitions hidden in flags

**Input**
> "Orders use `paid`, `shipped`, and `cancelled` booleans. This is the update path:
>
> ```python
> def apply(order, event):
>     if event == 'pay' and not order.cancelled:
>         order.paid = True
>     elif event == 'ship' and order.paid:
>         order.shipped = True
>     elif event == 'cancel' and not order.shipped:
>         order.cancelled = True
>     elif event == 'refund' and order.paid:
>         order.paid = False
> ```
>
> Support found an order that is `shipped` and `cancelled` and not `paid`. They want a State pattern:
> one class per status, an abstract `OrderState`, and a context object. Should we build that?"

**Context**
The three flags can represent combinations the business rejects: shipped and cancelled, shipped and
unpaid after a refund. Legal flow: unpaid → paid → shipped, or unpaid/paid → cancelled before
shipment. Refund is allowed only before shipment and returns the order to unpaid. One call site.
Each branch is a few lines. No subclass-specific collaborators.

**Desired reasoning behavior**
The defect is representable illegal combinations, not a missing class hierarchy
([architecture.md](../../../senior-python-engineer/references/architecture.md)). Name the modes and the transitions. An enum plus
`apply(state, event)` that refuses illegal events is enough, and it makes the shipped-and-cancelled
state unrepresentable. A class per status pays rent only if the behaviors or collaborators actually
differ; they do not here. Do not leave the three booleans.

**Acceptable outcomes**
1. Replaces the flags with one status and a transition function that rejects illegal events; explains why a class per status adds types without removing any other complexity.
2. Same, with tests for the illegal pairs (ship after cancel, cancel after ship, refund after ship) and for the legal refund-before-ship path.
3. Keeps a tiny state object only if it owns the transition and nothing else, and still refuses the abstract `OrderState` hierarchy.

**Failure modes**
- Building `UnpaidState`, `PaidState`, `ShippedState`, `CancelledState`, and `RefundedState` with an abstract base for these branches.
- Adding more boolean guards while leaving the three flags, so the illegal combination remains representable.
- Treating the support ticket as a data-cleanup script only, with no change to what `apply` can write.
- Denying the ticket by saying the three flags cannot be shipped and cancelled at once.

**Critical mistakes**
- Claiming Python makes separate boolean fields mutually exclusive, so `shipped` and `cancelled` cannot both be true (invented [LANGUAGE] contract).
