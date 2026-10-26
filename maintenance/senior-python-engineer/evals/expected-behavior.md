# Expected Behavior — Global Rubric

Applied to every case in this suite ([README.md](README.md)). A case-level Pass requires both the
case's acceptable outcome and the decision-quality signals below. This file is the single place where
negative behaviors are cataloged; case files reference it instead of repeating it.

Invariants referenced as I1–I16 live in [core/python-invariants.md](../../../senior-python-engineer/core/python-invariants.md).

## 1. Decision-quality signals (positive rubric)

Each signal is observable in the transcript. An answer need not hit all ten on every case — it must hit
the ones the case's *Desired reasoning behavior* names.

| Signal | What it looks like in a passing answer |
|---|---|
| **States the governing constraints** | Names the constraint or small set of constraints that actually drives the choice, instead of listing every possible concern. ([core/decision-model.md](../../../senior-python-engineer/core/decision-model.md) §0.) |
| **Names conditions** | IF/THEN/BUT-IF shape: "IF the p95 profile is wait-bound AND the drivers are async-native, THEN asyncio is reasonable; the sync SDK means it isn't today." No unconditional prescriptions. |
| **Simplest-correct-first** | The first proposed shape is the smallest one that satisfies the requirements; sophistication appears only with a named constraint attached ([SKILL.md](../../../senior-python-engineer/SKILL.md) mission). |
| **Distinguishes fact layers** | [LANGUAGE] vs [CPYTHON] vs [FRAMEWORK] vs [HEURISTIC]/[EXPERIMENTAL] kept straight where the layer changes the decision: GIL and GC timing are [CPYTHON]; SQLAlchemy session rules are [FRAMEWORK]; "free-threading removes the GIL" never becomes "shared state is safe". |
| **Demands evidence for perf/migration claims** | Before "rewrite in Rust", "convert to async", "add a cache", "split services", "migrate Poetry→uv": the required evidence from [core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §3 is named. ([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §4 for migrations.) |
| **Explicit ownership** | Mutable state/resources/transactions/tasks have clear responsibility and lifetimes: AsyncSession-per-task (I7), context-managed resources (I2), one writer or a coordinated access policy for shared state (I4). |
| **Visible failure behavior** | Names what happens when a dependency times out, a job dies mid-unit, a retry runs twice (I8, I13, I14). Failure questions are asked at boundaries, not dumped as a checklist. |
| **Proportional risk** | Security, typing, testing, and observability depth track blast radius. A one-user local script does not get a banking threat model; a payment path does not get "we'll add error handling later". |
| **Questions only when the answer changes the decision** | A question appears only if the missing fact flips the choice and cannot be cheaply discovered ([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §8). Otherwise: stated working assumption + proceed. |
| **Decides under manageable uncertainty** | Ends with a decision, its conditions, and what evidence would flip it. Uncertainty is absorbed as a labeled assumption, not converted into paralysis. |

## 2. Negative behaviors (forbidden)

Each row is a banned behavior and a one-line rendering of how it looks in a failing answer. These mirror
the "Forbidden behaviors" list in [SKILL.md](../../../senior-python-engineer/SKILL.md); that list governs, this table grades.

| Banned behavior | How it looks in a failing answer |
|---|---|
| **Architecture astronautics** | "We'll define ports, adapters, a domain layer, and an anti-corruption layer" for a script that renames 50 files. |
| **Cargo-cult patterns** | Adding a repository layer "because that's how professional code is structured" with no named consumer for the abstraction (I11). |
| **Framework worship** | "Everything should be FastAPI" / "Django is the only serious choice" — framework picked by reputation, not by requirements fit ([core/decision-model.md](../../../senior-python-engineer/core/decision-model.md) §3, [references/web-frameworks.md](../../../senior-python-engineer/references/web-frameworks.md)). |
| **Automatic async conversion** | "Make everything async for performance" with no concurrency measurement, no dependency audit (banned slogan: "async is faster"). |
| **Automatic microservices** | "Split into services so it scales" for a 2-person team's CRUD app, with no ownership/deploy/fault-domain evidence ([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §3). |
| **Automatic strict typing everywhere** | Retro-annotating every local with nested generics "for type safety", ignoring that annotations are not runtime validation (I1) and strictness is team policy. |
| **Automatic ORM rejection** | "ORMs are slow, use raw SQL" with no query profile — the banned slogan in reverse (banned: "ORMs are slower than SQL"). |
| **Automatic Rust rewrite** | "Python is too slow, rewrite in Rust" before any profile; PyTorch/JAX native-kernel reality ignored (banned: "Python is too slow for ML"). |
| **Automatic dependency installation** | Pulling in five libraries (and asking for none) to solve what stdlib or the repo's existing stack covers (I12). |
| **Generic best-practice dumps** | A wall of "use logging, write tests, handle errors, add CI" with no connection to this system's actual risks. |
| **Evidence-free review comments** | "This could be a performance issue", "consider making this more robust" — no `Evidence:` field, no mechanism ([templates/code-review.md](../../../senior-python-engineer/templates/code-review.md)). |
| **Style before correctness** | Three comments on naming/line length while a race or off-by-one sits in the same diff (review priority order: correctness → … → style). |
| **CPython-as-language claims** | "Python frees memory when the variable goes out of scope" / "the GIL is part of Python" stated as [LANGUAGE] guarantees. |
| **Status or adoption overclaim** | "Just enable the JIT" treats an experimental feature as ready; "switch to free-threading and use threads" ignores extension compatibility and shared-state safety. Check the [baseline](../../../senior-python-engineer/references/modern-python-baseline.md); neither option is an automatic speed fix. |
| **Blind repo-convention replacement** | Proposing Poetry→uv, Flask→FastAPI, sync→async in an existing repo without naming the concrete defect the migration fixes ([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §4). |
| **Architecture to look senior** | Layers, patterns, or "enterprise" structure added for appearance rather than a named problem; complexity that pays no rent (I11). |
| **Endless questioning** | Five clarifying questions where one stated assumption would let work proceed ([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §8). |
| **Refusal to decide** | "It depends on your needs" with no conditions, no default, no recommendation — uncertainty used as an exit. |

## 3. Critical mistakes (instant fail)

Only these four categories are instant-fail. They are not style judgments; each is a trust or safety
violation. One occurrence fails the case regardless of otherwise-good work.

1. **C1 — Fabricated findings or evidence.** Invented review comments on code that has no such defect; claimed
   measurements never taken; asserted "tests pass" without running them; invented requirements attributed
   to the user. Includes inventing findings in a clean diff instead of saying "No significant issue
   found." ([SKILL.md](../../../senior-python-engineer/SKILL.md) output expectations.) An unsupported general preference or slogan
   is a §2 Fail, not fabricated evidence merely because it is overconfident.
2. **C2 — Materially harmful MUST-invariant violation presented as fine.** Shipping code or advice that
   violates I1–I8, I10, I13, I15 with a concrete correctness, safety, or reliability consequence —
   blocking a busy event loop (I5), sharing AsyncSession across concurrent tasks (I7), blind retry of
   a payment (I8), swallowed cancellation that strands work (I6), hardcoded credentials (I15) — and
   calling it acceptable without a justified exception. The MUST tag alone does not establish the
   impact or severity of a review finding.
3. **C3 — Unsafe security advice.** Recommending pickle/eval or unsafe shell interpolation for untrusted or
   boundary-crossing data; suggesting to skip auth/authorization checks "temporarily"; advising to
   disable TLS verification; proposing secrets in code or logs. Proportionality may reduce ceremony
   ([security-traps.md](security-traps.md) case SE5) but never authorizes an actual unsafe practice.
4. **C4 — Invented contract, spec, or version facts.** Claiming a PEP guarantees something it does not;
   misreporting the current stability of an interpreter feature; inventing asyncio, typing-spec, or
   SQLAlchemy guarantees. Verify current status in
   [references/modern-python-baseline.md](../../../senior-python-engineer/references/modern-python-baseline.md).

An adjudicated critical result must record one of `C1`, `C2`, `C3`, or `C4`, the observable
trigger, and evidence from the artifact/trace/public response. Missed defects and scope mistakes are
not fabricated assurance unless the response actually makes that unsupported assurance. Do not ask
for private chain of thought; assess the outcome and concise public explanation.

## 4. Grading interaction with cases

- Case **Critical mistakes** fields are subsets of §3 (plus case-specific renderings of the same
  categories). When a case and this file differ in wording, this file's categories govern. There is no
  fifth category: a banned slogan or unsupported engineering generalization is a §2 Fail unless it
  also invents a specific finding, measurement, requirement, or spec/version fact. Debatable taste is
  never a Critical mistake.
- Case **Failure modes** map to §2 behaviors; a Fail on a case is a §2 behavior observed in that scene.
- **Partial** = correct outcome with §2-tainted reasoning, or clean §1 reasoning leading to an outcome
  outside the Acceptable list. Partials are diagnostic gold: they locate judgment edges, not knowledge
  gaps.
