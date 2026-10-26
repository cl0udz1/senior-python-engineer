# Security Review

## Contents

- [Scope & trigger](#scope--trigger)
- [Review contract](#review-contract)
- [Procedure](#procedure)
- [Checklist](#checklist)
- [Finding format](#finding-format)
- [False positives / legitimate exceptions](#false-positives--legitimate-exceptions)
- [Output expectations](#output-expectations)

Trust-boundary review: where does untrusted data flow, what can it reach, and what privilege does the
runtime hold? This review is proportionate — depth scales with blast radius ([principles §7](../core/engineering-principles.md)).
A local analyst script and an internet-facing payment endpoint do not get the same paranoia.

## Scope & trigger

Use when: code crosses trust boundaries — network input, file uploads, archives, user-supplied paths or
URLs, deserialization, subprocesses, SQL, authn/authz changes, secrets handling, dependency additions;
the diff is AI-generated and touches security-critical surfaces ([principles §5](../core/engineering-principles.md));
a vulnerability class is being fixed ([SECURE] tasks); or a release touches anything internet-facing
([production-readiness.md](production-readiness.md) requires this review for trust boundaries).
Details of vulnerability classes: [references/security.md](../references/security.md).

## Review contract

Follow the shared [review contract](code-review.md#review-contract) for task scope,
priority, severity, evidence, finding format, and a valid clean-review outcome.

## Procedure

1. **Draw the trust boundaries of the change.** For each input source (HTTP, queue, file, archive, DB
   content originating from users, IPC, config), trace where the data flows and what it reaches
   (I1).
2. **Check the dangerous-reachability list** below — deserialization, code execution, shell, SQL, URL
   fetch, filesystem paths, temp files — at every boundary in the flow, not just the entrypoint.
3. **Check enforcement, not just UI.** Every endpoint/action is checked for authentication and
   authorization at the server side; hidden UI is not access control.
4. **Check secrets (I15).** Where do credentials come from, where can they surface (logs, error
   messages, traces, serialized exceptions, diffs, CI output)?
5. **Check the runtime identity's privilege.** Container user, DB grants, IAM scope, file permissions —
   least privilege limits the blast radius of everything above.
6. **Check dependencies added by the change** via [dependency-review.md](dependency-review.md); the
   install path is part of the attack surface.
7. **Scale the review depth** to the blast radius: quick pass for local low-privilege tooling; full
   adversarial pass for internet-facing, credential-handling, or deserializing code.
8. **Report** in the standard format. AI-authored security-critical code gets a second, independent
   check — the author agent must not be its only validator ([principles §5](../core/engineering-principles.md)).

### Proportionality: depth by blast radius

| System | Depth |
|---|---|
| Throwaway local script, no secrets, no network | Checklist items 1–3 spot-check; no threat modeling |
| Internal tool behind auth, touches internal data | Full checklist on input paths, secrets, authz |
| Internet-facing service / payment / auth / secrets store | Full adversarial pass: full data-flow tracing per input, dependency review, least-privilege audit, explicit threat statement |

## Checklist

| Check | Mechanism | Evidence to look for |
|---|---|---|
| Deserialization | `pickle` and unsafe YAML object loaders can instantiate attacker-chosen objects; `multiprocessing.Connection.recv()` auto-unpickles. `marshal` is unsafe for untrusted bytes but loading it is not itself equivalent to executing pickle opcodes | Trace whether less-trusted bytes reach pickle/YAML object loading or `marshal`; inspect what happens to any loaded code object |
| `eval`/`exec` | Dynamic code execution on influenced input | `eval`, `exec`, `compile(..., 'exec')` on strings derived from users/config/templates |
| Subprocess / shell injection | `shell=True` + interpolation re-parses metacharacters | `os.system`, `subprocess.run(f"...", shell=True)`, `os.popen` with variable content; fix = argument vector + allowlist |
| SQL injection | Raw SQL text even in ORM applications | `text(f"...")`, `.format`/`%`/f-strings building SQL, `execute` with concatenated values ([FRAMEWORK] SQLAlchemy `text()` binds params — use them) |
| SSRF | User-controlled URLs fetched server-side | Webhooks, importers, image fetchers, redirect-following clients; fix = scheme/host allowlist, DNS resolution check with `ipaddress` to block decimal/octal/IPv6 bypasses and private/link-local ranges |
| Path traversal / archive extraction | User-controlled paths or archive members can escape an intended root, overwrite files, or exhaust storage | Trace path resolution, member size, and the interpreter patch level. Missing `filter='data'` is the legacy trusted behavior on 3.12/3.13; on 3.14+ the unset default is `'data'`, which still does not cap size. Earlier 3.14 releases had filter bypasses fixed later ([baseline](../references/modern-python-baseline.md)). `zipfile` has no equivalent path filter [STANDARD] |
| Timing attacks on secrets | Content-short-circuiting equality on secrets | Tokens, API keys, and HMAC digests compared with `==` / `!=` instead of `secrets.compare_digest` or `hmac.compare_digest`. Different lengths can still leak length. Password checks belong to the hasher's verify API [STANDARD] |
| Temp file safety | Predictable names/races in shared temp dirs | `tempfile.mktemp`, fixed names in `/tmp`, world-readable temp writes of secrets; fix = `mkstemp`/`TemporaryDirectory` (I2) |
| Secrets handling (I15) | Credentials from a config/secret boundary; never in code, logs, errors, artifacts | Hardcoded live credentials or secrets exposed in logs/traces/CI; grade by validity, access, privilege, and exposure |
| Authn/authz enforcement | Every endpoint/action checks identity and permission server-side | New routes without auth dependency/middleware; object access without ownership check (IDOR); checks only in templates/JS |
| Input validation (I1) | External data validated/normalized at the boundary | Payloads/models used without schema validation; annotations treated as validation [STANDARD] |
| Dependency provenance | New/changed dependencies reviewed | Link to [dependency-review.md](dependency-review.md); typosquat check for newly named packages |
| AI-generated security code | Independent re-check of auth, secrets, subprocess, serialization, SQL, filesystem, network code | Checklist result recorded: what was verified vs assumed ([evidence-rules §6](../core/evidence-rules.md)) |
| Least privilege of runtime | Runtime identity cannot do more than the job needs | Container running as root; DB user with DDL rights for a read path; broad cloud IAM on a worker |

## Finding format

Per [templates/code-review.md](../templates/code-review.md):
`Severity:` `Evidence:` `Why it matters:` `Recommended change:` `Trade-off:` `Verification:`.

Grade by reachable impact and attacker control, not the MUST/SHOULD label
([invariants](../core/python-invariants.md#using-these-in-reviews)). `Evidence:` shows the data-flow
(source → sink) — "user-controlled" must be demonstrated, not assumed.

### Example finding (shape only)

- **Severity:** Critical
- **Evidence:** `api/import.py:24` fetches `request.json["avatar_url"]` with `httpx.get(...,
  follow_redirects=True)` and no scheme/host restriction; the service runs in the VPC that can reach
  `169.254.169.254` (instance metadata) and internal admin hosts.
- **Why it matters:** SSRF from an authenticated user's input path reaches cloud credential endpoints
  (I1) — exploitable, and credentials would then enter logs via error reporting (I15).
- **Recommended change:** allowlist scheme+host (expected image CDN), resolve and reject
  link-local/private ranges, disable redirects or re-validate after each hop.
- **Trade-off:** legitimate custom image hosts break unless allowlisted; provide an explicit
  registration path for them.
- **Verification:** test asserting `http://169.254.169.254/…` and a redirect-to-internal URL are both
  rejected; the same test fails against the old code.

## False positives / legitimate exceptions

- **Pickle between our own processes over an isolated channel** carrying only self-produced data is an
  accepted internal boundary — flagged only where less-trusted data or processes can reach it (also
  [concurrency-review](concurrency-review.md)).
- **Trusted internal artifacts with controlled provenance** may use fast formats; the finding begins
  where provenance is not actually controlled.
- **Deliberate trusted shell composition** (a fixed script with quoted constants) can use `shell=True`;
  uncontrolled input into it is the defect.
- **A local single-user tool with no secrets** needs a proportionate pass, not an OWASP full sweep
  ([principles §7](../core/engineering-principles.md)).
- **Framework-provided auth** (e.g. a framework's session/CSRF machinery [FRAMEWORK]) is not missing
  enforcement — but route-level permission checks still must be shown.
- **Internal-only endpoints** reduce exposure; they do not remove the validation requirement (I1) if any
  less-trusted system can reach them.
- **Security theater is also a finding**: flagging `eval` on a hardcoded literal string wastes the
  author's trust; proportionality cuts both ways.

## Output expectations

- Lead with Critical/High findings as source→sink flows a reader can follow, then the rest.
- "No significant issue found." is a valid result — and must name the trust boundaries checked and the
  depth applied (proportionality). Never invent vulnerabilities to appear thorough.
- Every fix names the mechanism (allowlist, argument vector, parameterized query, secret boundary,
  permission check) and its trade-off (broken legitimate flows, e.g. blocking a needed redirect).
- `Verification:` for security fixes names the proof: a test reproducing the exploit before/after, a
  config check, a scan command — not "code looks safe".
