# Architecture Review

## Contents

- [Scope & trigger](#scope--trigger)
- [Review contract](#review-contract)
- [Procedure](#procedure)
- [Checklist](#checklist)
- [Finding format](#finding-format)
- [False positives / legitimate exceptions](#false-positives--legitimate-exceptions)
- [Output expectations](#output-expectations)

System-level design review: does this design fit its actual requirements and dominant constraint, and
does every layer of complexity in it pay rent? For diff-level review use [Code Review](code-review.md);
for a release gate use [Production Readiness](production-readiness.md).

## Scope & trigger

Use this review when:

- A new system or major subsystem is being designed ([DESIGN]/[BLUEPRINT] tasks) — output follows
  [templates/blueprint.md](../templates/blueprint.md), scaled to project size.
- An existing system's structure is questioned ("is this the right architecture?") — inspect the repo
  first per [Existing Codebase](../playbooks/existing-codebase.md).
- A change crosses module/service boundaries: new service or datastore, new queue, sync→async
  conversion, monolith→services, ORM↔SQL migration, native extension, public API shape.
- A low-reversibility decision must be recorded: [templates/architecture-decision-record.md](../templates/architecture-decision-record.md).

Do NOT use it for line-level correctness (→ [code-review.md](code-review.md)), a single query's shape
(→ [database-review.md](database-review.md)), or a speed claim (→ [performance-review.md](performance-review.md)).
Depth is proportional: a one-file utility gets a few sentences of review, not an enterprise document
([principles §7](../core/engineering-principles.md)).

## Review contract

Follow the shared [review contract](code-review.md#review-contract) for task scope,
priority, severity, evidence, finding format, and a valid clean-review outcome.

## Procedure

1. **Read repository evidence first** (for existing systems): `pyproject.toml`, dependency set, lockfile,
   tests, CI, deployment config, DB layer, sync vs async model — the full scan in
   [existing-codebase.md](../playbooks/existing-codebase.md). Repository evidence outranks ecosystem
   preference ([evidence-rules §1](../core/evidence-rules.md)).
2. **Restate requirements and the dominant constraint** (latency? throughput? correctness risk? team
   size? operational maturity?). If the request names none, state the working assumption and proceed —
   do not stall ([principles §7](../core/engineering-principles.md)).
3. **Classify the workload** before judging the execution model: CPU-bound vs wait-bound, read vs write,
   batch vs interactive ([decision-model](../core/decision-model.md)).
4. **Build the ownership map**: for every piece of mutable state, resource, session, transaction, task,
   queue and cache — who creates it, who may mutate it or coordinate access, who releases it, and what happens to it on
   shutdown ([principles §4](../core/engineering-principles.md)).
5. **Draw the trust boundaries**: which data crosses process/network/storage boundaries, where is it
   validated (I1), where do secrets live (I15).
6. **Walk the failure questions that apply** to this system's boundaries — the relevant subset of
   [failure-modes](../catalogs/failure-modes.md): duplicate execution, mid-task death, timeout, partial
   success, unbounded growth, schema change (I14). Not the whole list.
7. **Charge rent**: for every layer, queue, service, cache, and native boundary, name the problem it
   solves and the cost it adds (I11). New infrastructure/dependencies state their value case (I12).
8. **Check reversibility**: cheap-to-reverse decisions (module layout, helper shape) get a line of
   rationale; expensive ones (datastore, service split, native boundary, public API) get an ADR with a
   review trigger ([evidence-rules §7](../core/evidence-rules.md)).
9. **Write the output** with [templates/blueprint.md](../templates/blueprint.md) or
   [templates/architecture-decision-record.md](../templates/architecture-decision-record.md), findings
   in the standard format below.

## Checklist

| Check | Mechanism | Evidence to look for |
|---|---|---|
| Requirement fit | Every design element traces to a stated requirement; elegance is not a requirement | Component list vs requirement list; components with no mapped requirement are suspect |
| Dominant constraints named | The constraints that drive the choices (latency, correctness risk, team size…) are stated | Design/ADR explains trade-offs; an omission is a finding only when it obscures a material choice |
| Ownership map complete (I2, I4, I6, I7) | State, resources, sessions, transactions, tasks, queues have clear owners or coordinated access and release points | Diagram/text naming responsibility; conflicting mutations without a safe strategy are a finding per [principles §4](../core/engineering-principles.md) |
| Trust boundaries (I1, I15) | External data validated at an appropriate boundary; secrets behind a config/secret boundary | Validation mechanism named; grade unvalidated input by reachable corruption or exposure |
| Transaction boundaries visible (I7) | What commits/rolls back together is visible at the use-case level | Use-case description/sequence; a hidden commit is a finding when it can surprise the caller or break atomicity |
| Execution model fit (I5) | CPU vs wait classification matches the thread/process/async choice; async needs real multiplexing + async-capable deps | Workload class + dependency audit; "async because it's faster" = finding ([decision-model](../core/decision-model.md)) |
| Indirection pays rent (I11) | Each repository/service/DI/plugin/queue/event bus names its problem and its cost | Removing the layer must create a named problem; otherwise "ceremony" finding |
| Change stays local | Changing how work is done does not edit callers that only wanted the outcome; a hierarchy matches the axis that varies | Callers list a collaborator's steps; the next real variant requires a subclass on the wrong axis ([architecture.md](../references/architecture.md)) |
| Public contract holds | Names, units, and inherited operations match what a caller can do without reading the body | A zero-based calendar field next to 1-based ones; a `list`/`dict` subtype that rejects ordinary updates; a mutator that breaks a state other methods assume ([architecture.md](../references/architecture.md)) |
| Failure-mode coverage (I14) | Relevant boundary questions answered: duplicate job, mid-task death, timeout, partial success, unbounded queue, schema change | A material unanswered question is graded by the consequence it leaves unresolved |
| Reversibility recorded | Expensive decisions have an ADR + review trigger | ADR entries for datastore, service split, native boundary, public API |
| Framework conventions local (I10) | Framework lifecycle rules ([FRAMEWORK]) applied only where that framework runs | Django/Flask/FastAPI/SQLAlchemy rules kept local, not generalized into universal Python rules |
| Dependencies justified (I12) | Consequential new dependencies/infrastructure state their value case | [principles §1](../core/engineering-principles.md) justification proportionate to cost; grade an unexplained addition by its risk |

## Finding format

Every finding follows [templates/code-review.md](../templates/code-review.md):
`Severity:` `Evidence:` `Why it matters:` `Recommended change:` `Trade-off:` `Verification:`.

Grade by reachable consequence, not the invariant's MUST/SHOULD label
([invariants](../core/python-invariants.md#using-these-in-reviews)). Evidence cites the concrete
mechanism — "this queue has no bound and the consumer can stall" — never "this feels overengineered".

### Example finding (shape only)

- **Severity:** High
- **Evidence:** `billing/service.py:88` and `reports/refresh.py:41` both mutate `Account.balance`;
  the design doc names no owner or synchronization for it.
- **Why it matters:** two writers without an owner is a lost-update race and a hidden transaction
  boundary (I4, I7) — the reporting refresh can silently roll back billing's write.
- **Recommended change:** make the billing use case the single writer; reports consume committed
  snapshots refreshed on a schedule.
- **Trade-off:** reports become eventually consistent within the refresh interval.
- **Verification:** a test running both writers against one account asserts the balance invariant;
  the blueprint's ownership map names the single writer.

## False positives / legitimate exceptions

- **A modular monolith is not a finding.** Missing microservices is never a finding; distribution needs
  independent ownership/deploy/scale/fault domains ([evidence-rules §3](../core/evidence-rules.md)).
- **A one-file utility without layers is not a finding.** Proportionality ([principles §7](../core/engineering-principles.md)).
- **A forward boundary can be legitimate** when a near-term consumer, enforced contract, or costly future
  change justifies its current cost. Ask for the rationale; absence of a second consumer alone is not a finding.
- **Framework choice is not a finding.** Django vs FastAPI vs Flask is a workload decision; repo evidence
  wins. Recommending Flask→FastAPI or sync→async without a named problem is forbidden.
- **Not every decision needs an ADR** — only low-reversibility ones ([evidence-rules §7](../core/evidence-rules.md)).
- **Existing conventions are the starting point.** Poetry-over-uv, ORM-over-raw-SQL, or sync-over-async
  are not defects without a concrete problem they cause ([existing-codebase](../playbooks/existing-codebase.md)).
- **Simple direct calls are not "missing abstraction".** A plain function is the default shape; layers
  must justify themselves, not the reverse.

## Output expectations

- Lead with the verdict: does the design fit its dominant constraint, and what are the top findings in
  priority order? Then the reasoning a reviewer can challenge.
- Every finding carries evidence (code location, config value, doc section, or named mechanism). A claim
  without evidence is dropped ([evidence-rules](../core/evidence-rules.md)).
- "No significant issue found." is a valid complete result — for the review or any section. State what
  was inspected and what was out of scope; never fabricate findings to appear thorough.
- Name what would change the recommendation (e.g. "if measured wait-bound concurrency exceeds one
  process's budget, revisit the execution model").
- Never generate architecture to look senior: if the simplest design satisfies the requirements, the
  correct review result is that it does.
