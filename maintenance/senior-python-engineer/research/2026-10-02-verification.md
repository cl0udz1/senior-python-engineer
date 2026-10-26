# 2026-10-02 verification log

> Historical input retained for provenance. This is not an active instruction or a current factual baseline; use SOURCE_POLICY.md and the current claim registers.

Internal source record for the 1.3.0 correction pass. Not runtime guidance. Operational rules stay in
`references/` and `core/`. The 2026-09-29 research report was not rewritten. The 1.2.0 changelog line
that attributed `typing.Never` to PEP 654 was left as history.

Docs pages below were read as the 3.14.8 documentation set unless a draft or library version is named.
"Last updated" dates are the page footers or release notes seen on 2026-10-02.

## Corrections

### Stable baseline is 3.14.8, not 3.14.7

- Previous: documentation and the safe production pin were 3.14.7; 3.15 final was treated as imminent on 2026-10-01.
- Updated: production baseline is 3.14.8. The release page dates it Sept. 30, 2026; PEP 745 records Thursday 2026-10-01. Both dates are kept. 3.15.0 final was postponed on 2026-10-01; the last published candidate page found was 3.15.0rc2 (2026-09-01). Patch levels are not interchangeable.
- Source: https://www.python.org/downloads/release/python-3148/ ; https://peps.python.org/pep-0745/ ; https://discuss.python.org/t/python-3-15-following-tradition-lets-have-a-surprise-rc3/109313 ; https://www.python.org/downloads/release/python-3150rc2/ ; https://peps.python.org/pep-0790/
- Source date: release page Sept. 30, 2026; PEP 745 schedule row 2026-10-01; postponement post 2026-10-01; rc2 page 2026-09-01.
- Reason: an expedited security release and a slipped final are different engineering facts from "3.14.7 docs, 3.15 about to ship."

### Support windows

- Previous: no current branch table. 3.10 could be read as still receiving fixes.
- Updated: 3.14 bugfix at 3.14.8; 3.13 security-only after 3.13.16; 3.12.15 and 3.11.17 security-only; 3.10 end of life at 3.10.22.
- Source: https://devguide.python.org/versions/ ; https://blog.python.org/2026/10/python-31022-31117/
- Source date: Insider post published 2026-10-01 (Pablo Galindo). Devguide table checked the same day; the discuss postponement is newer than the devguide's "3.15 first release 2026-10-01" cell.
- Reason: support decisions (whether a CVE still gets a build) depend on the branch, not on "3.x exists."

### 3.15 features are not 3.14 features

- Previous: no named list, so a prerelease highlight could be cited as current production behavior.
- Updated: explicit lazy imports (PEP 810), `frozendict` (PEP 814), `sentinel` (PEP 661), UTF-8 as the default encoding (PEP 686, named only in the 3.15 draft), and `abi3t` (PEP 803) are direction. The 3.15 draft still calls the JIT experimental. `TaskGroup.cancel` is also 3.15-only and was left out of the baseline list on purpose.
- Source: https://docs.python.org/3.15/whatsnew/3.15.html (draft banner on the page)
- Source date: fetched 2026-10-02. Still a draft. rc3 was not confirmed published.
- Reason: naming the highlights stops them being invented as 3.14 guarantees without turning them into defaults.

### Incremental GC is not a 3.14 feature to recommend

- Previous: no statement. "Upgrade to 3.14 for incremental GC" was an available false recommendation.
- Updated: 3.14.0–3.14.4 shipped incremental GC. 3.14.5 and later, and the 3.15 draft, use the 3.13 generational collector again after production memory-pressure reports.
- Source: https://docs.python.org/3/whatsnew/3.14.html (Garbage collection; "From Python 3.14.5 onwards") ; https://docs.python.org/3.15/whatsnew/3.15.html (`gc` section)
- Source date: 3.14.8 docs, page content fetched 2026-10-02. 3.15 text is draft.
- Reason: recommending the reverted collector would send operators at a pause-time feature the release no longer has.

### JIT and the tail-calling interpreter

- Previous: JIT called experimental, without the production warning, the free-threaded exclusion, or the build-versus-app distinction.
- Updated: official macOS and Windows 3.14 binaries include an experimental JIT, off unless `PYTHON_JIT=1`, not recommended for production. Free-threaded builds do not support it. Workload impact in the 3.14 what's-new runs from about 10% slower to 20% faster; that range is not an expected gain and is not copied into a rule. The tail-calling interpreter (`--with-tail-call-interp`, Clang 19+) is a CPython build detail, not tail-call optimization of Python functions and not an application switch.
- Source: https://docs.python.org/3/whatsnew/3.14.html ("Binary releases for the experimental just-in-time compiler"; "A new type of interpreter")
- Source date: 3.14.8 what's-new, fetched 2026-10-02.
- Reason: "enable the JIT" and "enable the new interpreter" were being usable as drop-in speed advice.

### asyncio on a free-threaded build

- Previous: free-threading does not remove data races. No statement that one event loop stays serial.
- Updated: since 3.14, asyncio may be used from multiple threads on a free-threaded build, but one loop still runs callbacks on one thread. Do not share a loop, await or mutate another thread's `Task`, or use `asyncio.Lock` / `Event` / `Queue` across threads. Handoff is `call_soon_threadsafe`, `run_coroutine_threadsafe`, `queue.Queue`, or `threading` primitives. The 3.14 free-threaded build does not support the limited C API; `abi3t` is 3.15 pre-release.
- Source: https://docs.python.org/3/library/asyncio-threading.html ; https://docs.python.org/3/howto/free-threading-extensions.html (limited C API exclusion, as recorded for 3.14) ; https://peps.python.org/pep-0779/ ; https://docs.python.org/3.15/whatsnew/3.15.html (PEP 803, draft; build tools did not yet support `abi3t` at the time of that draft)
- Source date: asyncio-threading page is part of the 3.14.8 docs (set updated 2026-10-02). PEP 779 is Final.
- Reason: "free-threading makes this async service use multiple cores" is a false reading of thread-safe asyncio.

### `typing.Never` is not PEP 654

- Previous: `Never` was attributed to PEP 654 (that attribution also remains, untouched, in the 1.2.0 changelog).
- Updated: `Never` was added in 3.11. `NoReturn` was added in 3.6.2. They have the same meaning; checkers treat them equivalently. Prefer `Never` for unreachable values. PEP 654 is Exception Groups.
- Source: https://docs.python.org/3/library/typing.html (`typing.Never` / `typing.NoReturn`) ; https://peps.python.org/pep-0654/
- Source date: 3.14.8 typing docs, fetched 2026-10-02.
- Reason: the PEP number pointed reviewers at exception groups.

### PEP 695 variance

- Previous: "automatically infers variance (covariant/contravariant)."
- Updated: inference follows use inside the class and may be invariant, covariant, or contravariant. `TypeVarTuple` and `ParamSpec` stay invariant.
- Source: https://peps.python.org/pep-0695/ ; https://docs.python.org/3/library/typing.html (manual `TypeVar`s are invariant by default; PEP 695 is the inference PEP)
- Source date: PEP 695 Final; typing docs 3.14.8.
- Reason: omitting invariant made inference sound like it always picks co- or contravariance.

### `LiteralString` is not a SQL or SSRF control

- Previous: described as guarding injection including SSRF, and in one security bullet as enforcing that queries are safe because they are literals. I15 allowed reading it as an alternative to parameter binding.
- Updated: PEP 675 is a static claim that a string was composed from literals, with the PEP's own pragmatic limits. A literal URL can still be an unsafe destination. Runtime SQL control is parameter binding. `LiteralString` is an optional static complement.
- Source: https://peps.python.org/pep-0675/
- Source date: PEP 675 Final.
- Reason: a type checker cannot bind query parameters or prove a literal destination is safe.

### Deferred annotations, and the future import is not deprecated yet

- Previous: no 3.14 introspection rule. A draft of this pass said the future import "is deprecated."
- Updated: PEP 649 and PEP 749 are stable 3.14 behavior. Annotations are stored in annotate functions and evaluated when needed, unless `from __future__ import annotations` is used, which still stringifies. PEP 749 keeps that behavior at least until 3.13's end of life; deprecation starts no sooner than the first release after that; removal is at least two releases later. Introspect with `annotationlib.get_annotations` (`Format.VALUE`, `FORWARDREF`, `STRING`) on 3.14+. `inspect.get_annotations` remains the 3.10–3.13 helper. Evaluating annotations can run arbitrary code. This does not make annotations runtime validation.
- Source: https://docs.python.org/3/whatsnew/3.14.html (PEP 649 & 749) ; https://peps.python.org/pep-0749/ ("The future of from __future__ import annotations") ; https://docs.python.org/3/library/annotationlib.html
- Source date: what's-new and PEP 749 fetched 2026-10-02. PEP 749 is Final.
- Reason: libraries that read `__annotations__` as an evaluated dict break on 3.14, and calling the future import already deprecated would push needless rewrites.

### `compare_digest` does not eliminate length leaks

- Previous: "constant-time comparison" that "eliminates timing side-channels." The 1.2.0 changelog still says "constant-time"; that history line was not rewritten. Catalog uses of "constant-time" for CPU complexity were left alone.
- Updated: `hmac.compare_digest` avoids content-based short-circuit and is appropriate for cryptography. If `a` and `b` differ in length, or an error occurs, timing can theoretically reveal type and length, not values. Both sides must be ASCII `str` or bytes-like. Compare equal-length digests. Password checks belong to the hasher's verify API.
- Source: https://docs.python.org/3/library/hmac.html (`hmac.compare_digest`)
- Source date: 3.14.8 docs, last updated Oct 02, 2026 (17:26 UTC).
- Reason: "eliminates timing side-channels" overclaims the note printed on the function.

### `tarfile` default, patch level, and what `'data'` does not do

- Previous: `extractall(filter='data')` was the whole control. A missing keyword was treated as the legacy trusted behavior on every version. `'data'` was easy to read as a closed traversal fix.
- Updated: the `filter` parameter exists since 3.12. In 3.14, if `filter` is omitted and `extraction_filter` is `None`, the default is `'data'` (previously equivalent to `fully_trusted`). Docs: since 3.14 the default prevents the most dangerous issues and does not prevent all insecure behavior; still do not extract untrusted archives without inspection. Explicit `filter='data'` is the portable choice for 3.12/3.13. 3.14.8 fixes two `'data'`-filter bypasses in earlier 3.14 releases: hard link to a symlink (CVE-2026-82049) and directories outside the destination (CVE-2026-19672). 3.14.8 also bounds `zipfile` bzip2, LZMA, and Zstandard decompression per read (CVE-2026-15310); a monkey-patched decompressor that lacks the expected interface can remain unbounded. `'data'` does not cap archive size. CVE identifiers live in the baseline, not in the security reference. Other 3.14.8 CVEs (SSL use-after-free, `wrap_bio` hostname, `HTTPPasswordMgr` scheme mix, StringPrep, float-format precision) were not turned into skill rules.
- Source: https://docs.python.org/3/library/tarfile.html (Changed in 3.14; `extractall` warning; `extraction_filter`) ; https://www.python.org/downloads/release/python-3148/ ; https://peps.python.org/pep-0706/
- Source date: tarfile page is 3.14.8 docs, fetched 2026-10-02. Release page dated Sept. 30, 2026.
- Reason: "add the keyword" and "3.14 defaults to data, so uploads are safe" are both wrong as complete advice, and 3.14.0–3.14.7 are not the same extractor as 3.14.8.

### t-strings are not a safe shell or SQL API

- Previous: no statement. PEP 750 could be cited as if a t-string were parameterized SQL or a safe `subprocess` argument.
- Updated: a t-string is a `string.templatelib.Template` (PEP 750, 3.14). It exposes interpolations for a renderer. The language does not escape them. PEP 787 (subprocess t-string support) is Deferred and is not 3.14 behavior. f-strings still interpolate immediately.
- Source: https://peps.python.org/pep-0750/ ; https://peps.python.org/pep-0787/ ; https://docs.python.org/3/library/string.templatelib.html
- Source date: PEP 750 Final (3.14). PEP 787 status Deferred, targeted beyond 3.14.
- Reason: a new string literal is not a security boundary.

### PostgreSQL: any statement error aborts; 23505 is not blindly retryable

- Previous: retry guidance centered on `40001` / `40P01` and `25P02`, which made other SQLSTATEs look like the same retry. Case D6 already said any statement error aborts the transaction; that case was not rewritten.
- Updated: any statement error inside a transaction block aborts it. Further commands fail with `25P02` (`in_failed_sql_transaction`) until `ROLLBACK`. Retry the whole transaction, including the logic that chose the SQL. `40001` must be retried that way. `40P01` is advisable to retry that way. `23505` and `23P01` sometimes are really serialization conflicts and sometimes are persistent; do not retry them unconditionally. PostgreSQL does not retry automatically. psycopg's class name `InFailedSqlTransaction` is the driver spelling of that SQLSTATE.
- Source: https://www.postgresql.org/docs/18/mvcc-serialization-failure-handling.html (`40001`, `40P01`, `23505`, `23P01`) ; https://www.postgresql.org/docs/18/tutorial-transactions.html ("aborted state by the system due to an error") ; https://www.postgresql.org/docs/18/errcodes-appendix.html (`25P02` `in_failed_sql_transaction`).
- Source date: PostgreSQL 18 documentation, fetched 2026-10-02.
- Reason: retrying `23505` inside the same transaction, or retrying it as if it were always transient, both fail in production.

### pytest-asyncio 1.x loop scopes

- Previous: mixed session/module async fixtures with function-scoped tests were said to raise `ScopeMismatch`. Only `asyncio_default_fixture_loop_scope` was named. The removed `event_loop` fixture was not called out.
- Updated: in 1.4.0, unset `asyncio_default_test_loop_scope` means function scope for tests. Unset `asyncio_default_fixture_loop_scope` currently follows the fixture's cache scope, and the project says that unset default will become `function`. Set it explicitly. A fixture's loop scope must be at least its cache scope. Widening only the fixture loop while tests stay on function loops asks for two loops. The `event_loop` fixture was removed in pytest-asyncio 1.0. The exception name `ScopeMismatch` is not asserted. `MultipleEventLoopsRequestedError` was not re-verified against the 1.4 source and is not named.
- Source: https://pytest-asyncio.readthedocs.io/en/stable/reference/configuration.html (1.4.0)
- Source date: configuration page fetched 2026-10-02. Concepts background previously dated 2026-05-26; 1.0.0 release 2025-05-26 removed `event_loop`.
- Reason: the old exception name and the single ini key produced the wrong config change.

### PEP 639 license field

- Previous: `[project]` metadata did not say what `license` means.
- Updated: `license` is an SPDX license expression string; `license-files` lists files; the old license table and `License ::` classifiers are deprecated.
- Source: https://packaging.python.org/en/latest/specifications/pyproject-toml/ (PEP 639 history, December 2024) ; https://peps.python.org/pep-0639/
- Source date: PEP 639 Final; spec history entry December 2024.
- Reason: a table or classifier in `license` is the pre-639 shape.

### `pylock.toml` is interchange, not the native project lock

- Previous: `pylock.toml` was the standard lock interchange, without saying uv and Poetry still lock their own files. No record of the PyPA recommendations page disagreeing with Poetry.
- Updated: PEP 751 is the interchange format (initial approval April 2025; filename precedence clarification March 2026). uv keeps `uv.lock` and can export `pylock.toml`. Poetry 2.x reads PEP 621 `[project]` and still uses `poetry.lock`; export is via poetry-plugin-export on Poetry ≥ 2.3, not a replacement of `poetry.lock`. The PyPA tool-recommendations page (content dated 2026-09-22) still says poetry-core does not read `[project]`. Poetry's own 2.x docs contradict that. Trust the tool's docs for that tool. Poetry 2.5's "Python 3.15 support" is a Poetry release note, not a CPython production baseline.
- Source: https://packaging.python.org/en/latest/specifications/pylock-toml/ ; https://docs.astral.sh/uv/concepts/projects/layout/ ; https://docs.astral.sh/uv/concepts/projects/export/ ; https://python-poetry.org/docs/pyproject/ ; https://python-poetry.org/blog/announcing-poetry-2.3.0/
- Source date: pylock spec history April 2025 and March 2026. uv docs checked 2026-09-28. Poetry 2.3.0 announced 2026-01-18. Poetry docs pages dated 2026-09/10. PyPA recommendations content dated 2026-09-22.
- Reason: telling a Poetry repo to delete `poetry.lock` because pylock is "the standard lock" is a bad migration.

### SSRF address classification

- Previous: reject `is_private`, `is_loopback`, `is_link_local`, and `is_reserved`. No parse-failure or embedded-IPv4 rule.
- Updated: also reject `is_multicast` and `is_unspecified`. Parse failure is reject. On CPython 3.14.6, `ipaddress.ip_address` rejects the strings `2130706433` and `0177.0.0.1` rather than mapping them to loopback; other URL and socket parsers accept those spellings, so connect to the classified address object. If `ipv4_mapped` or `sixtofour` is set, classify the embedded IPv4 too. On 3.14.6, `2002:7f00:1::` has `sixtofour` 127.0.0.1 and `ipv4_mapped is None`. This was not re-run on 3.14.8. Do not reduce the rule to `is_global` alone.
- Source: https://docs.python.org/3/library/ipaddress.html ; local CPython 3.14.6 (tags/v3.14.6, Jun 10 2026) property check.
- Source date: local interpreter 2026-06-10 build, checked 2026-10-02. Not a 3.14.8 run.
- Reason: decimal and 6to4 spellings are real SSRF bypasses of a host-string check that only calls `ip_address` and then connects to the original string. The local parser does not itself accept the decimal form.

### Async generator early exit

- Previous: early `break` means `finally` does not execute promptly, and every `async for` should be wrapped in `aclosing`.
- Updated: `async for` does not by itself await `aclose()` when iteration stops early by `break` or exception. Cleanup can then run later, outside the iterating task. Use `contextlib.aclosing` when iteration can be abandoned before exhaustion. Full consumption is the other path.
- Source: https://docs.python.org/3/library/contextlib.html (`contextlib.aclosing`)
- Source date: 3.14.8 library docs.
- Reason: "always wrap" and "finally does not run" overstated the documented early-exit case.

### `torch.load`

- Previous: model files "often execute code on load," with no current `torch.load` default.
- Updated: stable `torch.load` signature still defaults `weights_only=True`. The warning still says never load untrusted data. `weights_only=False` is unrestricted pickle. `weights_only=True` restricts the unpickler and is not a complete sandbox (denial of service and other residual risk remain in the serialization notes). If the call omits the argument, `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD` selects unrestricted unpickling. An explicit `True` is not that path.
- Source: https://docs.pytorch.org/docs/stable/generated/torch.load.html (page dated 2026-09-29; signature and "Never load data from an untrusted source") ; https://docs.pytorch.org/docs/stable/notes/serialization.html (2.6 default; `weights_only` limits) ; https://docs.pytorch.org/docs/stable/miscellaneous_environment_variables.html (`TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD`, page dated 2025-06-17, PyTorch 2.13 docs tree)
- Source date: load page 2026-09-29; env-var page 2025-06-17; rechecked via search on 2026-10-02.
- Reason: treating every `torch.load` as arbitrary code execution, or treating the default as sufficient for untrusted uploads, are both wrong. The env var changes the omitted-argument default.

## Evals

- AS3: added a critical mistake for claiming one event loop runs its coroutines on multiple cores because the build is free-threaded. Existing "async is parallel" and "free-threading makes shared state safe" mistakes stayed.
- SE7: new case. Distinguishes the 3.14 `'data'` default, the 3.14.8 filter-bypass fixes (CVE-2026-82049, CVE-2026-19672, named in the case so a grader does not need the baseline), and the docs' limit that `'data'` is not every unsafe outcome. No eval for the `Never` PEP number, the SPDX spelling, or the PostgreSQL nuance (Case D6 already matched).

## Left unchanged on purpose

- `asyncio.gather` does not cancel siblings when one awaitable raises and `return_exceptions` is false. `TaskGroup` does cancel the rest. Case AS8 stands. Source: https://docs.python.org/3/library/asyncio-task.html
- SQLAlchemy `Session` is not safe to share across threads or asyncio tasks. `Engine.dispose(close=False)` in the child after fork matches the documented pattern. No upgrade-to-2.1 advice. Source: https://docs.sqlalchemy.org/en/20/orm/session_basics.html (page timestamp seen 2026-10-02; 2.0.45 was the labeled current release on the tutorial page, dated 2025-12-09).
- PEP 734 multiple interpreters stay conservative. Process isolation remains the mature choice. https://peps.python.org/pep-0734/
- OWASP Secure Coding with AI cheat sheet paraphrase was not expanded. https://cheatsheetseries.owasp.org/cheatsheets/Secure_Coding_with_AI_Cheat_Sheet.html
- FastAPI, Starlette, Django, Flask, and OpenTelemetry references had no hard version pin that this pass found stale. They were not rewritten.
- PEP 808, PEP 794, RISC-V as an official platform, `compression.zstd`, and Packaging Council notes were not added.
- JIT percentages were not copied into a rule.
- `deep-research-report.md` still says 3.14.7. It is a dated snapshot.
