# Dependency Review

## Contents

- [Scope & trigger](#scope--trigger)
- [Review contract](#review-contract)
- [Procedure](#procedure)
- [Checklist](#checklist)
- [Finding format](#finding-format)
- [False positives / legitimate exceptions](#false-positives--legitimate-exceptions)
- [Output expectations](#output-expectations)

Supply-chain review of what gets installed into the project and who can publish it. A dependency is an
attack surface plus an upgrade debt ([I12](../core/python-invariants.md)); provenance improves trust but
does not prove code safe. Packaging mechanics: [references/packaging.md](../references/packaging.md).

## Scope & trigger

Use when: a dependency is added, upgraded, or removed; a lockfile or version policy changes; release/CI
credentials are configured; a vulnerability advisory touches a used package; or generated code proposes
a new install ([principles §5](../core/engineering-principles.md)). Security consequences beyond the
supply chain route to [security-review.md](security-review.md); the release gate is
[production-readiness.md](production-readiness.md).

## Review contract

Follow the shared [review contract](code-review.md#review-contract) for task scope,
priority, severity, evidence, finding format, and a valid clean-review outcome.

## Procedure

1. **Establish the value case (I12).** For each addition: what does it replace, what gap does the
   existing stack have, and what is the simplest in-tree alternative? "It's popular" is not a value case.
2. **Map the transitive surface.** The direct dependency plus everything it pulls in; a small wrapper
   over a large tree is a large tree ([packaging.md](../references/packaging.md) on lockfiles).
3. **Check maintenance health**: recent releases, open issues triaged, bus factor, changelog discipline,
   migration burden from the pinned version.
4. **Check known vulnerabilities and license** compatibility for the intended distribution model.
5. **Check version policy and lockfile strategy** consistent with the artifact type (app vs library).
6. **Check provenance and release hygiene** (publishing identity, CI credentials, attestations) — with
   the standing caveat that provenance ≠ safety.
7. **Check install-time risk**: what code runs at build/install time (legacy `setup.py` builds,
   arbitrary build backends).
8. **Report** in the standard format. A rejected addition is a normal outcome of this review.

### Version policy quick reference

| Artifact type | Policy | Mechanism |
|---|---|---|
| Application / service | Exact pins (or bounded `~=`) + committed lockfile | Reproducible deploys; lockfile diff is the review unit |
| Library / package | Compatible ranges (`>=x.y,<x+1`) | Consumers resolve; overly tight pins break their resolution |
| Dev/test tooling | Pins in the app case; ranges acceptable in libraries | CI reproducibility where flakiness would mask real failures |
| Python version | Explicit floor in `requires-python`; CI matrix covers it | [modern-python-baseline.md](../references/modern-python-baseline.md) for what is current |

Lock interchange: `pylock.toml` (PEP 751) is the standard format [STANDARD]; tool-specific lockfiles
are fine when the team standardizes on that tool ([packaging.md](../references/packaging.md)). What
matters is that production installs come from a lock, not from floating resolution at deploy time.

## Checklist

| Check | Mechanism | Evidence to look for |
|---|---|---|
| Value case (I12) | Each dependency names what it replaces and the gap it fills | `pyproject.toml` change without stated reason; stdlib capability duplicated by a package |
| Transitive surface | Whole resolved tree reviewed, not just the direct dep | Lockfile diff showing the added subtree size; a "tiny" dep dragging in 20 packages |
| Maintenance health | Release cadence, issue triage, bus factor, changelog | Last release date, maintainer count, "maintained" claim checked against the repo, not the README |
| Known vulnerabilities | Advisory databases checked for the pinned range | OSV/GHSA/advisory links cited per finding; absence of advisories stated as "none known as of date" |
| License | License of every added package vs distribution model | License file/SPDX identifier; transitive license surprises (GPL in a shipped product) |
| Version policy | Pins for applications, compatible ranges for libraries | App repo with floating `>=` ranges; library needlessly pinning exact versions and breaking downstream resolution ([packaging.md](../references/packaging.md)) |
| Lockfile presence/strategy | Reproducible builds; lock interchange understood | No lockfile in an app; `pylock.toml` (PEP 751) or tool lockfile committed and refreshed in CI [STANDARD] |
| Provenance | Trusted Publishing / PyPI attestations where available | Attestation presence noted — **with the explicit caveat: provenance ≠ code safety**; review and pinning still required |
| CI/release credentials | Least-privilege, short-lived where possible | Long-lived PyPI tokens in CI env; broad cloud keys on build jobs; no environment protection on release workflows |
| Install-time risk | Build backend behavior understood | Executable `setup.py`-era builds [LEGACY]; unfamiliar custom build backends executing code at install |
| Typosquatting awareness | New package names checked against intended names | Near-miss names (`request` vs `requests`), fresh packages with sudden popularity, name confusion in generated code |
| Generated-code dependency adds | Agent-proposed installs double-checked | Every dependency suggested by generated code goes through this checklist before install ([principles §5](../core/engineering-principles.md)) |

## Finding format

Per [templates/code-review.md](../templates/code-review.md):
`Severity:` `Evidence:` `Why it matters:` `Recommended change:` `Trade-off:` `Verification:`.

### Example finding (shape only)

- **Severity:** Medium
- **Evidence:** `pyproject.toml` adds `quick-json-helper==0.3.1`; lockfile diff shows it pulls 9
  transitive packages; the package is 3 weeks old, one maintainer, no release history, and its name
  differs by one character from the popular `quickjson`.
- **Why it matters:** an unjustified, possibly typosquatting install path runs arbitrary code at build
  time in CI and at runtime (I12) — supply-chain risk with no offsetting value case.
- **Recommended change:** drop it and use the stdlib `json` already covering the stated use case; if a
  dependency is genuinely needed, pick the established package after this checklist passes.
- **Trade-off:** none material here; if performance of stdlib `json` were the concern, that is an
  [evidence-rules §3](../core/evidence-rules.md) measurement first.
- **Verification:** build with the dependency removed succeeds; `pip-audit`/advisory check run and
  recorded as of the review date.

Severity follows exploitability and reachable impact, not the SHOULD label. A vulnerable installed
package or typosquat can be High/Critical when used on an exposed path; missing reproducibility
controls matter when deploys can resolve differently (a lockfile is one option). A license conflict
matters when it applies to the distributed product. Evidence cites advisory IDs, resolved versions,
repo links, or license files — "this package looks risky" is not a finding.

## False positives / legitimate exceptions

- **Transitive dependencies of a well-chosen framework** are rarely flagged individually; the finding is
  the unreviewed surface as a whole or a specific bad package in it.
- **Library dependency ranges are common** because consumers resolve a shared environment. An exact
  constraint can still be justified by a known incompatibility; distinguish published metadata from a
  lock used only for library development ([packaging.md](../references/packaging.md)).
- **A young package can be the right choice** (solving a real gap, small auditable surface); flag
  absence of evidence as a stated risk, not an automatic rejection.
- **No advisories ≠ unsafe; advisories ≠ automatic removal** — exploitability in *this* usage decides
  severity ([principles §7](../core/engineering-principles.md)).
- **Dev/test-only dependencies** carry lower risk than runtime ones; scale depth accordingly.
- **Migrating the package manager or tool chain** is not this review's recommendation —
  Poetry→uv-style migrations need a named defect ([evidence-rules §4](../core/evidence-rules.md)).
- **`setup.py` in a legacy repo is a maintenance note, not a High**; it becomes a finding when the
  install path processes untrusted input or blocks a needed security property.

## Output expectations

- Lead with verdicts per dependency: accept / accept-with-conditions / reject, with the value case and
  the risk summary.
- "No significant issue found." is a valid result — state which packages were reviewed at what depth
  (direct only vs full tree, advisories checked as of which date). Never invent vulnerabilities.
- Every finding cites concrete evidence: advisory ID, lockfile diff, license file, repo activity link.
- Record the standing caveat in the output whenever provenance is discussed: attestations and Trusted
  Publishing improve provenance; they do not make code trustworthy.
- Record the review date with advisory findings — "none known" is only meaningful as of a date
  ([evidence-rules §6](../core/evidence-rules.md)).
