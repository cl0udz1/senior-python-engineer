# Architecture Decision Record (ADR)

## Contents

- [Fill-in structure](#fill-in-structure)
- [Context](#context)
- [Decision](#decision)
- [Alternatives considered](#alternatives-considered)
- [Evidence](#evidence)
- [Consequences](#consequences)
- [Reversibility](#reversibility)
- [Review trigger](#review-trigger)
- [Filled example](#filled-example)
- [Context](#context-1)
- [Decision](#decision-1)
- [Alternatives considered](#alternatives-considered-1)
- [Evidence](#evidence-1)
- [Consequences](#consequences-1)
- [Reversibility](#reversibility-1)
- [Review trigger](#review-trigger-1)

Purpose: capture one decision that is expensive to unwind, with the constraint that drove it and the
evidence behind it, so future readers can challenge the reasoning instead of guessing. Required for
low-reversibility decisions (datastore, service split, native boundary, public API shape) per
[Evidence Rules](../core/evidence-rules.md) §7; high-reversibility choices need only a line of rationale
in the PR.

When to use: when [Decision Model](../core/decision-model.md) says **Rev: low**, when a rejected
alternative keeps getting re-proposed, or when a trade-off will otherwise be rediscovered painfully.
One ADR = one decision. Keep to one page.

---

## Fill-in structure

# ADR-NNN: <decision as a short imperative title>

**Status:** Proposed | Accepted | Superseded by ADR-NNN | Deprecated
*Accepted is the default once merged; superseding keeps history visible.*

**Date:** YYYY-MM-DD · **Deciders:** <who owned the call>

## Context
*What situation forced a decision? Name the **dominant constraint** (§0 of the Decision Model) and the
facts that were true at the time. Two paragraphs max. The context must be enough to see why "do
nothing" was not an option.*

## Decision
*One paragraph, imperative: "We will X." State what was chosen, not a list of possibilities.*

## Alternatives considered
*Each alternative: one line of what it is, then the specific reason it lost — cost, risk, missing
evidence, wrong constraint fit. "Not best practice" is not a reason.*

## Evidence
*What backs the decision: repository facts, measured numbers, pinned-version docs, team/deploy topology.
Tag the layer ([ECOSYSTEM], [HEURISTIC]…) per [Evidence Rules](../core/evidence-rules.md) §2. If a key
rests on inference, say so.*

## Consequences
*Good AND bad. The costs are the part future readers need most: what becomes harder, what new failure
modes arrive, what this locks in. Include who pays the cost if it's not the deciding team.*

## Reversibility
*High / medium / low — and what the reversal would actually cost (data migration? API break? team
retraining?). Name the cheapest reversal path now, while nobody needs it.*

## Review trigger
*A date OR a metric ("when team > 8 services", "when p95 > 300ms measured", "when second consumer
appears"). "We'll revisit later" is not a trigger. Decisions without triggers become archaeology.*

---

## Filled example

*Illustrative example only: replace its names, values, and reported outcomes with project evidence.*

# ADR-007: Keep the modular monolith instead of splitting billing into a service

**Status:** Accepted · **Date:** 2026-09-29 · **Deciders:** backend team (3 engineers)

## Context
Billing code grew inside the main Django app (2 modules, ~4k LOC). Two "split billing into its own
service" proposals appeared this year. Dominant constraint: **correctness risk over money paths** with
a 3-person team that deploys once a week; there is no independent scaling or ownership need yet.

## Decision
We keep billing as modules inside the monolith, with a hard import boundary (billing imports nothing
from views; nothing outside billing touches its tables directly).

## Alternatives considered
- **Billing microservice:** lost — would introduce network partial failure and dual writes across the
  money path with no compensating independence (same team, same deploy cadence, same DB).
- **Shared library extracted now:** lost — one consumer; extraction adds versioning cost with no isolation
  benefit (I11). Revisit with the trigger below.

## Evidence
Deploy/ownership topology (same team, one repo, one weekly release) — [ECOSYSTEM]/[HEURISTIC].
Error budget shows 0 incidents from module coupling; 3 from data-model changes (which a service split
would have made worse via sync calls). Independent scaling has not been required by the current workload;
a capacity test would be needed before using throughput as an argument for a split.

## Consequences
+ Billing-table updates stay in one database transaction boundary (I7); an external payment gateway
  still needs its own idempotency and unknown-outcome handling.
− Billing deploys ship with the whole app; blast radius of a bad deploy is the monolith.
− If a second team ever owns billing, they share our release train until the trigger fires.

## Reversibility
Low-medium: reversal = extracting modules + moving tables + compatibility layer. Cheapest path is
strangler-style extraction behind the existing module interface (the import boundary already hides call
sites).

## Review trigger
When a second team needs to own billing, OR measured billing load forces independent scaling, OR
weekly deploy cadence becomes a stated billing requirement — whichever first. Checked quarterly.

---

*Scale note: a routine reversible choice (rename, small refactor, local pattern) does NOT get an ADR —
a two-line rationale in the PR is the right depth. Reserve this template for calls where being wrong is
expensive.*
