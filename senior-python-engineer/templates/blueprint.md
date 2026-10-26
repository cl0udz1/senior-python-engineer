# Blueprint — New-System Design Doc

## Contents

- [Scale-to-size rule (prominent for a reason)](#scale-to-size-rule-prominent-for-a-reason)
- [1. Requirements](#1-requirements)
- [2. Dominant constraints](#2-dominant-constraints)
- [3. Trust boundaries](#3-trust-boundaries)
- [4. State](#4-state)
- [5. Ownership](#5-ownership)
- [6. Lifecycle](#6-lifecycle)
- [7. Domain concepts](#7-domain-concepts)
- [8. Module / component boundaries](#8-module--component-boundaries)
- [9. Execution model](#9-execution-model)
- [10. Persistence model](#10-persistence-model)
- [11. Failure semantics](#11-failure-semantics)
- [12. External interfaces](#12-external-interfaces)
- [13. Observability](#13-observability)
- [14. Test strategy](#14-test-strategy)
- [15. Tooling (chosen last, enough to be justified)](#15-tooling-chosen-last-enough-to-be-justified)
- [16. Unresolved decisions](#16-unresolved-decisions)
- [17. Architectural invariants](#17-architectural-invariants)
- [Filled fragment (a payment-webhook worker — steps 2, 5, 11 at depth, rest abbreviated)](#filled-fragment-a-payment-webhook-worker--steps-2-5-11-at-depth-rest-abbreviated)

Purpose: turn a new-system request into a design where requirements, boundaries, ownership, and failure
behavior are decided *before* tooling. Select from the 17 design prompts below according to the requested scope.
BLUEPRINT is an alias for DESIGN in [task modes](../SKILL.md#task-modes). Judgment inputs: [Decision Model](../core/decision-model.md),
[Invariants](../core/python-invariants.md), [Failure Modes](../catalogs/failure-modes.md).

## Scale-to-size rule (prominent for a reason)

**Scale depth to project size and risk.** A one-file utility gets a few sentences total — fill maybe
steps 1, 2, 8, 15 and skip the rest with one line saying so. A library gets steps 1–8 + 12 + 14–17.
Only a multi-team, long-lived, or data-critical system earns every step at full depth. If the document
outweighs the code it describes, the template has been misused — that is on the author, not the project.

Use for DESIGN/BLUEPRINT requests, greenfield services, or a major new subsystem. In an existing repo,
inspect the affected context and consult the relevant [Existing Codebase](../playbooks/existing-codebase.md)
section if needed. Complete a design with decisions, assumptions, risks, and proposed acceptance checks;
scaffolding, dependency installation, test execution, and deployment belong to implementation scope.

---

## 1. Requirements
*What must this do, for whom? What is explicitly out of scope? Quantify where it matters (volume, latency, users).*

## 2. Dominant constraints
*Which constraint or small set of constraints governs this design — correctness risk, latency, throughput, team size, delivery speed, ops budget, compliance? Explain the trade-offs it drives.*

## 3. Trust boundaries
*Where does untrusted data enter (network, files, user input, inter-service, storage)? Where is it validated (I1)? What crosses an authn/authz boundary?*

## 4. State
*What mutable state exists? What is stored vs derived vs transient? Which state is shared (I4)?*

## 5. Ownership
*For each piece of mutable state and each resource: who is the single owner? Who may read it? Ambiguous ownership is an architectural smell — resolve it here or it resolves itself in production.*

## 6. Lifecycle
*Process/task/session/connection lifetimes: what starts what, what shuts down what, in what order (I2)? Startup must fail fast on bad config; shutdown must drain (see [Failure Modes](../catalogs/failure-modes.md)).*

## 7. Domain concepts
*The 3–8 nouns and verbs that actually matter. Their invariants. Keep it small — a domain model is not a noun census.*

## 8. Module / component boundaries
*What are the modules, and what named problem does each boundary solve (I11)? Dependency direction: which way do imports point? What is deliberately NOT a separate component?*

## 9. Execution model
*CPU-bound or wait-bound? How many concurrent waits per process? Sync, threads, asyncio, processes, workers — justified via [Decision Model](../core/decision-model.md) §1, not fashion. Who guarantees no blocking call reaches the loop (I5)?*

## 10. Persistence model
*What store, and why that one? Transaction boundary at the use-case level (I7); ORM vs SQL is conditional; session ownership (session-per-thread / AsyncSession-per-task). Migration/evolution strategy for the schema.*

## 11. Failure semantics
*For each boundary, the relevant "what happens if…" subset and the answers: retries + idempotency (I8), partial success, cancellation residue (I6), what must never be retried. Copy the answered subset, not the whole checklist.*

## 12. External interfaces
*APIs/CLIs/events/messages consumed and produced. Contracts, versions, compatibility policy. Which calls have timeouts and deadlines?*

## 13. Observability
*What must be knowable in production: logs (what fields), metrics (what SLIs), traces (which boundaries)? What alert fires on which symptom? See [Observability](../references/observability.md).*

## 14. Test strategy
*What behavior actually needs confidence, at which tier (unit/integration/contract/e2e)? What is deliberately not tested? Risk-proportional, mock-light ([Testing](../references/testing.md)).*

## 15. Tooling (chosen last, enough to be justified)
*Framework, libraries, deployment target — each named with the problem it solves and the alternative it beat. Reuse the repo's incumbent stack on existing projects unless a concrete gap names the migration (evidence rule: [Evidence Rules](../core/evidence-rules.md) §4).*

## 16. Unresolved decisions
*What is deliberately undecided? What is the cheap reversible default until then? What evidence or date triggers the decision? Naming unknowns is strength; hiding them is how blueprints rot.*

## 17. Architectural invariants
*A short list of properties this system must defend (e.g. "payment retries use a gateway-honored key",
"the job can resume after a worker crash"). Choose from actual risks; do not turn the examples into
universal architecture rules. These become review checks for future changes.*

---

## Filled fragment (a payment-webhook worker — steps 2, 5, 11 at depth, rest abbreviated)

*Illustrative example only: replace its names, values, and reported outcomes with project evidence.*

```markdown
## 2. Dominant constraints
Correctness risk (money) dominates; latency SLO is loose (jobs finish < 60s); team = 3.

## 5. Ownership
Job row has one current claimant via conditional-update claim; an expired lease can leave a stale
worker running, so the payment effect still needs the gateway key.
The payment client is owned by the job runner; no shared client state (I4).

## 11. Failure semantics (relevant subset: Q2, Q3, Q7, Q14 of failure-modes.md)
- Runs twice: each job has one stable key that the payment gateway honors for charges (I8);
  `payment_dedupe` records local intent and confirmed outcome.
- Worker dies halfway: a charge may have succeeded without a local result. Redelivery uses
  the same gateway key or queries the gateway to reconcile before marking the job done.
- Never retried: a charge with an unknown outcome and no gateway idempotency or query path;
  hold for reconciliation instead of issuing a fresh charge.

## 15. Tooling
FastAPI already runs the rest of the fleet (incumbent); no new framework. PostgreSQL
already stores jobs — no queue broker until backlog measurements demand one (review trigger:
queue depth > 1k sustained).
```

*Depth calibration: this worker is one service on a 3-person team — 4 of 17 steps at full depth, the
rest one line each. A greenfield payments platform would fill all 17 and link an
[ADR](architecture-decision-record.md) per irreversible choice.*
