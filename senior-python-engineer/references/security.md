# Security

## Contents

- [Principle: trust boundaries](#principle-trust-boundaries)
- [Unsafe deserialization](#unsafe-deserialization)
- [eval / exec / dynamic code](#eval--exec--dynamic-code)
- [Subprocess and shell injection](#subprocess-and-shell-injection)
- [SQL injection](#sql-injection)
- [SSRF (server-side request forgery)](#ssrf-server-side-request-forgery)
- [Path traversal](#path-traversal)
- [Unsafe temp files](#unsafe-temp-files)
- [Secrets (I15)](#secrets-i15)
- [Authentication / authorization boundaries](#authentication--authorization-boundaries)
- [Input validation at boundaries (I1)](#input-validation-at-boundaries-i1)
- [Dependency and supply chain (I12)](#dependency-and-supply-chain-i12)
- [AI-generated code as untrusted proposed change](#ai-generated-code-as-untrusted-proposed-change)
- [Proportional risk](#proportional-risk)

Operational reference for Python-specific security. Governing invariants: I1 (validation boundaries),
I15 (secrets), I12 (dependency surface) in [python-invariants.md](../core/python-invariants.md);
review procedure in [security-review.md](../reviews/security-review.md);
[Engineering Principles §5](../core/engineering-principles.md) — generated code is untrusted proposed
code. Version-sensitive facts live only in [modern-python-baseline.md](modern-python-baseline.md).

## Principle: trust boundaries

- Every input from outside the process is untrusted until validated at the boundary (I1): network,
  files, DB contents read back, message queues, subprocess output, **and anything unpickled**.
- Threat model proportional to exposure [HEURISTIC]: local internal script ≠ internet-facing service.
  The same `eval` is a footgun in one and a vulnerability in the other — but both are smell-worthy;
  exposure changes the severity, not the direction.

## Unsafe deserialization

- **`pickle` can execute arbitrary code during load** [LANGUAGE] — `pickle.loads` on untrusted bytes is
  an execution vector. The same concern applies to unsafe YAML object loaders and `eval`-based formats.
  `marshal` is unsafe for untrusted bytes but loading it is not itself equivalent to pickle execution;
  a loaded code object becomes executable when passed to `exec` or an equivalent path.
- **`multiprocessing.Connection.recv()` auto-unpickles** received objects [STANDARD] — even "internal"
  IPC between processes is a trust boundary. If any process in the chain can be influenced by an
  attacker (or a compromised peer), `recv()` is an execution vector. Prefer raw bytes + explicit
  schema (JSON/protobuf/msgpack) across process/network boundaries where trust isn't absolute.
- Model checkpoints may use pickle-based loading ([ai-ml.md](ai-ml.md)): inspect the pinned loader's
  mode and the artifact's trust. Unrestricted pickle loading can execute code; restricted modes reduce
  that risk but do not make arbitrary untrusted files safe. Prefer safer serialization formats where
  the stack supports them ([current baseline](modern-python-baseline.md)).
- Safe alternatives: JSON/msgpack/protobuf with schema validation; `safetensors` for tensors where
  available [ECOSYSTEM]; signing/checksums for artifacts at rest.

## eval / exec / dynamic code

- `eval`/`exec`/`compile` on attacker-influenced strings = code execution. Legitimate uses exist
  (REPLs, template engines, config DSLs) but they need a sandbox or a restricted grammar (AST parsing
  of *data*, not code). "Limited" `eval` (`eval(input, {"__builtins__": {}})`) has a long history of
  escapes — don't build security on it [ECOSYSTEM].
- Dynamic import (`importlib.import_module(user_string)`) and `__import__` are the same class: allowlist
  module names; never format module paths from input ([architecture.md](architecture.md) plugin
  boundaries).

## Subprocess and shell injection

- For a native executable, pass a fixed executable and an argument list with `shell=False`; avoid
  composing command strings from untrusted text [STANDARD]. This removes the ordinary shell expansion
  path, but the target program still interprets its arguments.
- **Windows batch files:** `.bat`/`.cmd` may launch through a system shell even with `shell=False`.
  Prefer a native executable or direct API for untrusted arguments. If a batch wrapper is unavoidable,
  follow Python's documented Windows launch/escaping guidance and test the exact launch path on
  Windows; the docs discuss `shell=True` for this narrow case. Do not generalize that choice to other
  commands. `shlex.quote` is POSIX-specific and does not secure a Windows command line.
- For other deliberate shell composition, keep the command structure trusted and use a verified
  data-passing boundary. Source: [subprocess security considerations](https://docs.python.org/3.14/library/subprocess.html#security-considerations).
- **Template strings are not a safe shell or SQL API** [LANGUAGE]. PEP 750 (`t"..."` → `string.templatelib.Template`,
  Python 3.14) exposes literal parts and interpolated values so a renderer *can* escape them. A
  t-string is not a `str`, and nothing in the language escapes it for you. PEP 787 (subprocess/shlex
  consuming t-strings) is Deferred, not part of 3.14. f-strings still interpolate immediately.
- Argument injection survives without `shell=True` when the *tool* interprets flags: user input as
  `["grep", user_input]` can become `--include=/etc/shadow` if it starts with `-`. Use `--` separators,
  allowlists for values that become arguments, and never pass user input as option names.
- Allowlists > denylists for command/flag/argument selection. Set timeouts on all subprocess calls
  ([reliability.md](reliability.md)); kill process groups on timeout.

## SQL injection

- Use parameterized queries: `cursor.execute("... WHERE id = %s", (id,))` or ORM parameter binding
  [LANGUAGE/FRAMEWORK]. String formatting/`f"…{user_input}"` into SQL text is injection regardless of
  how "internal" the data seems.
- `typing.LiteralString` (PEP 675) [STANDARD] is an optional static check that query text was
  composed from literals. It does not bind parameters, and a literal can still be an unsafe value.
  Limits live in [typing.md](typing.md).
- **ORMs do not auto-fix raw text**: `Model.query.filter(f"name = '{name}'")` or
  `text(f"SELECT … {x}")` is injectable even inside an ORM session. Parameterize `text()` clauses;
  identifiers (table/column names) can't be parameterized — allowlist them.
- Second-order injection: values read from the DB and later formatted into SQL are still untrusted.
  Review any query built from stored content ([persistence.md](persistence.md)).

## SSRF (server-side request forgery)

- Any URL/host taken from user input and fetched by the server is SSRF: attacker aims the request at
  internal services (cloud metadata `169.254.169.254`, internal admin panels, localhost).
- Mitigations: allowlist schemes/hosts/ports; validate the IP address actually connected to. Parse with
  `ipaddress.ip_address` and reject `is_private`, `is_loopback`, `is_link_local`, `is_reserved`,
  `is_multicast`, and `is_unspecified`. Also classify `ipv4_mapped` and `sixtofour` embedded IPv4
  addresses. `ipaddress` rejects ambiguous literals (a bare decimal such as `2130706433`, or an octet
  with a leading zero) with `ValueError` — treat parse failure as reject. Other URL and socket parsers
  accept those spellings, so connect to the address object you classified, not to the raw host string.
  Re-check after DNS resolution and on every redirect hop (DNS rebinding). Do not pass raw user URLs
  to `requests.get`/`httpx.get` without an outbound policy.

## Path traversal

- User-influenced file paths must be constrained to an intended base directory. For a cooperative tree,
  resolve both the base and candidate and use a component-aware containment check (`Path.is_relative_to`
  or `os.path.commonpath`), not a string-prefix comparison. If an attacker can change directory entries,
  a check followed by `open()` has a symlink race; use directory-relative, no-follow opening or an
  equivalent platform-specific safe traversal.
- **Archive extraction (PEP 706)** [STANDARD]: pass `filter='data'` to `TarFile.extractall` /
  `TarFile.extract`. That is the documented filter for untrusted data archives, not a proof the archive
  cannot escape. The tarfile docs say `'data'` does not stop every unsafe outcome, and it does not cap
  size. Verify the actual patched interpreter and current advisories; a minor-version label is not
  evidence that all filter bypasses are fixed ([baseline](modern-python-baseline.md#upstream-status-snapshot)).
  From 3.14 the tar default is `'data'`; older supported versions require an explicit filter policy.
  Apply member-count, expanded-size, destination, and resource limits appropriate to hostile input.
  For `zipfile`, validate member paths and sizes separately; it has no tar `'data'` filter.
  See [tar extraction filters](https://docs.python.org/3.15/library/tarfile.html#extraction-filters).
- Open files with explicit encodings and least privilege; don't build paths by string concatenation
  with input.

## Unsafe temp files

- Predictable temp names (`/tmp/myapp-` + str(pid)) are race conditions (symlink attacks, clobbering).
  Use `tempfile.mkstemp`/`TemporaryFile`/`TemporaryDirectory` [LANGUAGE] — they create with safe
  permissions atomically. Clean up via context manager (I2), not `finally: os.remove` guesses.

## Secrets (I15)

- Secrets come from the environment/secret manager/config boundary — never hardcoded, committed,
  logged, or included in exceptions, error pages, or serialized artifacts (I15). `print`-debugged
  tokens and repr'd config objects in tracebacks are common leaks.
- **Timing attacks** [STANDARD]: compare API tokens, webhook signatures, and HMAC digests with
  `secrets.compare_digest` or `hmac.compare_digest`. `==` / `!=` can short-circuit on the first
  differing byte. `compare_digest` avoids that content short-circuit; the hmac docs still note that
  different lengths, or an error, can reveal type and length — not the values. Compare equal-length
  digests. Stored passwords go through the hasher's verify API, which should compare a fixed-length
  digest; `compare_digest` on raw passwords is not a password store.
- Rotate leaked secrets immediately (revocation beats deletion); history-preserving systems (git)
  make "remove it later" fiction. CI/CD secrets are attack surface: least-privilege scoped tokens,
  short-lived credentials, no secrets in PR builds from forks [ECOSYSTEM].

## Authentication / authorization boundaries

- Authenticate at one known boundary (middleware/deps, [web-frameworks.md](web-frameworks.md));
  authorize per-resource in use-case code — handler-level checks alone get bypassed by new endpoints.
- Distinguish authentication (who) from authorization (may); 401 vs 403 vs 404 semantics matter for
  information disclosure (don't reveal existence of unauthorized resources).
- Session/cookie handling: HttpOnly/Secure/SameSite, signed tokens with verified algorithms (reject
  `alg: none` — a known JWT pitfall [ECOSYSTEM]), expiry + rotation.

## Input validation at boundaries (I1)

- Validate **at the trust boundary** (Pydantic/validators, [typing.md](typing.md)); validate size
  limits (uploads, strings, list lengths) — validation without bounds checking is denial-of-service
  surface. Reject unknown fields where shape matters.

## Dependency and supply chain (I12)

- **PyPI attestations / Trusted Publishing improve provenance** (who published, from what CI) but do
  **NOT** prove code is safe [STANDARD/ECOSYSTEM]. Banned slogan: "PyPI attestations make dependencies
  trustworthy." Review dependencies: maintainer health, transitive tree, typosquatting, install-time
  code (`setup.py` runs arbitrary code at install — prefer wheels/`--only-binary` in constrained
  environments).
- Version policy: pin for applications ([packaging.md](packaging.md)); bounded ranges + lockfiles for
  libraries. Update cadence with changelog review; `pip-audit`/`osv`-style scanning for known CVEs
  [ECOSYSTEM] as signal, triage before reacting (not every CVE affects your usage).
- Vulnerability response: know your SBOM/lockfile inventory, have an upgrade path, and treat
  compromised-release incidents as security events (rotate credentials, diff releases).
- Least-privilege CI/release: publish tokens scoped per-project, protected branches/environments,
  no long-lived credentials in the repo or its logs (I15).

## AI-generated code as untrusted proposed change

- OWASP 2026 guidance [ECOSYSTEM]: an AI system must **not** both author security-critical code and be
  its own independent validation. AI-generated code is untrusted proposed change
  ([principles §5](../core/engineering-principles.md)) — check dataflow, dependencies, subprocess use,
  serialization, authorization, secrets, and tests before accepting, especially at the boundaries named
  in this file.
- **Coding-agent privilege is risk**: shell access, dependency installation, and credential access mean
  a compromised/prompt-injected agent is a compromise of the environment. Constrain agent execution
  (sandboxed env, no production credentials, reviewed dependency additions (I12), approval gates on
  network/secret-touching actions).
- Review priorities for generated code touching: auth logic, crypto, deserialization, subprocess,
  SQL — verify behavior, not just plausible syntax ([security-review.md](../reviews/security-review.md)).

## Proportional risk

- Scale security investment to exposure and impact: internal CLI processing trusted local data needs
  safe defaults (no `shell=True`, parameterized SQL, secrets handling); internet-facing services need
  the full boundary treatment (validation, authn/z, SSRF/path/limits, dependency review, monitoring).
- Document the residual risk you accepted and why — unspoken assumptions are how "internal tool"
  becomes "production attack surface."
