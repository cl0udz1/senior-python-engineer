# Modern Python Baseline

Use this file for version-sensitive decisions, not as a mandate to upgrade a repository. Interpret the
[knowledge layers](../SKILL.md#knowledge-classification) separately: language guarantees, implementation
behavior, library contracts, and engineering policy have different scopes.

## Contents

- [Choose a project baseline](#choose-a-project-baseline)
- [Upstream status snapshot](#upstream-status-snapshot)
- [Version-scoped capabilities](#version-scoped-capabilities)
- [Tool and framework status](#tool-and-framework-status)
- [Use and refresh current facts](#use-and-refresh-current-facts)

## Choose a project baseline

1. Read the repository's declared Python range, CI matrix, deployment interpreter, dependency pins,
   native-extension support, and consumer compatibility promises.
2. Keep that supported range for a scoped fix unless a concrete incompatibility, support deadline, or
   security requirement makes a change necessary. A newer upstream minor release alone is not that reason.
3. For a new project, choose a supported version that its dependencies and deployment platform actually
   support. Use the current suitable patch release for that branch; verify it at decision time.
4. Separate a patch/security update from a minor-version migration. Name the affected behavior and run
   relevant compatibility checks before changing syntax, public APIs, interpreter build, or lockfiles.
5. If current facts cannot be verified, state the last verified date and the unresolved question. Do
   not present this snapshot or a planned release date as a live status check.

## Upstream status snapshot

**Verified on 2026-10-26.** This table records observed official status, not the project's tested range.
It will become stale; recheck the release page and support schedule before recommending an upgrade.

| Branch | Official status at verification | Release page checked |
|---|---|---|
| 3.15 | Stable, bugfix | [3.15.2](https://www.python.org/downloads/release/python-3152/), released 2026-10-25 |
| 3.14 | Stable, bugfix | [3.14.10](https://www.python.org/downloads/release/python-31410/), released 2026-10-25 |
| 3.13, 3.12, 3.11 | Security maintenance | Check the branch's current release and distributor policy when needed |
| 3.10 | Upstream end of life | Plan supported-runtime migration when this is the deployed branch |

Branch status source: [Python Developer's Guide](https://devguide.python.org/versions/).
Both checked maintenance releases are expedited security releases. Security decisions also depend on
exposure and distributor backports; verify the deployed build rather than inferring patch coverage from
its minor-version label. This is not an exhaustive advisory inventory. Archive handling guidance is in
[security.md](security.md#path-traversal).

## Version-scoped capabilities

| Capability | Verified scope and status | Engineering consequence |
|---|---|---|
| Deferred annotation evaluation | Python 3.14, PEP 649/749 [LANGUAGE/STANDARD] | Use the matching introspection API; annotations still do not validate runtime values. See [typing](typing.md). |
| Multiple interpreters | Python 3.14 adds `concurrent.interpreters` [STANDARD] | Check dependency support and communication cost; select isolation for the actual failure model. |
| Free-threaded CPython | An optional supported build in 3.14 [CPYTHON] | Audit shared state and extensions; support does not make every package compatible or eliminate races. |
| Free-threaded stable ABI | Python 3.15 introduces `abi3t` [CPYTHON/STANDARD] | Do not assume a 3.14 free-threaded wheel can use it; verify build-tool support and the extension's API constraints. |
| Lazy imports and other 3.15 additions | Stable 3.15 includes explicit lazy imports, `frozendict`, `sentinel`, and UTF-8 default encoding [LANGUAGE/STANDARD] | Use only within the repository's supported range; assess import side effects and encoding compatibility on migration. |
| JIT | 3.14 and 3.15 documentation still labels it experimental [CPYTHON/EXPERIMENTAL] | Check the actual binary, platform, profiler support, and workload; do not transfer 3.14 build restrictions to 3.15 without checking. |
| Garbage collection | 3.14.0–3.14.4 used an incremental collector; 3.14.5 reverted to the earlier generational design [CPYTHON] | Patch-level implementation details are not portable latency guarantees. |
| Process startup | `fork` is not the default on any platform from 3.14 [STANDARD/CPYTHON] | Use the actual platform/context contract; libraries should accommodate caller-provided contexts. |

Primary references: [3.14 changes](https://docs.python.org/3.14/whatsnew/3.14.html),
[3.15 changes](https://docs.python.org/3.15/whatsnew/3.15.html),
[free-threading guidance](https://docs.python.org/3.15/howto/free-threading-python.html), and
[multiprocessing contexts](https://docs.python.org/3.14/library/multiprocessing.html#contexts-and-start-methods).

A free-threaded build may re-enable the GIL when loading an incompatible extension. Verify the complete
runtime stack before depending on GIL-free behavior. One asyncio event loop still runs its callbacks
serially in its owning thread; use documented thread-safe handoff APIs for cross-thread access. See
[asyncio and free threading](https://docs.python.org/3.15/library/asyncio-threading.html) and
[concurrency guidance](asyncio-concurrency.md#free-threaded-cpython-and-multiple-interpreters).

`tarfile` defaults to the `data` filter from 3.14, while earlier versions need an explicit policy;
that filter is not a complete sandbox or decompression resource limit. `zipfile` has different APIs.
Check each module's patched behavior separately; do not apply tar filter claims to ZIP files.
Source: [tar extraction filters](https://docs.python.org/3.15/library/tarfile.html#extraction-filters).

## Tool and framework status

**Verified on 2026-10-26.** Keep framework claims tied to the installed major/minor version.

| Topic | Scoped status | Use in decisions |
|---|---|---|
| TorchServe | Its official documentation says active maintenance and planned fixes/security patches have ended | Assess existing deployments and migration cost; do not offer it as an unqualified new-production default. [Notice](https://docs.pytorch.org/serve/) |
| SQLAlchemy mypy plugin | SQLAlchemy 2.0 documents deprecation and compatibility only through mypy 1.10.1 | Prefer native typed mapping APIs for new 2.x mappings; inspect legacy pins before proposing a migration. [Plugin documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/mypy.html) |
| SQLAlchemy relationship loaders | In 2.0, legacy `noload` can expose empty/None state; `raiseload` has an error contract | Choose behavior explicitly; neither name proves an object has no related database rows. [Relationships](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html) |
| `pylock.toml` | Standardized lockfile format [STANDARD] | Verify import/export support in the pinned tools; it does not replace every frontend's native lockfile. [Specification](https://packaging.python.org/en/latest/specifications/pylock-toml/) |
| PyTorch checkpoint loading | `torch.load` in the checked 2.14 docs defaults to `weights_only=True` [FRAMEWORK] | Keep the argument explicit when it is the intended policy. Restricted loading does not make untrusted files safe; see [loading](https://docs.pytorch.org/docs/2.14/generated/torch.load.html) and [serialization](https://docs.pytorch.org/docs/2.14/notes/serialization.html). |

For PyTorch 2.14, `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` selects unrestricted loading only at call sites
that omit `weights_only`; an explicit `True` retains that call-site policy. Audit environment overrides
and trusted artifact provenance as well as the function call.

`pyproject.toml` and packaging specifications define interoperability; pip, uv, Poetry, PDM, Hatch, and
other frontends define workflows. Preserve the repository's toolchain unless a named problem warrants
change. Select linters and type checkers by the defects they prevent, ecosystem compatibility, and the
team's existing checks. See [packaging](packaging.md) and [tooling](tooling.md).

## Use and refresh current facts

- Recheck release/security status for an upgrade, deployment, newly reported advisory, or unsupported
  branch. Recheck framework APIs against the installed version before proposing code that uses them.
- Record a consequential changed claim with its source URL, affected version/platform, verification
  date, affected files, and next review trigger in the separate maintainer source ledger. Do not use
  archived research or opaque citation markers as evidence of current status.
- Keep stable mechanisms in their relevant reference; keep release and maintenance snapshots here.
  Reconcile summaries and evaluation expectations when a canonical claim changes.
- Mark gaps honestly. A live documentation check is not a runtime compatibility test; a single
  interpreter reproduction is not evidence for all Python versions, operating systems, or builds.
