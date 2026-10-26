# Existing Codebase

## Contents

- [1. Typical system shape](#1-typical-system-shape)
- [2. Important constraints](#2-important-constraints)
- [3. Recommended discovery questions](#3-recommended-discovery-questions)
- [4. Common architecture choices](#4-common-architecture-choices)
- [5. What not to overengineer](#5-what-not-to-overengineer)
- [6. Failure modes](#6-failure-modes)
- [7. Performance considerations](#7-performance-considerations)
- [8. Testing strategy](#8-testing-strategy)
- [9. Security concerns](#9-security-concerns)
- [10. Deployment/lifecycle concerns](#10-deploymentlifecycle-concerns)
- [11. References for unresolved questions](#11-references-for-unresolved-questions)
- [12. Exit/readiness criteria](#12-exitreadiness-criteria)

**Modes:** EXPLAIN, REVIEW, DESIGN, IMPLEMENT · **Concerns:** REFACTOR, MODERNIZE, DEBUG · **Domains:** in-repo work of any domain
Procedure for making changes inside a repository you did not design. Governing rule: **local evidence
outranks ecosystem preference** ([Evidence Rules](../core/evidence-rules.md) §1-2, §4; [SKILL.md](../SKILL.md) "Inspect before prescribing").

## 1. Typical system shape

- The shape is whatever the repo already is; the playbook's job is to map it before touching it:
  package layout (src vs flat), entrypoints (web app, CLI, workers), module boundaries, data layer,
  and where cross-cutting concerns (config, logging, auth) live.
- IF the change is local (one module, one feature) → keep the change local; do not "improve" neighbors.
- IF the change crosses module boundaries → map the dependency direction first; circular imports here
  usually mean the dependency direction is wrong, not that Python is ([Anti-Patterns](../catalogs/anti-patterns.md)).

## 2. Important constraints

- **The repository's own evidence is the authority**: `pyproject.toml`, lockfile, CI, tests, deploy config,
  existing patterns outrank personal tool/framework preference ([Evidence Rules](../core/evidence-rules.md) §1 level 2).
- **Migration ban without a named problem** ([Evidence Rules](../core/evidence-rules.md) §4): NEVER recommend
  Poetry→uv, Flask→FastAPI, sync→async, ORM→raw SQL, or monolith→microservices unless the concrete problem
  the migration solves, its cost, and its rollback story are stated. "Modern" and "popular" are not problems.
- [I10](../core/python-invariants.md): framework conventions stay local; [I12](../core/python-invariants.md):
  keep the incumbent dependency stack absent a concrete gap.
- Behavior preservation is the contract of REFACTOR work: structure changes, observable behavior does not.
- Local coding conventions outrank personal style ([I16](../core/python-invariants.md)).

## 3. Recommended discovery questions

Read before asking — the repo answers most of this itself. Record findings when they change the recommendation:
1. `pyproject.toml` / `setup.cfg` / `setup.py` ([LEGACY]): metadata, build system, tool config, dependency groups.
2. Python version floor (requires-python, CI matrix, `.python-version`, container base image).
3. Lockfile type (`uv.lock`, `poetry.lock`, `requirements*.txt`, `pylock.toml` [STANDARD]) and the package manager actually in use.
4. Layout: src-layout vs flat; where the importable package lives; namespace conventions.
5. Entrypoints: console scripts, WSGI/ASGI app object, worker commands, cron definitions.
6. Dependencies: direct vs transitive, pinned vs ranged, framework and driver versions actually pinned.
7. Tests: runner (pytest/unittest), layout, fixtures, coverage config, what is actually asserted.
8. CI: what runs on PR (lint, type-check, tests, build), and what gates merges.
9. Containers/deploy: Dockerfile, compose, K8s manifests, process model, env config.
10. Framework config: settings module, middleware, app factory vs global app.
11. DB layer: ORM vs SQL, session/transaction patterns, migration tool and migration state.
12. Lint/format/type config: Ruff/Black/flake8, mypy/Pyright strictness, per-module overrides.
13. Sync vs async model: where coroutines run, whether the dependency surface is async-native.
14. Conventions: naming, error handling style, logging style, how config and secrets are read.
Only ask the human what the repo cannot answer (product intent, upcoming constraints, ownership).

## 4. Common architecture choices

- IF the repo's pattern fits the change → follow it exactly, even if a different pattern would be your default.
- IF the change is a refactor → capture untested behavior that the refactor could change, then restructure ([Testing](../references/testing.md)); use small steps and relevant checks between them.
- IF a named production problem exists (e.g. measured N+1, blocking call stalling the loop) → propose the minimal fix for that problem, with the evidence ([Evidence Rules](../core/evidence-rules.md) §3).
- IF a stack migration is genuinely warranted → problem + proof + cost + rollback ([Evidence Rules](../core/evidence-rules.md) §4), recorded as an [ADR](../templates/architecture-decision-record.md), executed as a [migration-plan](../templates/migration-plan.md).
- BUT IF the incumbent works and no problem is named → keep it. Style conflicts get matched, not "fixed".
- IF the repo mixes ORM and raw SQL → that is normal ([Decision Model](../core/decision-model.md) §4); do not unify.

## 5. What not to overengineer

- Unrequested modernization: Python upgrades, tool swaps (Poetry→uv, Flake8→Ruff), framework upgrades "while we're here".
- Reformatting or restyling unrelated code; converting sync to async; adding type annotations everywhere;
  adding layers (repositories, services, DI) to code that has one consumer ([I11](../core/python-invariants.md)).
- Adding dependencies to do what the incumbent stack or stdlib already does ([I12](../core/python-invariants.md)).
- Rewriting working code because it is "ugly" — ugliness with no defect is a style comment, and style
  comments must not hide correctness problems ([SKILL.md](../SKILL.md) review priority order).

## 6. Failure modes

Domain-relevant subset of [Failure Modes](../catalogs/failure-modes.md) for in-repo change:
- **Behavior drift during refactor** — untested edges changed silently (mitigate: characterization tests, §4).
- **Schema/migration mismatch** — code expects columns the deployed DB lacks; migrations not reversible.
- **Import-time side effects** ([I3](../core/python-invariants.md)) exposed by restructuring imports.
- **Hidden test gaps** — suite is green but covers only the happy path of the touched area.
- **Convention breakage** — the change works but every future reader pays the inconsistency cost.
- **Scope creep** — the fix for one defect silently becomes a rewrite ([SKILL.md](../SKILL.md): changes stay scoped).

## 7. Performance considerations

- Do not optimize unprompted. IF performance is the task → measure *in this repo's environment* first:
  workload → profile → attribute → fix dominant term ([Evidence Rules](../core/evidence-rules.md) §3,
  [Performance](../references/performance.md)).
- The common in-repo wins are boring and measurable: N+1 query elimination via existing eager/select-in
  loading ([Decision Model](../core/decision-model.md) §4), batch calls, removing accidental O(n²) data
  shuffling, cutting duplicate external calls. Caching only with defined invalidation ([Decision Model](../core/decision-model.md) §4).
- IF a "Python is slow" claim appears → demand the profile showing interpreter-bound cost before any
  native/rewrite proposal ([I9](../core/python-invariants.md), [Evidence Rules](../core/evidence-rules.md) §3).

## 8. Testing strategy

- Establish a relevant baseline when it helps distinguish existing failures from regressions. Start with
  checks for the touched behavior, then rerun them after meaningful changes. Run the broader suite when
  shared behavior, integration risk, or a required repository gate warrants it; an expensive full suite
  before every edit is not a universal prerequisite.
- IF a refactor could change untested observable behavior → add focused characterization checks before restructuring ([Testing](../references/testing.md), [Testing Review](../reviews/testing-review.md)).
- Match the repo's test style (pytest vs unittest, fixture patterns, placement); do not introduce a parallel
  test architecture.
- Verification is part of the work: state the exact commands run (tests, linter, type-checker) and their results ([Evidence Rules](../core/evidence-rules.md) §6).

## 9. Security concerns

- Proportional to risk: changes touching auth, secrets, subprocesses, serialization, SQL, filesystem, or
  network are **untrusted proposed change** and get review-grade scrutiny before delivery
  ([Security](../references/security.md), [Code Review](../reviews/code-review.md)).
- Never weaken existing validation/auth to make a change pass; never move secrets into code, logs, or diffs ([I15](../core/python-invariants.md)).
- Dependency additions: value case + maintenance/health/license/transitive weight ([I12](../core/python-invariants.md);
  [Dependency Review](../reviews/dependency-review.md)). PyPI attestations ≠ trustworthy code.
- IF legacy deserialization (pickle of stored artifacts) is encountered → treat as a security finding, not a style issue ([Security](../references/security.md)).

## 10. Deployment/lifecycle concerns

- Respect the existing deploy topology and process model; a code change that breaks the shutdown/drain
  sequence or probe behavior is a production change, not a code change ([Deployment](../references/deployment.md),
  [Reliability](../references/reliability.md)).
- Database migrations: backwards compatible with the running version (expand → migrate → contract);
  state the rollback story ([migration-plan](../templates/migration-plan.md)).
- IF the repo's config reads are scattered → centralize only with a named defect (e.g. conflicting env
  reads); otherwise match the incumbent pattern.

## 11. References for unresolved questions

Read only the section that answers an active question; this list is a menu, not a reading sequence.

- [core/evidence-rules.md](../core/evidence-rules.md) — §1 evidence hierarchy, §4 migration evidence (the core rule of this playbook).
- [core/python-invariants.md](../core/python-invariants.md) — especially I3, I10, I12, I16 for in-repo discipline.
- [references/tooling.md](../references/tooling.md) — lint/format/type tool behavior when the repo's config needs interpretation.
- [references/packaging.md](../references/packaging.md) — reading `pyproject.toml`, lockfiles, build systems.
- [references/modern-python-baseline.md](../references/modern-python-baseline.md) — what the pinned/available Python version implies.
- [reviews/code-review.md](../reviews/code-review.md) — self-review of the change before delivery.
- [templates/migration-plan.md](../templates/migration-plan.md), [templates/architecture-decision-record.md](../templates/architecture-decision-record.md) — only if a migration/ADR is actually warranted.
- Domain playbook matching the repo's domain (e.g. [web-api.md](web-api.md), [workers-jobs.md](workers-jobs.md)) once identified.

## 12. Exit/readiness criteria

Apply the [mode-specific completion rules](../SKILL.md#task-modes) to the relevant criteria below.
Operational checks are release gates only when release readiness is in scope. Report actual evidence
and label proposed or unavailable checks.

Observable checklist:
- [ ] Discovery findings recorded (the §3 list, trimmed to what matters) and any finding that changed the recommendation is stated in the reply.
- [ ] Change is scoped to the named problem; no unrequested migrations, restyling, or dependency additions.
- [ ] Existing conventions preserved (layout, naming, error handling, test style).
- [ ] Relevant checks and results stated, including any baseline failures; lint/type checks run where the touched surface or required repository gate calls for them ([Evidence Rules](../core/evidence-rules.md) §6).
- [ ] Behavior-preservation evidence exists for refactors (characterization tests or explicit before/after behavior).
- [ ] Trust-boundary code re-checked per [Code Review](../reviews/code-review.md); result (including "No significant issue found.") reported.
- [ ] Migrations/deploy implications stated, with rollback where irreversible.
