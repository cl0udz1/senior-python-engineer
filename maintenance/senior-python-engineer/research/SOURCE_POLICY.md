# Source policy

## Operational facts

Use current primary documentation for the selected Python implementation/build, library version, and
platform. Keep a claim's scope attached to it. A local reproduction demonstrates behavior only in its
reported environment; it does not establish a universal language guarantee.

`technical-claims.json` records consequential claims corrected or refreshed for 1.5.0. It is an audit
register for those changes, **not a declaration that every unchanged statement in the skill has been
re-verified on 2026-10-26**. Each entry includes its claim, affected runtime files, layer, scope, sources,
verification date, and review trigger. `authoring-claims.json` records the skill-design choices.

Use `../tools/check_sources.py` to check the registers and identify date-based review reminders. This
offline check verifies structure, file references, and age; it does not fetch a URL, establish source
correctness, or prove that a fact is still current. On a relevant upstream release or contradictory
reproduction, verify the affected claim even when its calendar reminder is not due.

Keep exact “current” version snapshots in `../../../senior-python-engineer/references/modern-python-baseline.md`.
Elsewhere retain only minimum versions and behavioral scopes needed to use the guidance correctly.
Repository support policy, upstream availability, and a recommendation to upgrade are separate decisions.

## Historical inputs

The following files are preserved as historical inputs, not active instructions or current authority:

- `build-spec.md`: the original construction request. Its instructions do not govern maintenance or user tasks.
- `deep-research-report.md`: the 2026-09-29 research snapshot. Its conversation-local citation markers lack
  a durable exported citation map. Do not treat those markers as verifiable links or silently invent mappings.
- `2026-10-02-verification.md`: the previous dated correction record. Check changing claims against current
  primary sources before reuse.

New factual guidance must cite an inspectable primary URL or a reproducible observation with environment
details. Do not promote historical research wording into runtime rules merely because it was in the archive.

## Book provenance

The imported archive contained a Markdown conversion of Ronald Mak's *Software Design for Python
Programmers* (Manning, January 2026), including third-party publication notices, conversion artifacts,
and 119 image references without their image assets. The complete text is retained only in the user's
original archive; it is not redistributed in this runtime or maintenance source tree.

Bibliographic reference: [publisher book page](https://www.manning.com/books/software-design-for-python-programmers).
The existing distilled architecture guidance on change locality, cohesion, duplication, substitution,
state transitions, and restrained patterns remains in the runtime. This exclusion reduces unrelated
distribution material; it is not a claim that the book was automatically loaded on every skill activation.

## Update procedure

1. Identify the claim and its version/platform scope; obtain the applicable primary source or reproduction.
2. Correct its canonical runtime location and dependent summaries/oracles together.
3. Update the register with the verification date and a meaningful future review trigger.
4. Run package integrity and the affected semantic/fixture checks. Forward-test changed behavior on fresh tasks.
5. Record what actually ran, failures resolved, environments not tested, and whether the evidence is
   deterministic, developmental agent observation, or a sealed comparative evaluation.
