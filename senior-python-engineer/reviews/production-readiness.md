# Production Readiness

## Contents

- [Scope & trigger](#scope--trigger)
- [Review contract](#review-contract)
- [Procedure](#procedure)
- [Checklist](#checklist)
- [Decision](#decision)
- [Finding format](#finding-format)
- [False positives / legitimate exceptions](#false-positives--legitimate-exceptions)
- [Output expectations](#output-expectations)

The ship gate ([SHIP] task): is this system safe to run unattended, and what breaks first under load?
Output maps to [templates/production-readiness.md](../templates/production-readiness.md) and ends in an
explicit decision: **GO / GO-with-conditions / NO-GO** with reasons. Design questions live in
[architecture-review.md](architecture-review.md); this review judges the system as it will actually run.

## Scope & trigger

Use when: a service/worker/pipeline is about to be deployed or exposed to real traffic; a release
changes schema, config, topology, or dependencies; an incident review demands readiness gaps
([templates/failure-review.md](../templates/failure-review.md) for the postmortem itself); or someone
asks "can we ship this?". Re-run after major changes — readiness is perishable.

## Review contract

Follow the shared [review contract](code-review.md#review-contract) for task scope,
priority, severity, evidence, finding format, and a valid clean-review outcome.

## Procedure

1. **Name the load expectation and service objective.** Use measured traffic when available, or an
   explicit capacity estimate and review trigger for a new system. Grade gaps by the expected load.
2. **Walk the boundary failure questions** ([failure-modes](../catalogs/failure-modes.md), I14): DB
   gone, dependency timeout, duplicate job, worker dies mid-job, shutdown now, queue grows, disk full,
   schema change, partial success. Each must have an answer in the system, not in the slide deck.
3. **Verify timeouts/retries/idempotency end to end (I8).** Trace one request and one background job
   from entry to side effect: which calls have deadlines, what retries, and what happens if the retry
   duplicates the effect.
4. **Verify graceful shutdown and queue drain** ([reliability.md](../references/reliability.md)):
   in-flight requests/jobs complete within the termination budget, connections close (I2), nothing is
   silently dropped or double-consumed.
5. **Check probes and process topology**: liveness vs readiness distinguished; worker counts measured
   against CPU/memory/pool limits, not formulaic.
6. **Check the config/secrets boundary** and observability ([observability.md](../references/observability.md)):
   logs/metrics/traces on the paths that failed in the failure walk.
7. **Check the operational package**: runbooks, alerts that map to runbooks, rollback plan, and the
   migration plan for any schema change ([templates/migration-plan.md](../templates/migration-plan.md)).
8. **Confirm the specialist reviews** for this system's risk surfaces are done (below), then render the
   decision in [templates/production-readiness.md](../templates/production-readiness.md).

## Checklist

| Check | Mechanism | Evidence to look for |
|---|---|---|
| Load expectations named | Latency/availability objective + expected traffic shape | Measurement or explicit estimate; "should handle production" without a capacity assumption is weak evidence |
| Timeouts (I6, I14) | Calls that can stall the use case have an effective deadline reaching the I/O | Unbounded waits on critical client calls; missing consumer shutdown bound |
| Retries + idempotency (I8) | Every retry answers "can this safely happen twice?" | Non-idempotent effect retried without effect-level idempotency or reconciliation; grade by reachable harm |
| Graceful shutdown + queue drain | In-flight work completes or has a safe redelivery/recovery path within the termination budget | SIGTERM handling in workers ([reliability.md](../references/reliability.md)); material loss or harmful duplication on deploy blocks ship |
| Liveness vs readiness probes | Readiness removes from traffic; liveness restarts; liveness not used as load shedding | One probe doing both; aggressive liveness under overload causing cascading restarts [FRAMEWORK/ECOSYSTEM] |
| Config/secrets boundary (I15) | One validated settings boundary; secrets from the secret store, never code/logs/diffs | `os.environ` reads scattered through modules (scattered-config smell); secrets in exception text |
| Observability | Logs/metrics/traces cover the failure paths, with context propagation | Error paths with no log; no latency/queue-depth metric; trace context dropped at async boundaries ([observability.md](../references/observability.md)) |
| Runbooks + alerts | Every alert maps to a documented action | Page-worthy alert with no runbook; runbook for a condition nobody is alerted on |
| Rollback/recovery plan | Prior version can run against current schema/config, or a tested forward/data recovery path exists | A destructive change with no acceptable recovery for its data risk blocks ship |
| Schema migration plan | Compatibility, data preservation, and recovery fit the deployment topology ([templates/migration-plan.md](../templates/migration-plan.md)) | Destructive DDL during a rolling overlap or without adequate data recovery can block ship |
| Capacity / worker counts evidenced | Workers, pool sizes, memory limits checked against measurement or a greenfield estimate | "2× cores + 1" copied as a final answer; pool demand exceeding available connections ([performance-review](performance-review.md)) |
| Dependency review done | [dependency-review.md](dependency-review.md) run for the release's dependency delta | New deps shipped unreviewed |
| Security review done | [security-review.md](security-review.md) applied to relevant trust boundaries and release changes | Reachable high-impact auth/credential surface unreviewed can block ship |
| Resource lifecycle (I2) | Connections/files/processes released on all paths incl. failure and shutdown | Leaks under error paths; reliance on GC timing for cleanup |

## Decision

The output ends with exactly one of:

- **GO** — release-blocking safety properties are verified; known residual risks are accepted with
  named owners.
- **GO-with-conditions** — no material release-blocking risk remains; bounded residual gaps have a
  compensating control or monitoring watch. Each condition names an owner, deadline, and check.
- **NO-GO** — a reachable material risk remains unmitigated or unverified (for example data loss,
  unavailable rollback after a destructive migration, auth bypass, non-idempotent payment retry).
  Reasons cite the specific finding.

A NO-GO is a normal outcome, not a failure of the review. Equally: a GO with a fabricated finding list
is worse than a short honest one.

### Example decision block (shape only)

- **Decision: GO-with-conditions** — service `billing-api`, release 2026.09.
- **Reasons:** the payment retry and rollback paths are verified; no material release-blocking gap
  remains. Readiness and liveness have distinct behavior under the expected burst.
- **Conditions:** (1) owner=team lead, deadline=ship+24h: link the existing `DB pool exhaustion` alert
  to its runbook; verify the alert definition points to it. (2) owner=platform, deadline=ship+48h:
  review the first burst's pool-wait metric and adjust the capacity estimate if needed.

## Finding format

Per [templates/code-review.md](../templates/code-review.md):
`Severity:` `Evidence:` `Why it matters:` `Recommended change:` `Trade-off:` `Verification:`.

Invariant strength does not set severity or automatically decide GO/NO-GO
([invariants](../core/python-invariants.md#using-these-in-reviews)). Judge the reachable failure and its
impact; a material unverified failure path blocks GO. Evidence can be config values, probe definitions,
load tests, log/metric excerpts, or runbooks — never "should be fine".

## False positives / legitimate exceptions

- **A small internal tool does not need the full SRE package** — SLOs can be "finish before the analyst
  returns"; alerts can be the exit code ([principles §7](../core/engineering-principles.md)).
- **Missing multi-region, chaos engineering, or auto-scaling** is never a finding by itself; distribution
  needs its own justification ([architecture-review](architecture-review.md)).
- **A database with automated backups and a tested restore** is a rollback plan; don't demand
  blue-green ceremony for a CLI job.
- **Readiness-only deployments** (batch jobs with no traffic) legitimately have no readiness probe; the
  requirement is the correct shutdown/exit semantics.
- **Alert volume discipline**: not every metric needs an alert; finding quality beats alert count.
- **"Worker count looks high/low" without load evidence** is an assumption, not a finding
  ([evidence-rules §3](../core/evidence-rules.md)).

## Output expectations

- Use [templates/production-readiness.md](../templates/production-readiness.md): checklist result per
  item, findings in priority order, then the **GO / GO-with-conditions / NO-GO** decision with reasons.
- "No significant issue found." is a valid result for any checklist section — and a GO with genuinely
  short findings is better than padded ones. Never fabricate findings to appear thorough.
- Every condition of a GO-with-conditions names an owner, a verification step, and a deadline.
- State what was verified versus assumed ([evidence-rules §6](../core/evidence-rules.md)) — an unverified
  timeout claim is an assumption, and readiness decisions must not rest on silent assumptions.
- Keep the checklist result even when everything passes: an empty section with "verified, no issue"
  is the evidence that the item was checked rather than skipped.
