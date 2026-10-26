# Code Review — Findings Document

Purpose: report review results as evidence-backed, priority-ordered findings a reader can act on or
challenge. This is the output format for all REVIEW tasks ([SKILL.md](../SKILL.md)); severity rules live
in [Invariants](../core/python-invariants.md), priority order in SKILL.md.

When to use: reviewing a diff, a module, or a design artifact. Scale note: a 20-line diff review is
"Summary + findings or 'No significant issue found.'"; a system review gets the full structure.

**Priority order (governs ordering of findings, not vibes):**
1 correctness → 2 security → 3 data integrity → 4 concurrency/state ownership → 5 resource lifecycle →
6 failure behavior → 7 performance → 8 maintainability → 9 readability/style.
Style comments must never hide correctness problems. Never fabricate findings to appear thorough —
**"No significant issue found." is a valid and complete review result.**

---

## Fill-in structure

# Review: <change/area> — <date>

## Summary verdict
**Approve | Request changes | Needs discussion**
*One or two sentences on why. "Needs discussion" is for design disagreements, not defects.*

## Findings (priority-ordered)

### <F1 — short name>
**Severity:** Critical | High | Medium | Low | Advisory
*Grade by plausible impact and reachability, not the MUST/SHOULD label ([python-invariants](../core/python-invariants.md)); reserve Critical for severe reachable harm.*
**Evidence:** *file:line, test output, measured number, doc cite. Findings without evidence are opinions.*
**Why it matters:** *the concrete consequence — user-visible bug, outage class, security surface. Not "this is bad style".*
**Recommended change:** *the specific fix, smallest that removes the mechanism.*
**Trade-off:** *what the fix costs or what it gives up. "None" is rarely true; if truly none, say why.*
**Verification:** *how the reviewer/author proves it fixed — test to run/add, command, metric.*

## Minor notes (style only, after correctness)
*Formatting, naming, local conventions. Only after all correctness/security items. If a "minor" note is
actually a correctness issue, promote it to Findings.*

## "No significant issue found."
*Use this section when applicable: state it plainly. Do not pad with advisory trivia.*

## What was checked vs not checked
**Checked:** *which concerns were examined (imports? concurrency? SQL? auth? tests actually run?).*
**Not checked:** *what is out of scope or unverifiable here (perf under load, dependency provenance,
browser behavior…). Honest scope limits build trust; hidden ones destroy it.*

---

## Sample finding block (evidence-based severity)

*Illustrative example only: replace its paths, values, and reported outcomes with project evidence.*

### F1 — Retry loop duplicates charge calls
**Severity:** High *(reachable double charge on a payment path; I8 identifies the retry risk)*
**Evidence:** `billing/charge.py:88-92` — `for attempt in range(5): try: gateway.charge(...) except
Exception: continue`. `gateway.charge` has no idempotency key (checked `gateway/client.py:31`). Test
`test_charge_retries.py` passes while asserting only the success path.
**Why it matters:** a gateway timeout after the charge succeeded but before the response arrives causes
the next attempt to charge again. Timeout-with-late-success is common on payment gateways; this is a
double-charge path on the money flow (correctness + data integrity).
**Recommended change:** generate `idempotency_key=charge_id` and pass it to `gateway.charge`; retry only
`TransportError`/5xx, max 3 attempts with backoff and a total deadline; on exhaustion, record an
unknown outcome for reconciliation instead of treating it as a failed charge.
**Trade-off:** one extra gateway parameter and slightly slower worst-case failure path (bounded 30s);
must confirm the gateway honors idempotency keys (verify against its pinned docs).
**Verification:** with a fake gateway that honors idempotency keys, test a charge that succeeds but whose
response times out — assert one effect per key and a recorded unresolved result when confirmation fails;
run `pytest tests/billing`.

---

## Depth calibration

| Review size | Right depth |
|---|---|
| 20-line diff | Verdict + findings or "No significant issue found." + what was run |
| Feature/MR | Full structure above |
| System/module | Full structure + link to specialized review ([async](../reviews/async-review.md), [database](../reviews/database-review.md), [security](../reviews/security-review.md)…) as needed |

Invariants identify what to inspect; impact determines severity. Advisory smells use the triage rule in
[smells.md](../catalogs/smells.md) — comment only when the reader's next decision would change.
