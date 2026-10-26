# Version 1.5.0 verification

Prepared on **26 October 2026** from the user's 1.4.0 archive. The operational changes, maintenance
tools, executable fixtures, and five fresh-context development tasks are complete. The evidence below
supports this release's specific corrections and tooling; it does not establish a comparative quality
gain across a task population.

**Installation status:** not installed. Automatic approval review rejected the attempted write to
`/root/.codex/skills/remote-skills` because it is a protected configuration subtree and the user had
not explicitly named that destination or the accompanying maintenance files. No configuration files
were changed by that rejected command. The completed project and validation evidence are retained.

## Verified release contents

| Measure | Result |
|---|---|
| Runtime folder and metadata name | `senior-python-engineer` |
| Runtime files | 55: 54 operational Markdown files and optional `agents/openai.yaml` |
| Entry point | 146 lines, 1,195 whitespace-separated words, 10,130 bytes |
| Original entry point | 221 lines, 1,943 whitespace-separated words, 17,712 bytes |
| Entry-point word reduction | Approximately 38.5 percent |
| Runtime bytes | 633,743 |
| Local links checked | 1,817 occurrences, including heading targets |
| Consequential claim records | 25, including 22 technical corrections and 3 authoring/evaluation policies |
| Public prose cases | 60, each checked for its six required fields |
| Executable development tasks | 12 across 8 families |
| Original archive | Unchanged; SHA-256 `b8cd6fcf774e5a3da08426929903cd264f8dbb9e85768a9587bdf45a9394b787` |

The runtime retains the broad reference coverage. Its operational files are somewhat larger than the
original 593,527-byte operational subset because corrections and section navigation were added; the
entry point is shorter. The original 1,748,184-byte non-Git distribution also contained maintenance and
the full book, so comparing that total with runtime alone measures packaging, not model context savings.
No measured token or latency reduction is claimed.

The tested runtime distribution is identified by the SHA-256 of the exact generated
`runtime-manifest.json` bytes: `0529d391adefdd86cc5a4c407128d893f118893e84967e56097f429f85476980`.
That manifest contains sorted relative paths with file sizes and individual SHA-256 values, plus
static package metrics. The current runtime was compared byte-for-byte with that frozen snapshot.

## Checks actually run

Environment: **CPython 3.12.14 on Linux x86-64**. Tool tests, semantic probes, and fixture graders use
only the standard library. The skill-creator metadata check additionally used the already installed
PyYAML. Exact command outputs are in [validation](validation/verification-index.json).

| Check | Observed result |
|---|---|
| Official skill-creator `quick_validate.py` | Passed metadata validation |
| Project package validator | Passed naming, supported frontmatter format, file policy, local links/anchors, I1–I16 references, and direct resource navigation |
| Package-tool regressions | 8 tests passed, including malformed YAML scalars, contamination, symlinks, escaping/broken links, and safe reproducible copies |
| Evaluation-tool regressions | 11 tests passed, including zero tests and early exit not being accepted as success, immutable preparation, scope, adjudication, paired-report guards, and duplicate rejection |
| Python mechanism probes | 19 checks passed for asyncio ownership/suspension/capacity, language descriptors/operators/imports, native argv, and context-based process startup |
| Fixture machinery | All 9 intentionally buggy starters failed; all 9 reference solutions passed; 3 unchanged design/review fixtures passed structural checks only |
| Reference grader coverage | 31 unittest methods across the 9 implementation fixtures |
| Source registers | 25 structurally valid, dated claims; no review reminders due on the verification date |
| Source-checker negative cases | Outside-runtime paths and invalid source URLs rejected; changing-status claims become due at a later test date |
| Original-source preservation | Uploaded archive hash and every extracted non-Git source file matched the original bytes |

An independent release reviewer found that the first validator revision could approve a description
containing invalid unquoted YAML. The scalar rules and build regressions were corrected before the
final passing run. Review also found an early-exit false-pass risk in the initial evaluator; final
grading requires a completed test record with executed, non-skipped tests. Those fixes do not make
the grader a hostile-code sandbox or tamper-proof judge.

## Five development agent tasks

Each task used a fresh agent context, the frozen candidate skill, and a visible task workspace.
Agents were instructed to read only that task and the skill. Evaluator answers were outside those
directories, but the shared environment did not enforce inaccessible mounts. A separate reviewer
received only the requests and resulting artifacts, without grader keys or candidate version labels.

| Task | Artifact/scope evidence | Independent artifact review |
|---|---|---|
| Architecture-only inventory import | 649-word design; only `response.md` changed; source seed untouched | Pass |
| Async dashboard fallback and cleanup | 5 external behavior tests passed; only solution/response changed | Pass; independent async checks also passed |
| Correct membership helper review | Only response changed; no invented defect or applied fix | Pass; independently checked the nine stated cases |
| Rolling status migration | 4 external behavior tests passed; mixed readers and stale populated values handled | Pass; independent state-sequence checks also passed |
| Narrow legacy lookup fix | 2 external behavior tests passed; unrelated helper preserved | Pass; independent return/signature checks also passed |

The final scope snapshots showed no persisted changes outside the allowed files. These are five
development observations in one candidate condition, not five independent estimates of general skill
quality. The independent reviewer distinguished current-artifact checks from the generating agents'
reported execution histories. Full trusted host traces and token/cost telemetry were not captured.

Two tasks were prepared before the evaluator's completion-attestation fix. Their exact artifacts were
regraded, without substantive editing, against the final evaluator in fresh workspaces. These remain
two original agent trials, not four. See the saved [trial summary](evals/results/forward-2026-10-26/summary.json),
[independent review](evals/results/forward-2026-10-26/independent-review.md), per-case artifacts,
raw results, adjudications, and provenance records. Absolute paths in raw execution records describe
the original session; the copied task artifacts are retained alongside those records.

## What has not been established

- **Comparative quality or cost improvement:** the randomized 108-run A/B/C plan is generated, not
  executed. It represents 12 distinct public tasks with repeated trials, not 108 independent tasks.
  No no-skill/original/revised aggregate is reported from the five candidate-only observations.
- **Unseen-task generalization:** all shipped cases are public development material. No sealed holdout
  is claimed; new untouched tasks and enforced answer isolation are needed for that claim.
- **Automatic activation:** the package format and explicit invocation were checked; implicit host
  routing must be observed separately using the activation cases and host telemetry.
- **Cross-platform/version compatibility:** Python 3.14/3.15 and actual Windows batch execution were
  not run. Documentation checks are not a substitute for that execution matrix.
- **Framework/database integration:** SQLAlchemy loader and pytest teardown corrections were checked
  against official documentation. The SQLite retry fixture uses an injected conflict, not a live
  PostgreSQL SQLSTATE test; migration fixtures model explicit state sequences, not a deployed fleet.

## Maintenance acceptance

Keep runtime and maintainer material separate, preserve the original archive, retain failed cases,
and use the same integrity checks when changing a release. Expand execution testing for a named
platform/deployment decision or a concrete remaining uncertainty. Freeze the candidate and comparison
protocol before any claimed quality benchmark, and record actual outcomes, costs, and task-level
uncertainty rather than inferring them from package size or reference-solution success.
