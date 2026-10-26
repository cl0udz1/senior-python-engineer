# Senior Python Engineer

An engineering-judgment skill for Python design, implementation, debugging, and code review.

**Version 1.5.0** helps a coding agent choose proportionate architecture, make state and resource ownership explicit, preserve existing project conventions, and verify its work honestly. It separates explanation, review, design, and implementation: greater risk requires deeper checking, not permission to expand the task.

## Install

Copy only [`senior-python-engineer/`](senior-python-engineer/) into the skills directory supported by your agent. Keep the directory name `senior-python-engineer` and its `SKILL.md` entry point intact.

Example request:

> Use the senior-python-engineer skill to review this Python change. Report findings without editing the project.

For implementation or an architecture-only blueprint, state that scope explicitly.

## Repository layout

| Directory | Contents |
|---|---|
| [`senior-python-engineer/`](senior-python-engineer/SKILL.md) | Installable skill: core rules, 12 playbooks, 10 review guides, 16 references, three catalogs, eight templates, and optional host metadata |
| [`maintenance/senior-python-engineer/`](maintenance/senior-python-engineer/README.md) | Evaluation cases, executable fixtures, graders, validation tools, source records, and historical release evidence |

Do not install the maintenance tree as part of the runtime. During evaluation, keep graders and expected answers outside the candidate agent's accessible workspace.

## Validate locally

The maintainer tools require Python 3.11+ and use the standard library. From the repository root:

```bash
cd maintenance/senior-python-engineer
python tools/validate_skill.py
python -m unittest discover -s tools -p 'test_*.py' -v
python tools/verify_python_semantics.py
python tools/evaluate.py selftest
```

See the [maintainer guide](maintenance/senior-python-engineer/README.md) for source checking, runtime export, and evaluation commands.

## What is verified

The recovered 55-file runtime matches every byte count and SHA-256 hash in the original release manifest. Publication checks on CPython 3.13.5/Linux passed the 19 tool tests and 19 mechanism checks. Fixture validation confirmed nine intentionally broken starters fail, nine reference implementations pass, and three design/review fixtures satisfy structural checks only.

These are package and fixture checks, **not a claim that this skill outperforms an unassisted agent**. The original release records five development agent-task observations. The 108-run A/B/C comparison was prepared, not executed. Windows-specific execution, live PostgreSQL behavior, and automatic host activation are not established by these checks.

- [Version history](maintenance/senior-python-engineer/VERSION.md)
- [Original release evidence and limits](maintenance/senior-python-engineer/RELEASE_VERIFICATION.md)
- [Publication verification](maintenance/senior-python-engineer/validation/publication-2026-10-26/README.md)
- [Source and provenance policy](maintenance/senior-python-engineer/research/SOURCE_POLICY.md)

The verbatim third-party book conversion, private workspace data, and original Git metadata are not distributed here. Historical source-check dates are historical; verify volatile facts when a task depends on them.
