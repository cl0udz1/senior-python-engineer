# Failure Review — Pre-Mortem

## Contents

- [Fill-in structure](#fill-in-structure)
- [System boundary under review](#system-boundary-under-review)
- [Question bank subset chosen](#question-bank-subset-chosen)
- [Failure scenarios](#failure-scenarios)
- [Gaps found](#gaps-found)
- [Actions](#actions)
- [Filled fragment](#filled-fragment)
- [Post-incident variant](#post-incident-variant)

Purpose: walk a system (or a design) through its relevant failure scenarios *before* production forces
the lesson, and record what happens at each one. Pre-mortem style: assume it *has* failed and ask why.
Operationalizes [Failure Modes](../catalogs/failure-modes.md) and invariants
[I2, I4, I6, I7, I8, I13, I14](../core/python-invariants.md).

When to use: before shipping a new system/subsystem ([Production Readiness](production-readiness.md)
links here), after adding a new boundary (queue, upstream, store), or as a periodic review of a
load-bearing path. Not every module needs this — only code where failure has consequences.

**Usage rule:** ask only the relevant subset of the question bank. Record which subset you chose and
why; a review that dumps all 14 questions mechanically has learned nothing about this system.

---

## Fill-in structure

# Failure review: <system / path under review> — <date>

## System boundary under review
*One paragraph: what this covers (e.g. "ingest path from HTTP receipt to queue ack"), what it does NOT
cover, and the load/traffic shape (approximate rate, payload size). Reviewing an unnamed boundary
reviews nothing.*

## Question bank subset chosen
*List the questions asked (from [failure-modes.md](../catalogs/failure-modes.md) core bank: Q1–Q14) and
one line each on why this question applies here. Note which boundaries were skipped and why (e.g.
"Q9 disk-full not asked: no file writes in this path").*

## Failure scenarios

### S1: <scenario name, e.g. "DB connection lost mid-batch">
**Trigger:** *the concrete event (network blip, deploy, poison input, load spike…).*
**Detection:** *what shows it happened — log line, metric, alert, user report. If nothing: that IS the
finding; state "no detection" explicitly.*
**State at failure:** *what is partially done / in flight / half-written when it hits. Include who owns
the state (I4) and what the transaction boundary leaves behind (I7).*
**Recovery:** *what restores service — automatic (retry with idempotency key I8, failover, drain) or
manual (runbook step). If none: "none — see gap G1".*
**Residual risk:** *what remains wrong even after recovery (stale data window, backlog, duplicated
side effects prevented only by X…).*

*(repeat per scenario — 3–8 scenarios is typical; fewer is fine for small systems)*

## Gaps found
*G-numbered list: each gap = one sentence on what's missing (no detection, no recovery, unbounded queue,
ambiguous owner) + the scenario(s) it exposes. Gaps are the point of this document.*

## Actions
*Each action: the gap it closes, and — owner-less is fine — **each has a verification**: a test name,
command, metric, or date-based review that proves the action happened. Actions without verification are
wishes.*

- A1 (closes G1): <action> — *verify by: <test/step/metric>*

---

## Filled fragment

*Illustrative example only: replace its names, values, and reported outcomes with project evidence.*

```markdown
## Failure scenarios

### S2: Worker crashes after charge, before job ack
**Trigger:** OOM kill or deploy SIGKILL mid-job (~1/10k jobs run 30-60s).
**Detection:** job lease expiry metric + `jobs.redelivered` counter (exists).
**State at failure:** charge succeeded at gateway; job still "processing"; local dedupe row is
uncommitted and will roll back with the transaction (gap G1).
**Recovery:** redelivery after visibility timeout; second worker sees dedupe record... except the
dedupe row was rolled back with the transaction, so the charge repeats.
**Residual risk:** double charge until G1 closes.

## Gaps found
G1: the gateway charge has no gateway-honored idempotency key or reconciliation path; the local
dedupe row rolls back, so redelivery can re-charge (S2). G2: no alert on `jobs.redelivered` > threshold.

## Actions
A1 (closes G1): assign a stable key to the job, pass it to a gateway that honors charge idempotency,
and reconcile an unknown result with that key before ack. Persist local intent/outcome separately;
a pre-charge row alone cannot make the external effect atomic. — verify by:
`test_crash_before_charge` and `test_crash_between_charge_and_ack` (one gateway effect per key).
A2 (closes G2): alert on redelivered > 5/min. — verify by: alert rule present in staging config + fire test.
```

## Post-incident variant

When the failure has already happened, the same skeleton serves as the incident document with one
section swapped:

**Timeline** (facts with timestamps — what was observed when, not what was thought) →
**Contributing factors** (conditions that made the failure possible: missing timeout, no idempotency,
aggressive liveness probe — systems, not names) →
**Systemic fix vs blame**: the output is the same Actions list as above — the fix is a change to the
system (test, bound, alert, invariant), never an admonition to "be more careful". If an action could
only be performed by a more careful human, the design gap is still open.

Severity note: unresolved gaps with reachable consequences are findings in
[Code Review format](code-review.md). Material unmitigated risks block
[Production Readiness](production-readiness.md), whatever the invariant label.
