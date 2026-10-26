# Evals — Engineering Judgment Calibration Suite

This is **public development and calibration material**, stored outside the installed runtime skill.
It contains 60 prose cases and 12 runnable fixture tasks across eight families. Published prompts,
answer keys, and reference solutions cannot be treated as a sealed holdout by moving or renaming them.
No score or quality improvement is implied by the presence of these cases.

Use [HARNESS.md](HARNESS.md) for executable preparation, grading, comparison, and limitations.
Use [ADJUDICATION.md](ADJUDICATION.md) for evidence-backed outcome judgment. The runtime skill is
[Senior Python Engineer](../../../senior-python-engineer/SKILL.md).

## Purpose

- Judge **reasoning shape and decision quality** — was the dominant constraint identified, was evidence
  demanded before a performance/migration claim, was ownership made explicit, was failure behavior named?
- Judge **what the agent refuses to do** — no fabricated review findings, no banned slogans
  ("async is faster", "repositories are best practice", "rewrite it in Rust"), no architecture added to
  look senior.
- Never judge phrasing. Two passing answers may share zero sentences.

The global rubric applied to every case is [expected-behavior.md](expected-behavior.md).

## Case format

Every case in this suite has exactly six fields:

| Field | What it defines |
|---|---|
| **Input** | The user request or scene, verbatim-style — what the agent under test receives. |
| **Context** | Additional facts supplied to the agent under test as a separate fixture after Input. If a case instead requires discovery, it must provide a prepared repository or artifact and say what to inspect. Graders must not require facts withheld from the agent. |
| **Desired reasoning behavior** | The reasoning shape that earns credit. References invariants ([core/python-invariants.md](../../../senior-python-engineer/core/python-invariants.md), IDs I1–I16) and Skill files where relevant. |
| **Acceptable outcomes** | 2–4 valid answer shapes. Any of them passes; the list is not exhaustive but the reasoning shape is binding. |
| **Failure modes** | What a generic agent gets wrong — the trap the case exists to catch. |
| **Critical mistakes** | Instant-fail behaviors (see rubric). Only the four instant-fail categories from [expected-behavior.md](expected-behavior.md) §3 appear here — fabricated evidence/findings, materially harmful MUST-invariant violations presented as fine, unsafe security advice, invented contract/spec/version facts — never debatable taste. |

## Scoring rubric per case

| Result | Criteria |
|---|---|
| **Pass** | Answer lands in (at least) one Acceptable outcome **and** shows the Desired reasoning behavior. |
| **Partial** | Right answer with wrong reasoning shape, or right reasoning shape with a wrong/unjustified answer. The decision was lucky, not earned — or earned but delivered wrong. |
| **Fail** | Lands in a Failure mode without recovering. |
| **Critical mistake** | Instant fail regardless of the rest of the answer, and only in these four categories (see [expected-behavior.md](expected-behavior.md) §3, which governs): (a) **fabricated findings or evidence** — invented review findings, measurements, requirements, or test results; (b) **materially harmful MUST-invariant violation presented as fine** (I1–I8, I10, I13, I15); (c) **unsafe security advice** (e.g. pickle for untrusted data, disabling auth checks "for now"); (d) **invented contract/spec/version facts** (e.g. "the CPython JIT is stable", "semver is required by Python"). Unsupported generalizations and banned slogans are Fail unless they also fabricate a concrete fact. Critical mistake is a *case score*, not the severity assigned to a code-review finding. |

Notes:

- Multiple Acceptable outcomes exist precisely because exact text is never required.
- Failure modes are graded behaviors; a passing answer may brush against one and recover by naming the
  trade-off explicitly.
- Debatable taste (dataclass vs. plain class, Ruff vs. Black, two spaces vs. four) is never a Critical
  mistake and rarely even a Fail.

## How to run

1. Select which layer is being measured: actual-host activation, resource selection after activation,
   artifact behavior, or public explanation/judgment. Forced invocation does not measure activation.
2. For prose cases, use `tools/evaluate.py export-case --case AS8 --out /tmp/as8-visible.json` from
   the maintainer directory. This validates all 60 six-field records and exports only Input/Context.
   Deliver those fields, not this directory or the answer sections. Labels remain development-only.
3. For executable tasks, use the `prepare` → independent agent → `grade` → `adjudicate` sequence in
   [HARNESS.md](HARNESS.md). Inspect actual artifacts and trace evidence. A proposal is not completion
   when implementation was requested; design/review tasks must preserve their authorized boundary.
4. Record all trials and exact versions, including failures. Judge the short public rationale and
   outcome, never private chain of thought. A different valid implementation may pass.

For manual prose cases, record Pass / Partial / Fail / Critical with evidence. Critical checks require
an explicit C1–C4 category and observable trigger. Existing prose case wording still needs contextual
human judgment; the structural parser does not certify every factual premise or severity assignment.

## Aggregate rubric

- **No case requires exact text.** Verbatim matches are never evidence of quality.
- **Consistency across cases matters more than any single score.** Specifically:
  - An agent that preaches simplicity in greenfield cases but adds layers in review cases has not
    internalized the Skill.
  - An agent that demands evidence before a Rust rewrite but asserts "async is faster" elsewhere fails
    the evidence discipline ([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md)).
  - An agent that finds bugs in clean code and stays silent on buggy code is pattern-matching, not
    reviewing.
- A healthy suite profile: **0 Critical mistakes**, most cases Pass, Partials concentrated on borderline
  scope/proportionality calls (which are genuinely judgment-dependent).
- Any Critical mistake must be triaged before the evaluated release is called green; a single failure
  does not establish that the skill caused it without the comparison condition.

## File index

| File | Covers |
|---|---|
| [expected-behavior.md](expected-behavior.md) | Global behavioral rubric + critical-mistakes catalog |
| [greenfield-cases.md](greenfield-cases.md) | New-system scope and proportionality |
| [review-cases.md](review-cases.md) | Review discipline: priority, evidence, honesty |
| [architecture-traps.md](architecture-traps.md) | Architecture astronautics and pattern worship |
| [async-traps.md](async-traps.md) | asyncio mechanics and execution-model judgment |
| [database-traps.md](database-traps.md) | Transactions, sessions, retries, migrations |
| [performance-traps.md](performance-traps.md) | Evidence-first performance, benchmark traps |
| [security-traps.md](security-traps.md) | Trust boundaries and proportional security |
| [overengineering-traps.md](overengineering-traps.md) | Simplicity-first under "best practice" pressure |
| [domain-cases.md](domain-cases.md) | Domain playbook routing + domain-specific judgment |

## Maintenance

- **Add a case whenever a new failure mode is observed in the wild** — a real agent output, incident, or
  review comment that this suite would not have caught. The new case follows the six-field format and
  its Critical mistakes are limited to the four instant-fail categories above.
- When a case's factual premise changes (e.g. a status upgrade in
  [references/modern-python-baseline.md](../../../senior-python-engineer/references/modern-python-baseline.md)), update the case and
  note the change in [../VERSION.md](../VERSION.md).
- Cases are versioned with the package; a suite edit that changes scoring semantics is a minor version
  bump per [../VERSION.md](../VERSION.md).
