# Version 1.5.0

- **Skill:** senior-python-engineer
- **Version:** 1.5.0
- **Prepared and published:** 2026-10-26
- **Publication:** source and evaluations pushed to `cl0udz1/senior-python-engineer`; verified import commit `096087745ef300203b1ed01de66e3a22f6be7c69`
- **Installation:** copy only the runtime directory to the agent host. Publishing this repository does not itself install or activate the skill in a user's local environment.
- **Imported baseline:** 1.4.0, preserved in the original user archive
- **Original archive SHA-256:** b8cd6fcf774e5a3da08426929903cd264f8dbb9e85768a9587bdf45a9394b787
- **Current operational guidance:** [runtime entry point](../../senior-python-engineer/SKILL.md)
- **Historical versions:** [versions through 1.4.0](research/history/versions-through-1.4.0.md)

## Changes

1. Corrected language, asyncio, multiprocessing, Windows subprocess, SQLAlchemy, fixture-cleanup,
   and tool-maintenance guidance, with primary links and scoped claims.
2. Separated EXPLAIN, REVIEW, DESIGN, and IMPLEMENT completion. BLUEPRINT is DESIGN; risk changes
   analysis depth without adding authorization. Updated all domain playbooks and output templates.
3. Reduced the entry point to a routing contract, removed mandatory core-file read chains,
   centralized the specialist review contract, and added contents navigation to long operational files.
4. Rewrote the migration example around writer/read authority, old-writer retirement, reconciliation
   of stale populated values, compatible dual writes, and explicit rollback-window closure.
5. Separated runtime instructions from maintenance, historical research, public evaluations,
   grader code, reference solutions, and validation tools. Excluded the verbatim third-party book.
6. Corrected public evaluation oracles and added executable development fixtures, artifact grading,
   explicit adjudication, an A/B/C pilot planner, activation cases, and a holdout lifecycle.
7. Added offline package/link/anchor/invariant checks, reproducible runtime builds and checksums,
   source-register checks, and deterministic Python mechanism regressions.

## Validation and scope of evidence

See [release verification](RELEASE_VERIFICATION.md) for the original preparation commands, outcomes,
environments, and fresh-agent observations. Its installation-status statements describe that earlier
snapshot. See [publication verification](validation/publication-2026-10-26/README.md) for the recovered
source checks, and the repository's Validate skill workflow for ongoing package and fixture checks.

Passing an official metadata check, package checks, semantic probes, or reference-solution tests does
not establish automatic host activation or comparative agent-quality gain. Current source verification
covers the corrected claims in the registers; unchanged material is not blanket re-certified by this
release date. The restored-source inventory records the pre-publication source, before the root README,
this publication-status update, and the GitHub validation workflow.

## Update policy

- Keep release/maintenance snapshots in the runtime's modern Python baseline. Keep repository
  compatibility policy separate from upstream availability and upgrade recommendations.
- Update the canonical claim, dependent summaries, source register, and affected development oracles
  together. Record version/platform conditions and a meaningful review trigger.
- Run the relevant package and outcome checks after changes. Preserve failed runs and limitations.
- Use actual host telemetry for tokens/cost. File bytes and word counts are not token usage.
- For comparative claims, freeze the conditions, blind outcome review, pair at task level, and use
  new untouched tasks after any holdout-driven change. Public cases remain development material.
