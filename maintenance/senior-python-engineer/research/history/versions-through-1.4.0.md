# Historical versions through 1.4.0

Historical snapshots below are not current runtime guidance. Version and maintenance status may have changed.

## Changelog

- **1.4.0** (2026-10-03 design-judgment pass):
  - Change locality, cohesion versus a class-per-noun, when a duplicate is cheaper than a base class,
    public surprises and invariants, explicit state versus a class per mode, and when a pattern earns
    rent. Home: [references/architecture.md](../../../../senior-python-engineer/references/architecture.md). Decision model, architecture
    review, code review, greenfield discovery, and generated-code scrutiny point there.
  - Slogans added for mechanical DRY, speculative extension, patterns as a goal, and a leading
    underscore as privacy.
  - Evals: A7 (a passing test whose next change leaks), A8 (flags that can represent an illegal
    order), OE6 (a template-method base for two rules that change apart), R9 (`list` subclass that
    tests never use as a list).
  - Python version facts were not taken from the design source. The 1.3.0 baseline stands.
- **1.3.0** (2026-10-02 web-verified correction pass):
  - Baseline moved from 3.14.7 to **3.14.8**. 3.15.0 final was postponed on 2026-10-01; last published
    candidate found was 3.15.0rc2. 3.10 is end of life; 3.13's last full maintenance release is 3.13.16.
  - Recorded the 3.14.5+ incremental-GC revert, the still-experimental JIT (including "no JIT on
    free-threaded builds"), and 3.14 asyncio-on-free-threading rules (one loop stays serial and
    unshared).
  - Corrected `typing.Never` (3.11 bottom type, not PEP 654), PEP 695 variance (inference includes
    invariant), and `LiteralString` (not an SSRF or runtime SQL control). Documented PEP 649/749
    deferred annotations. `from __future__ import annotations` still stringifies in 3.14; deprecation
    is not before the first release after 3.13's end of life.
  - Nuanced `compare_digest` (length can still leak; passwords use a hasher verify), `tarfile` defaults
    versus 3.14.8 filter-bypass fixes, t-strings (PEP 750 is not safe shell/SQL; PEP 787 is Deferred),
    and PostgreSQL `25P02` (any statement error aborts; `23505` is not blindly retryable).
  - pytest-asyncio 1.x: dropped the removed `event_loop` fixture and the `ScopeMismatch` name; fixture
    and test loop scopes have to match. PEP 639 SPDX `license`. uv/Poetry keep native locks; `pylock.toml`
    is export/interchange. `torch.load` still defaults to `weights_only=True` and is still not a
    license to load untrusted files; omitting the argument can be flipped by
    `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD`.
  - Evals: AS3 rejects "free-threading parallelizes this one loop"; SE7 covers tarfile default versus
    patch level versus a complete sandbox.
  - Source notes: [research/2026-10-02-verification.md](../2026-10-02-verification.md). The
    2026-09-29 research report was left as a snapshot.
- **1.2.0** (2026-10-02 comprehensive improvement pass):
  - **Factual correctness & modern standards**: added PEP 675 `LiteralString`, `typing.Never`, and PEP 695 auto-variance to `references/typing.md`; `TaskGroup` with `ExceptionGroup` and `except*`, `gather` sibling task leak hazard, and `contextlib.aclosing` to `references/asyncio-concurrency.md`; PostgreSQL `40001`/`40P01` transaction abort `25P02 InFailedSqlTransaction` whole-transaction rollback semantics and connection pool fork-safety (`engine.dispose(close=False)`, Gunicorn `--preload`) to `references/persistence.md` and `references/deployment.md`; `secrets.compare_digest` constant-time comparison against timing attacks, PEP 706 `tarfile.extractall(filter='data')`, and `ipaddress.ip_address` SSRF checks to `references/security.md`; `pytest-asyncio` loop scoping to `references/testing.md`.
  - **Senior judgment & architecture**: balanced simplicity-first with anti-underengineering; codified `constraint → options → trade-offs → decision`; formalized triggers for domain/service boundaries across multi-entrypoint workflows.
  - **Catalogs & smells**: added anti-pattern 28 (Under-engineered controller / Anemic handler coupling) and anti-pattern 29 (Orphaned gather tasks on exception) to `catalogs/anti-patterns.md`; added Controller-as-domain smell to `catalogs/smells.md`.
  - **Execution efficiency & routing**: streamlined domain routing in `SKILL.md` to be strictly just-in-time; introduced progressive depth by task risk (Tiers 1, 2, 3) to eliminate ceremony on routine work.
  - **Reviews**: updated async, database, security, and general code reviews with new technical verification criteria and PR scope containment.
  - **Evals calibration suite**: replaced duplicate Case OE4 with the Under-Engineering Trap (dogmatic refusal of domain boundaries across multi-entrypoints); added Case R8 (drive-by tooling/reformatting migration smuggled into a bug fix PR); added Case AS8 (`asyncio.gather` sibling task leakage); added Case D6 (statement-level retry inside an aborted PostgreSQL transaction).
- **1.1.0** (2026-09-30 second pass): corrected asyncio cancellation, framework and packaging claims;
  separated invariant strength from review severity; made evidence, routing, and production gates more
  conditional; strengthened regression evals.
- **1.0.0** (2026-09-29 knowledge base): initial package — core decision model, invariants, evidence
  rules; 12 domain playbooks; 10 review procedures; 16 references; 3 catalogs; 8 templates; 11 eval
  files. Baseline: Python 3.14.
