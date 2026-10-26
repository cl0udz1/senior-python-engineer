# CLI & Automation

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

**Modes:** DESIGN, IMPLEMENT, REVIEW · **Concerns:** PACKAGE · **Domains:** CLI_AUTOMATION, DEVOPS_INFRASTRUCTURE
Procedure for command-line tools, scripts, and automation. Governing rule: pure-ish core logic, side
effects at the edges, and honest exit codes ([I13](../core/python-invariants.md)).

## 1. Typical system shape

- Three-part shape: **argument parsing → pure-ish core (decisions/transformations) → side effects at the edges** (files, subprocesses, network, cloud APIs). Core is importable and testable without executing anything.
- Entry points: `main(argv) -> int` returning an exit code; `if __name__ == "__main__":` guard; console-script entrypoint in `pyproject.toml` when packaged ([packaging](../references/packaging.md)).
- IF the tool is one file under ~200 lines with one consumer → keep it one file. Promotion triggers: second consumer, subcommands, or core logic that tests need to import.
- Automation wrappers (cron, CI steps) call the same entrypoint; no parallel "internal" code path.
- Output contract: human-readable text by default, `--json` (or similar) for machine consumers; stable stdout for data, stderr for diagnostics [ECOSYSTEM].

## 2. Important constraints

- **Startup time** matters for CLI ergonomics [ECOSYSTEM]: heavy imports (large SDKs, pandas, ML stacks) go behind lazy imports in the code path that needs them — but import-time *work* stays banned ([I3](../core/python-invariants.md)); lazy import ≠ import-time side effects.
- **Distribution**: pick explicitly — venv/requirements for CI-internal, pipx/uv-tool for personal/team tools, packaged app for non-Python users ([packaging](../references/packaging.md)). Lock or pin for reproducible automation; declare supported Python versions.
- **Exit codes** are API: 0 success, non-zero failure, distinct codes per failure class callers must distinguish; document them in `--help`.
- **Idempotent re-runs**: automation runs twice — by retry, by double-cron, by human. Every script answers "what happens if this runs twice?" ([I8](../core/python-invariants.md)).
- Sync execution model is the default here ([Decision Model](../core/decision-model.md) §1): sequential ops, short process lifetimes, and startup cost all argue against asyncio.
- Environment assumptions are explicit: working directory, locale, PATH, and platform (POSIX/Windows) are inputs, not ambient luck [HEURISTIC].

## 3. Recommended discovery questions

Ask only what changes the design:
- Who invokes it — human, CI, cron, another system? (Startup cost, exit codes, logging format.)
- What does it change, and what happens if it runs twice or dies halfway? (Idempotency/dry-run design, [I8](../core/python-invariants.md).)
- What inputs are untrusted (files, user args, remote data)? (Validation boundary, [I1](../core/python-invariants.md); injection surfaces, §9.)
- How is it distributed and to whom? (Packaging form, lockfile, Python version floor.)
- What is the blast radius — dev machine, staging, production? (Audit logging, confirmation prompts, force flags.)
- Does it need to run concurrently with another instance? (Locking/overlap behavior for cron.)
- Which failure classes must callers distinguish? (Exit-code map.)
- Does anything already consume the output programmatically? (Output stability contract.)
- How will it be upgraded in place — and can old and new versions run concurrently during rollout? (Config/data format compat.)

## 4. Common architecture choices

- **Argument parsing**: argparse (stdlib, zero deps) [STANDARD] vs Click/Typer (subcommand ergonomics, testing helpers) [ECOSYSTEM] — IF the tool is small or dependency-averse → argparse; BUT IF rich subcommands/UX and the stack already includes Click/Typer → use it. Parser choice is plumbing, not architecture.
- **Core/edge split**: IF logic can be a pure function of inputs → make it one; side effects (writes, calls) in thin edge functions receiving explicit paths/clients. BUT IF the tool is a thin one-shot wrapper over one API call → the ceremony is not needed; validate, call, report.
- **Destructive operations**: IF the tool mutates anything → `--dry-run` (default for risky ops) + `--force`/`--yes` for automation; diff/report before change where feasible. BUT IF the operation is trivially reversible → skip the ceremony, say why.
- **Packaging**: app with pinned lock for CI/cron reproducibility; pipx-style tool with ranged deps for personal tools ([packaging](../references/packaging.md)). Executable `setup.py` workflows are [LEGACY].
- **Concurrency**: sync unless the tool's *job* is high-concurrency I/O fan-out with async-native deps ([Decision Model](../core/decision-model.md) §1); async for a sequential script adds debugging cost with no gain.

## 5. What not to overengineer

- DI containers, plugin architectures, or abstract factory trees for a 200-line tool ([I11](../core/python-invariants.md)).
- Async for sequential operations; thread pools for one call; caching in a process that lives 2 seconds.
- Custom logging frameworks (stdlib `logging` or structured one-liners suffice); elaborate config systems for three flags — flags/args/env in that order of preference.
- Rich TUI frameworks unless the UX genuinely requires it; output-parsing frameworks when plain text/JSON out works.
- A class hierarchy for what are five functions ([Decision Model](../core/decision-model.md) §2).
- Retry frameworks for a script whose failure handling is "exit non-zero and let the scheduler decide" ([I13](../core/python-invariants.md)).

## 6. Failure modes

Domain-relevant subset of [Failure Modes](../catalogs/failure-modes.md):
- **Partial application of changes** — halfway through a multi-file/multi-resource change, one step fails and earlier steps are unknown ([I8](../core/python-invariants.md): per-step idempotency or a plan/apply split).
- **No dry-run where risky** — automation mutates production on first syntax-level mistake; add `--dry-run` + diff.
- **Shell injection** — `shell=True` or string-built commands with uncontrolled input ([Security](../references/security.md): argument vectors, allowlists).
- **Unlogged silent failure** ([I13](../core/python-invariants.md)) — `except Exception: pass` in a cron job hides months of breakage; exit non-zero and log with context.
- **Overlap/double-run** — two cron instances interleave writes without locking; define locking or idempotent re-run.
- **Secrets in logs/args** ([I15](../core/python-invariants.md)) — argv is visible in `ps` and CI logs; read secrets from env/secret boundary, never CLI flags.

## 7. Performance considerations

- Evidence-first ([I9](../core/python-invariants.md), [Performance](../references/performance.md)): for CLI/automation, "performance" is usually startup time and bulk I/O — measure both before optimizing.
- IF startup is slow → attribute (import time via `python -X importtime`, interpreter startup, network) before restructuring ([Evidence Rules](../core/evidence-rules.md) §3).
- Bulk operations: batch API calls and file writes; N-per-item calls to a remote API are the classic automation bottleneck (rate limits too).
- Rewrite-in-faster-language for CLI tools is a distribution/startup decision, not a Python failure [HEURISTIC]; state the actual constraint ([Evidence Rules](../core/evidence-rules.md) §3).
- Networked automation is dominated by remote latency: parallelize independent calls with bounded concurrency or batch them; measure rate-limit headroom first.

## 8. Testing strategy

- Follow [Testing](../references/testing.md): the core/edge split makes the expensive logic cheap to test:
  - **Core**: unit tests over pure functions (parse→plan→transform), including malformed-input cases ([I1](../core/python-invariants.md)).
  - **Edge**: thin tests with a fake server or recorded fixtures for external calls; one integration test per real side-effect boundary that is safe to run.
  - **CLI contract**: exit codes and stdout/stderr behavior per documented case (success, validation error, partial failure).
- Property-based tests for parsers/transformations ([Testing](../references/testing.md)). Test dry-run output equals planned change.
- IF the tool runs unattended → one test asserting the failure path exits non-zero and emits a diagnosable message.

## 9. Security concerns

- Proportional to blast radius ([Security](../references/security.md)); automation frequently runs with elevated credentials — treat that as the risk multiplier:
  - **Subprocess hygiene**: prefer argv with `shell=False` for native executables; validate executable,
    options, paths, and environment. On Windows, `.bat`/`.cmd` wrappers need separate analysis because
    shell parsing can occur even with `shell=False`; avoid untrusted arguments through wrappers when
    feasible and follow the scoped [security guidance](../references/security.md).
    Source: [Python subprocess security considerations](https://docs.python.org/3.14/library/subprocess.html#security-considerations).
  - **Input validation** ([I1](../core/python-invariants.md)): args, env, and file formats cross trust boundaries.
  - **Secrets** ([I15](../core/python-invariants.md)): from env/secret manager; never in argv, logs, or committed configs; redact in error output.
  - Least-privilege credentials for the tool's role; destructive commands require explicit confirmation/force ([Security Review](../reviews/security-review.md)).

## 10. Deployment/lifecycle concerns

- Scheduling: cron/CI invocation defined with overlap policy (flock/skip-if-running), retry policy, and **failure alerting** — unattended failure is silent failure at org scale ([Reliability](../references/reliability.md)).
- Reproducibility: pinned environment for automation ([packaging](../references/packaging.md)); "works on my venv" is not a deployment.
- Logging: timestamped, structured where machines consume it; where the log goes when run unattended (CI artifact? aggregator?) is part of the design ([Observability](../references/observability.md)).
- Long-running automation (daemons) is out of this playbook's shape — route to [workers-jobs.md](workers-jobs.md) or [production-service.md](production-service.md).

## 11. References for unresolved questions

Read only the section that answers an active question; this list is a menu, not a reading sequence.

- [core/python-invariants.md](../core/python-invariants.md) — I1, I3, I8, I13, I15 dominate this domain.
- [references/packaging.md](../references/packaging.md) — entrypoints, dependency/lock strategy, pipx vs app packaging.
- [references/security.md](../references/security.md) — subprocess hygiene, path traversal, secrets handling.
- [references/testing.md](../references/testing.md) — testing core/edge split and CLI contracts.
- [references/tooling.md](../references/tooling.md) — lint/type tooling appropriate to tool size.
- [references/reliability.md](../references/reliability.md) — retry/idempotency/overlap behavior for scheduled runs.
- [catalogs/failure-modes.md](../catalogs/failure-modes.md) — the partial-failure and double-run questions to answer.
- [cli-automation.md](cli-automation.md) is this file; pair with [existing-codebase.md](existing-codebase.md) when adding to an existing tool.

## 12. Exit/readiness criteria

Apply the [mode-specific completion rules](../SKILL.md#task-modes) to the relevant criteria below.
Operational checks are release gates only when release readiness is in scope. Report actual evidence
and label proposed or unavailable checks.

Observable checklist:
- [ ] Exit codes defined (0 + distinct failure classes) and documented in `--help`; tested.
- [ ] `--dry-run`/`--force` present where the tool mutates anything risky; dry-run output matches what would change.
- [ ] Core logic tested without side effects (unit tests run and results stated).
- [ ] Idempotency answer recorded: what happens on double-run and on death halfway ([I8](../core/python-invariants.md)).
- [ ] Subprocess/path handling passes hygiene check (no shell-string interpolation of untrusted input).
- [ ] Secrets sourced from config/secret boundary, absent from argv/logs ([I15](../core/python-invariants.md)).
- [ ] Distribution story stated (venv/pipx/app + lock/pin) and scheduled-run failure alerting defined.
- [ ] Output contract documented (stdout/stderr separation, machine format if any) and stable.
- [ ] Environment assumptions explicit (cwd, PATH, platform) and validated at startup where they matter.
