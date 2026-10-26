# Packaging

## Contents

- [pyproject.toml is the standard STANDARD](#pyprojecttoml-is-the-standard-standard)
- [Build isolation](#build-isolation)
- [Locking and reproducibility](#locking-and-reproducibility)
- [Dependency groups STANDARD](#dependency-groups-standard)
- [Package vs application](#package-vs-application)
- [Entry points and console scripts](#entry-points-and-console-scripts)
- [Wheels and sdists](#wheels-and-sdists)
- [Frontends: a workflow choice ECOSYSTEM](#frontends-a-workflow-choice-ecosystem)
- [Versioning strategy (libraries)](#versioning-strategy-libraries)
- [Dependency hygiene (I12)](#dependency-hygiene-i12)
- [Checklist: new package](#checklist-new-package)

Operational reference for Python packaging. Standardized facts are [STANDARD]-tagged (PyPA specs);
frontend/tool choices are [ECOSYSTEM]. Version-sensitive facts (Python baseline, tool maturity) live
only in [modern-python-baseline.md](modern-python-baseline.md). Library workflow:
[library-package playbook](../playbooks/library-package.md).

## pyproject.toml is the standard [STANDARD]

- `pyproject.toml` is the standard home for build metadata and many tool settings, with distinct layers:
  - `[build-system]` — which build backend and requirements (`setuptools`, `hatchling`, `flit`,
    `poetry-core`, `maturin`…). This is standardized [STANDARD].
  - `[project]` — metadata (name, version, dependencies, requires-python, scripts, urls). Standardized
    fields [STANDARD]. `license` is an SPDX license expression string (PEP 639); `license-files` lists
    the files. The old `license` table and `License ::` classifiers are deprecated.
  - `[tool.*]` — **tool-specific** configuration (Ruff, mypy, pytest, coverage…). The *location* is
    conventional; each tool's keys are that tool's own schema ([tooling.md](tooling.md)).
- `setup.py`-as-workflow (executable setup scripts, `python setup.py install/sdist`) is [LEGACY].
  Modernization path (PyPA-documented): move metadata to `pyproject.toml`, keep `setup.py` only if a
  build backend genuinely needs it (rare), use `python -m build` to produce sdist/wheel. Do not design
  new systems around executable setup scripts; if a repo still uses them, that's a MODERNIZE task with
  a named migration ([modernization](../templates/migration-plan.md)).

## Build isolation

- Standards-based frontends normally build in an isolated environment seeded by
  `[build-system].requires`; a backend may request additional build dependencies, and frontends can
  explicitly disable isolation [STANDARD]. Reproduce the project's actual build mode when diagnosing
  "it builds on my machine" (`python -m build` for the usual isolated path).
- Editable installs (`pip install -e .`) are **development convenience**: they link source to the
  environment for iteration. Production deploys install built artifacts (wheel/sdist) — never an
  editable install pointing at a mutable checkout. Production reproducibility comes from declared
  dependencies + locked resolution + immutable artifacts, not from dev-environment state.

## Locking and reproducibility

- `pylock.toml` (PEP 751) is the **standardized lockfile interchange format** [STANDARD] (approved
  2025; adoption across tools is newer — see [baseline](modern-python-baseline.md)). Interchange is
  possible when the chosen tools implement the format; tool-native lockfiles (poetry.lock, uv.lock,
  pinned requirements files) remain common [ECOSYSTEM].
- Applications need reproducible deploys: commit the tool's lock or equivalent resolved constraints,
  then install from that resolution/immutable artifact and update it deliberately. Libraries normally
  publish compatible dependency constraints and test against them; an internal dev/test lock can make
  their CI reproducible without constraining consumers. Published exact pins need a specific reason.

## Dependency groups [STANDARD]

- Dependency groups (`[dependency-groups]`, PEP 735) provide a standardized way to keep dev/test/docs
  requirements out of built project metadata [STANDARD]. A repository may still use requirements files
  or tool-specific groups; choose the format its workflow supports.

## Package vs application

| | Library/package | Application |
|---|---|---|
| API stability | Public API is a contract; versioning policy stated | Internal compatibility follows deploy needs |
| Dependencies | Ranges (`>=,<`) | Locked exact versions |
| Distribution | PyPI/internal index; sdist+wheel | Container/image or venv deploy ([deployment.md](deployment.md)) |
| Versioning | Breaking-change signal follows stated policy (major bump if using SemVer after 1.0) | Deploy artifact version/commit SHA |

- Confusing the two is a common packaging error: an app with library-style ranges gets non-reproducible
  deploys; a library with pinned deps collides with its users' resolution.

## Entry points and console scripts

- `[project.scripts]` maps command names to `module:function` callables [STANDARD]; the generated
  wrapper handles interpreter/env details. Use functions as entry points (not `if __name__ == '__main__'`
  blocks in scripts) so the same code is importable and testable.
- Entry points also power plugin discovery ([architecture.md](architecture.md)); both use the same
  registry metadata.

## Wheels and sdists

- **Wheel** (.whl): built distribution — pre-compiled, installs without a build step. **sdist**: source
  distribution — requires a build on install. Prefer wheels in constrained/production environments
  (no compiler needed, faster, less install-time code execution ([security.md](security.md))).
- Platform/ABI: pure-Python wheels are universal; C extensions need per-platform wheels (build matrix
  cost — [performance.md](performance.md) native boundary decision). `manylinux` tags describe
  compatibility [STANDARD].

## Frontends: a workflow choice [ECOSYSTEM]

- pip (the baseline installer), uv (fast resolver/manager), Poetry (project + dependency management),
  PDM, Hatch, pip-tools (compile/requirements flow). They differ in lock UX, speed, monorepo support,
  build integration — **no single frontend is "correct"**; the banned slogan "uv is a packaging
  standard" is wrong: standards are `pyproject.toml`/`pylock.toml`; frontends implement them with
  different workflows.
- Choose per repo needs: existing repo keeps its frontend absent a named problem (repository evidence
  rule, [SKILL.md](../SKILL.md)); greenfield picks based on team workflow, lockfile preference, and CI
  constraints. Record an ADR only if the choice is costly to reverse.
- Interop direction of travel: frontends converge at standard interfaces (metadata, lock interchange)
  while keeping distinct UX — design for the standards so tool swaps stay possible
  ([baseline](modern-python-baseline.md) tracks convergence).

## Versioning strategy (libraries)

- SemVer is one option [ECOSYSTEM]: after 1.0, major = breaking API change, minor = additive, patch =
  compatible fixes. The contract is the declared public API; underscore-private modules are normally
  outside it. Set deprecation windows based on consumer upgrade needs and the chosen policy.
- `requires-python` is part of the contract: dropping a Python version is a breaking change for users
  on it — bump major (or follow the stated support policy) and say so in the changelog. Supported
  versions are tested in CI against the baseline matrix
  ([modern-python-baseline.md](modern-python-baseline.md)).
- Under SemVer, pre-1.0 signals unstable API: `0.y.z` may change at any time, so consumers need an
  explicit compatibility policy if they rely on it. Changelogs document behavior changes, not just
  commit lists.

## Dependency hygiene (I12)

- Every dependency states what it replaces, its maintenance/health, license, transitive weight, and
  security surface (I12). Prefer stdlib when it covers the need; prefer the repo's existing stack over
  a new addition for convenience.
- Regular audits: outdated pins, yanked releases, known CVEs ([security.md](security.md) supply chain).
  Lockfile updates are reviewed changes, not bot-blind merges.

## Checklist: new package

1. `pyproject.toml` with `[build-system]` + `[project]` (metadata complete: `requires-python`, license).
2. Choose src or flat layout with import-test behavior understood ([architecture.md](architecture.md)); build via `python -m build`; test install from wheel.
3. Keep dev dependencies out of published runtime metadata; use groups or the repo's existing convention. A library may lock its own dev/test environment without locking consumers.
4. `py.typed` if typed ([typing.md](typing.md)); entry points as functions.
5. CI: build + install-from-artifact + tests on the supported Python versions (see
   [baseline](modern-python-baseline.md)); publish via trusted publishing where available
   ([security.md](security.md)).
