# Maintaining Senior Python Engineer

This directory holds the source records, development evaluations, tooling, and release evidence for
**version 1.5.0**. The installed skill is the separate
[runtime directory](../../senior-python-engineer/SKILL.md). Do not put this maintenance directory in a
candidate agent's readable or writable mounts during evaluation.

## Layout

| Location | Purpose |
|---|---|
| `../../senior-python-engineer/` | Runtime instructions, playbooks, references, reviews, catalogs, and templates |
| `tools/` | Offline integrity checks, verified runtime copying, source checks, mechanism probes, and evaluation CLI |
| `evals/*.md` | Sixty public six-field judgment cases and evaluation guidance |
| `evals/fixtures/` | Twelve visible development tasks and starter artifacts |
| `evals/graders/` and `evals/reference/` | Evaluator-only behavior checks and reference implementations |
| `evals/results/` | Recorded fixture checks and development task artifacts |
| `research/` | Current claim registers, source policy, and clearly historical inputs |
| `validation/` | Exact release check outputs and command index |
| `VERSION.md` | Changes, original-archive identity, and maintenance policy |
| `RELEASE_VERIFICATION.md` | Validation outcomes and limits of the release evidence |

## Validate and build

The project tools require Python 3.11+ and use only the standard library. Run these commands from this
maintenance directory. They do not install dependencies or contact external services.

```bash
python3 tools/validate_skill.py
python3 tools/check_sources.py --as-of 2026-10-26 --fail-on-due
python3 tools/verify_python_semantics.py
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 tools/evaluate.py selftest
python3 tools/build_runtime.py --output /tmp/senior-python-release
```

Use the actual review date instead of the example `--as-of` date. Use a new output directory for each
build; existing output is never overwritten. The build validates the source, copies only the runtime,
validates the copy, compares file hashes, and writes a checksum manifest beside the installed directory.
Only the inner `senior-python-engineer/` directory is the skill.

The frontmatter validator deliberately supports this project's unquoted, single-line string format.
It rejects ambiguous YAML scalar syntax; it is not a general-purpose YAML parser or a complete
CommonMark implementation. The official skill-creator metadata validator was also run for this release.
Package checks verify local navigation, permitted files, naming and invariant references. They do not
prove the engineering advice correct or observe automatic activation by a host.

The source checker validates structure, affected file paths, and review age. A due reminder is a request
to recheck a claim, not proof that it has become false; passing the check does not establish live factual
currency. See [source policy](research/SOURCE_POLICY.md).

## Evaluate behavior

Use [HARNESS.md](evals/HARNESS.md) for visible-only preparation, grading, recorded adjudication, result
reporting, A/B/C comparisons, actual-host activation checks, and the holdout lifecycle. Use
[ADJUDICATION.md](evals/ADJUDICATION.md) for outcome criteria.

`evals/pilot-plan.json` is a reproducibly shuffled plan for 12 tasks × 3 conditions × 3 trials.
Generating it executes zero agents. The published cases and fixtures are development material.
A future generalization claim requires fresh untouched tasks, comparable host/model/tool conditions,
actual outcome evidence, and task-level uncertainty. An agent's private reasoning is not a deliverable
or a grading requirement.

The grader executes candidate Python and is not a security sandbox. Its completion record prevents
accidental zero-test/early-exit false passes but is not tamper-proof. Apply isolation and resource
limits in the actual execution host, and inspect trusted traces for actions a final filesystem snapshot
cannot reveal.

## Preserve provenance and scope

The original uploaded archive remains unchanged. Its full third-party book conversion is not included
here; the bibliography and original distilled architecture guidance are retained. Historical research
with unmapped conversation citations is archived as context and must not be treated as current authority.

Update a claim's canonical runtime home and dependent summaries/oracles together. Keep tests and
reference answers outside runtime. Record exact environments, distinguish proposed checks from actual
runs, and retain failed trials instead of averaging away consequential defects.
