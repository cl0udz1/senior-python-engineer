# Tooling

## Contents

- [The landscape is a set of trade-offs, not a winner](#the-landscape-is-a-set-of-trade-offs-not-a-winner)
- [Lint and format: Ruff vs Black](#lint-and-format-ruff-vs-black)
- [Type checkers: mypy vs Pyright](#type-checkers-mypy-vs-pyright)
- [pytest configuration](#pytest-configuration)
- [Pre-commit and CI integration](#pre-commit-and-ci-integration)
- [Config centralization](#config-centralization)
- [Editor/CI parity](#editorci-parity)
- [Environments and CI job design](#environments-and-ci-job-design)
- [Adopting or replacing tools (evidence rule)](#adopting-or-replacing-tools-evidence-rule)
- [Toolchain minimum for most projects HEURISTIC](#toolchain-minimum-for-most-projects-heuristic)

Operational reference for lint/format/type/test tooling. Tool claims are [ECOSYSTEM]/[FRAMEWORK];
standards for config locations are [STANDARD] ([packaging.md](packaging.md)). Version-sensitive facts
live only in [modern-python-baseline.md](modern-python-baseline.md). Adoption/replace decisions follow
[Evidence Rules §4](../core/evidence-rules.md) — name the defect before changing tools.

## The landscape is a set of trade-offs, not a winner

- Banned slogans: "Ruff replaces every Python tool", "uv is the standard", "mypy is the checker".
  Each tool has a scope; repository evidence outranks ecosystem fashion
  ([SKILL.md](../SKILL.md) repository discovery).

## Lint and format: Ruff vs Black

| Dimension | Ruff | Black |
|---|---|---|
| Scope | Linter (many rule sets consolidated: pyflakes, isort-style, bugbear-style, etc.) + formatter | Formatter only (highly stable, opinionated output) |
| Speed | Very fast (Rust implementation) [ECOSYSTEM] | Fast enough for most codebases |
| Style | Formatter aims for Black-compatible output with **intentional deviations** | The de-facto style reference; near-zero churn |
| Extensibility | No general third-party rule-plugin compatibility like Flake8 [ECOSYSTEM] | N/A (no rules) |
| Migration | Can replace flake8/isort/pylint-class tooling for most rule sets | Stays if repo already formats with it |

- Current common practice [ECOSYSTEM]: Ruff for lint (+ optionally format) on new projects; Black kept
  where formatting stability and tool-agnosticism matter, or where the repo already uses it. Both
  formatting paths are legitimate; mixing formatters is not (one formatter per repo, enforced in CI).
- Intentional deviations matter when migrating Black→Ruff format: diff churn and edge-case line breaks
  will change — review formatting migration diffs as formatting-only commits, never mixed with logic.
- Lint rule selection is policy, not maximalism: enable rules whose violations name real defects
  (unused imports/variables, common bug patterns, import order) and skip style-nitpick noise that
  fights the formatter. A lint config nobody understands is a disable-comment generator.

## Type checkers: mypy vs Pyright

- Both mature [ECOSYSTEM]; differences that matter operationally:
  - **Typing behavior and extension support**: compare the pinned checkers on this repository's
    representative contracts; inference and diagnostics differ. mypy supports plugins [FRAMEWORK],
    but plugin compatibility is version-specific. SQLAlchemy 2.0's old mypy plugin is deprecated
    and tied to older mypy releases; use its native typed mapping APIs for new 2.x mappings. Do not
    silently migrate an existing repository's mappings. See [plugin status](https://docs.sqlalchemy.org/en/20/orm/extensions/mypy.html)
    and the dated [baseline](modern-python-baseline.md#tool-and-framework-status).
  - **Config semantics**: `mypy.ini`/`[tool.mypy]` vs `pyrightconfig.json`/`[tool.pyright]` — different
    strictness flag names and per-module override models.
  - **Speed on large codebases**: Pyright (Node-based) is generally faster on big trees; mypy daemon
    (`dmypy`) narrows the gap in dev loops.
- One pinned checker in CI is a useful default. A second can be justified by distinct checks worth
  its configuration and disagreement cost ([typing.md](typing.md) strictness policy). Record versions —
  checker upgrades can change findings and deserve review.
- Gradual strictness: per-module `disallow_untyped_defs`, `warn_unused_ignores`, explicit `Any` policy
  ([typing.md](typing.md)). Adopt incrementally on legacy codebases; `--strict` day one produces
  ignore-comment debt.

## pytest configuration

- `[tool.pytest.ini_options]` in `pyproject.toml` centralizes markers, testpaths, addopts
  (`-q`, `--strict-markers`, coverage addopts). Custom markers get registered (`--strict-markers`
  prevents typo'd markers silently skipping tests).
- Coverage config lives alongside (`[tool.coverage.*]`); fail-under thresholds are team policy — use
  them as ratchets (floor on critical packages), not global vanity targets
  ([testing.md](testing.md) philosophy).
- Test layout: `tests/` parallel to `src/`; conftest.py for shared fixtures — keep conftest shallow
  (fixture graphs are architecture).

## Pre-commit and CI integration

- `pre-commit` runs formatters/linters on changed files for fast feedback [ECOSYSTEM]; CI runs the same
  tools **pinned to the same versions** on every change. Editor/CI parity is the goal: same formatter,
  same linter rules, same checker version — otherwise "works in my editor" reviews fight CI noise.
- Never rely on pre-commit alone (hooks can be skipped); CI is the enforcement point. Keep the checks
  fast enough to run on every push (lint+typecheck in the fast lane, full test matrix in the thorough
  lane) — see [deployment.md](deployment.md) for CI/CD release gating.
- A common stack is Ruff lint/format checks, one configured type checker, and pytest; these are
  ecosystem choices, not required gates for a small script or an existing repository.

## Config centralization

- Standard: `pyproject.toml` holds tool config where the tool supports it (`[tool.ruff]`, `[tool.mypy]`,
  `[tool.pytest.ini_options]`, `[tool.coverage.*]`) [STANDARD location, tool-specific keys].
- Exceptions stay explicit: `pyrightconfig.json` (or editor settings), `.pre-commit-config.yaml`,
  mypy plugins needing separate config files. Avoid scattering: one tool, one config location, discoverable
  in repo discovery ([SKILL.md](../SKILL.md)).

## Editor/CI parity

- Editor runs a **subset** (fast: format on save, lint on type) with identical config to CI's full run.
- Version skew (editor's bundled mypy vs CI's pinned mypy) is the top source of "CI disagrees with my
  IDE" — pin versions in the repo and have the editor read repo config. Containerized dev environments
  (`devcontainer`, `tox`/`nox`-style envs) reduce this class of drift.

## Environments and CI job design

- Environment reproducibility: lockfiles/pins per [packaging.md](packaging.md); local venvs match CI
  Python version (pyenv-class version managers or containerized dev [ECOSYSTEM]). tox/nox-class tools
  [ECOSYSTEM] run the suite across supported Python versions — use for libraries, where the support
  matrix is the contract.
- CI job ordering for fast feedback: **static lane** (format check + lint, seconds) → **type lane**
  (mypy/Pyright) → **unit lane** (fast tests) → **integration lane** (real DB/boundaries,
  [testing.md](testing.md)) → **build lane** (artifact build + install-from-artifact,
  [packaging.md](packaging.md)). Fail fast left; don't run the 20-minute lane before lint.
- CI caching: cache wheels/downloads keyed on the lockfile hash; never cache virtualenvs across Python
  versions. Pin tool versions in CI identical to dev ([tooling.md](tooling.md) editor/CI parity).
- Flake quarantine policy: a test that fails without code change is quarantined with a tracking issue
  within days, not ignored — flaky gates train humans to re-run instead of investigate.

## Adopting or replacing tools (evidence rule)

- Change tools only with a **named defect** the change fixes (CI latency that harms feedback, false-positive rate
  blocking merges, missing rule class causing a bug family, unsupported platform). "It's newer" is not
  a defect ([Evidence Rules §4](../core/evidence-rules.md) migration evidence).
- For a material migration: named defect → representative before/after check → config parity plan →
  churn budget for formatting/rule diffs → rollback plan. Record an
  [ADR](../templates/architecture-decision-record.md) when the decision is costly to reverse.
- Repo's existing tooling wins absent a concrete problem: don't propose Black→Ruff or mypy→Pyright
  migrations unprompted ([existing-codebase playbook](../playbooks/existing-codebase.md)).

## Toolchain minimum for most projects [HEURISTIC]

| Concern | Typical choice | Alternatives when |
|---|---|---|
| Format | Ruff format **or** Black (one per repo) | — |
| Lint | Ruff | flake8/pylint-class if repo already invested |
| Types | mypy **or** Pyright (one in CI by default) | Both when distinct checks justify the upkeep |
| Tests | pytest + Hypothesis where invariants matter | unittest for existing suites |
| Security scan | `pip-audit`/OSV for deps; semgrep-class for code [ECOSYSTEM] | Full SAST if compliance demands ([security.md](security.md)) |

Tools serve the workflow; the workflow serves confidence in change
([testing.md](testing.md)). Upgrade tools on a schedule (version pins reviewed), not continuously.
