# Security Automation / SOC Tooling

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

**Modes:** DESIGN, IMPLEMENT, REVIEW · **Concerns:** SECURE · **Domains:** SECURITY_AUTOMATION
Procedure for collectors, parsers, detection/analysis logic, and automated response tooling.
Governing rule: **the inputs are hostile by construction** — parsers and tool invocations are the
attack surface ([Security](../references/security.md), [I1](../core/python-invariants.md)).

## 1. Typical system shape

- Flow shape: **collectors/parsers → analysis (rules/detections) → action + audit trail**. Each stage takes typed, validated input and emits typed output with provenance.
- Parsers are the risk center: they consume attacker-influenced bytes (pcap, logs, malware samples, archives, API responses). For complex binary formats, an audited memory-safe parser (for example, Rust) can reduce memory-corruption risk; C/C++ parsers need separate memory-safety controls. Python can orchestrate around either choice (§4).
- Actions (block, isolate, notify, ticket) are explicit, permissioned operations with audit records — never incidental side effects of analysis code.
- Evidence integrity: collected artifacts preserved with hashes/chain-of-custody; analysis is repeatable from stored inputs.
- Every stage emits typed output with provenance (source, parser version, run ID) — findings without provenance are not evidence [HEURISTIC].

## 2. Important constraints

- **Hostile input**: assume every parsed artifact is crafted to break the parser; fuzzing and bounds are part of normal development, not hardening extras ([Security](../references/security.md)).
- **Least privilege**: collectors and responders hold scoped, minimal credentials; a compromised detection job must not yield infra-wide access ([I15](../core/python-invariants.md)).
- **Auditability**: who/what/when/why for every automated action; SOC automation without an audit trail is unauditable enforcement [HEURISTIC].
- **Evidence integrity**: tamper-resistant storage for collected artifacts and action logs; results must be reproducible for review/legal processes.
- **Failure visibility**: a silently failing detection rule = a blind spot ([I13](../core/python-invariants.md)).

## 3. Recommended discovery questions

Ask only what changes the design:
- What formats are parsed, from whom, and how large/complex? (Parser language/threat model, §4.)
- What is the blast radius of an automated action? (Approval gates, dry-run defaults.)
- What must be provable after the fact? (Audit/evidence retention requirements.)
- Which credentials does each stage need, and what can it reach? (Least-privilege scoping, §9.)
- What is the acceptable detection latency vs throughput? (Batch vs streaming analysis.)
- What happens when a rule is wrong — false-positive cost vs false-negative cost? (Tuning/alerting design.)
- Where do secrets for third-party security tools live? ([I15](../core/python-invariants.md).)
- Who reviews automated actions, and how would a bad rule be rolled back fast? (Rule versioning, kill switch.)
- What is the retention and access policy for captured artifacts? (Evidence handling, §9.)

## 4. Common architecture choices

- **Parser language**: IF parsing complex untrusted binary formats creates a credible memory-corruption risk in the available parser stack → an audited memory-safe component (e.g. Rust via PyO3) can be justified by the threat model even without a speed profile. For a performance-driven rewrite, require profile evidence and a stable boundary ([Decision Model](../core/decision-model.md) §6). BUT IF inputs are structured text/JSON/CSV with schemas → Python with boundary validation ([I1](../core/python-invariants.md)) is usually enough; don't outsource text parsing by default.
- **Subprocess hygiene**: IF external security tools must be invoked → argument vectors, allowlists of binaries, no `shell=True` with controllable input ([Security](../references/security.md)); capture output as untrusted data.
- **Safe deserialization**: IF intermediate artifacts are stored/transported → schema'd formats (JSON/parquet with validation); **never pickle** collected artifacts or IPC payloads ([Security](../references/security.md); note `multiprocessing.Connection.recv()` auto-unpickles [STANDARD]).
- **Rule execution**: IF rules are data-driven → rule engine with versioned rule definitions, test corpus per rule, and per-rule failure isolation ([I13](../core/python-invariants.md)). BUT IF rules are code → normal code review + tests; dynamic `eval` of rules-as-strings is a vulnerability, not a feature.
- **Automated response**: IF action blast radius is high → dry-run default + human approval + replayable audit; IF low and reversible → automate with monitoring ([principles §7](../core/engineering-principles.md) proportionality: name what would raise the bar).

## 5. What not to overengineer

- Agent frameworks (LLM or otherwise) orchestrating scripted response playbooks — deterministic scripts with clear exit codes beat autonomous action for enforcement [HEURISTIC] ([I11](../core/python-invariants.md)).
- Custom rule DSLs before plain Python/SQL rules prove insufficient; generic "SOAR platform" abstractions for three integrations.
- Microservices per pipeline stage; Kafka-class streaming for hourly batch correlation.
- ML-based detection before the rule-based baseline and its measurement exist ([Evidence Rules](../core/evidence-rules.md) §3 applies: measure detection quality first).
- Hand-rolled parsers for formats with maintained libraries — but vet those libraries ([I12](../core/python-invariants.md)).
- Full data-lake architecture for one team's alert triage backlog.

## 6. Failure modes

Domain-relevant subset of [Failure Modes](../catalogs/failure-modes.md):
- **Unsafe pickle of collected artifacts** — unrestricted `pickle` or `torch.load(..., weights_only=False)` on quarantine samples/IPC can execute attacker code; check the pinned deserializer's safety mode and keep malware artifacts untrusted ([Security](../references/security.md)).
- **Shell injection in tool invocation** — detector commands built by string formatting with attacker-influenced fields (hostnames, filenames); use argument vectors + allowlists.
- **Silent rule failure** ([I13](../core/python-invariants.md)) — a rule throwing on new input formats is skipped unnoticed for weeks; per-rule error isolation + failure alerting.
- **Secrets in logs** ([I15](../core/python-invariants.md)) — API keys for threat feeds/EDR in debug logs and ticket text; centralized redaction.
- **Parser crashes/DoS** — malicious inputs kill collectors or exhaust memory; bounds, timeouts, and resource limits per input ([Security](../references/security.md)).
- **Poisoned evidence chain** — actions recorded without input provenance; findings cannot be defended or reproduced.
- **Credential overreach** — one automation token that can both read all logs and modify firewall rules ([I15](../core/python-invariants.md)).

## 7. Performance considerations

- Evidence-first ([I9](../core/python-invariants.md), [Performance](../references/performance.md)): profile representative *attacker-shaped* inputs — worst-case, not average ([Evidence Rules](../core/evidence-rules.md) §3).
- Volume reality check: log/pcap processing at real volume is I/O + parsing bound; batch reads, streaming parses, and pushdown to search/SQL engines usually beat Python-loop over every event [HEURISTIC] ([data-engineering.md](data-engineering.md) patterns apply).
- Parser hot paths over untrusted binary data may justify a native memory-safe component. For safety, document the threat model and available parser alternatives; for speed, profile the workload and check that the boundary is stable ([Decision Model](../core/decision-model.md) §6).
- Analysis correlation: bounded lookback windows and keyed joins; unbounded in-memory correlation state is a self-DoS.
- Rule evaluation cost is often dominated by data fetch, not rule logic; batch and cache lookups with freshness semantics ([Decision Model](../core/decision-model.md) §4).

## 8. Testing strategy

- Follow [Testing](../references/testing.md), with security-specific depth:
  - **Parser fuzzing/property tests** on hostile-shaped inputs (mutated samples, truncated files, oversized fields) — a normal part of parser CI here ([Security](../references/security.md)).
  - **Detection corpus per rule**: true-positive samples must fire; known false-positive samples must not. Rule changes run the corpus.
  - **Action tests**: dry-run vs apply paths; audit record completeness asserted.
  - **Injection tests**: malicious filenames/hostnames/fields through tool-invocation and logging paths.
- Regression corpus of real (sanitized) artifacts; sanitized means *actually* sanitized ([I15](../core/python-invariants.md)).
- Injection/regression tests run per rule change against the corpus before deployment (§10).

## 9. Security concerns

- This domain is its own attack surface ([Security](../references/security.md), [Security Review](../reviews/security-review.md)):
  - Untrusted parsing: bounds, timeouts, memory-safe parsers for binary formats; treat parser output as untrusted too.
  - Deserialization: no pickle of collected artifacts or IPC; schema-validate everything crossing a boundary ([I1](../core/python-invariants.md)).
  - Subprocess: validate executable/arguments and control the environment; no shell interpolation of
    evidence-derived strings. Prefer native executables, and inspect Windows batch wrappers separately
    ([subprocess platform guidance](../references/security.md)).
  - Least privilege per stage; short-lived scoped credentials; separation between "read telemetry" and "change infra" roles.
  - Secrets ([I15](../core/python-invariants.md)): feed/API credentials in secret boundary; redaction in logs, tickets, and exported evidence.
- Automated enforcement can have a high blast radius. Review generated changes and run relevant
  hostile-input/failure checks; arrange independent review when the release policy or risk warrants it.
  If that review is unavailable, finish the scoped implementation and its checks, report the pending
  release gate, and do not describe self-review as independent validation ([Security](../references/security.md)).

## 10. Deployment/lifecycle concerns

- Deployments of detection code change detection behavior: version rules + code together, run corpus before rollout ([Testing](../references/testing.md)).
- Credential rotation and revocation procedures documented; break-glass path defined for automation failure ([Reliability](../references/reliability.md)).
- Audit/evidence retention: storage policy, access control, tamper evidence ([Observability](../references/observability.md) for the action log).
- Scheduling/overlap for collection jobs ([workers-jobs.md](workers-jobs.md) rules apply: idempotent re-runs, drain, alerting).
- Kill switch: how to disable a misbehaving automated action or rule in minutes, documented and rehearsed ([Reliability](../references/reliability.md)).

## 11. References for unresolved questions

Read only the section that answers an active question; this list is a menu, not a reading sequence.

- [references/security.md](../references/security.md) — deserialization, subprocess hygiene, injection classes, secrets (the core of this domain).
- [core/python-invariants.md](../core/python-invariants.md) — I1, I13, I15 dominate; I3 for collector startup.
- [core/decision-model.md](../core/decision-model.md) §6 — when a native parser component is justified.
- [references/testing.md](../references/testing.md) — fuzzing/property tests, corpus-driven rule testing.
- [references/reliability.md](../references/reliability.md), [references/observability.md](../references/observability.md) — action audit trails, alerting on rule failure.
- [data-engineering.md](data-engineering.md) — volume patterns for collection/ETL stages.
- [workers-jobs.md](workers-jobs.md) — scheduled collectors and their idempotency/drain rules.
- [reviews/security-review.md](../reviews/security-review.md) — review gate for parser/action code.

## 12. Exit/readiness criteria

Apply the [mode-specific completion rules](../SKILL.md#task-modes) to the relevant criteria below.
Operational checks are release gates only when release readiness is in scope. Report actual evidence
and label proposed or unavailable checks.

Observable checklist:
- [ ] Parser threat model stated per format (source trust, complexity, memory-safety approach); hostile-input tests/fuzzing in CI.
- [ ] Least-privilege credentials per stage, verified (scope documented; read/change separation enforced).
- [ ] Action auditability: every automated action has who/what/when/why record with input provenance; evidence artifacts hashed.
- [ ] Deserialization safe: no pickle/unsafe loads of collected artifacts or IPC ([Security](../references/security.md)).
- [ ] Subprocess invocations pass hygiene check (argument vectors, allowlists, no shell interpolation).
- [ ] Rule failure visibility: per-rule error isolation + alerting ([I13](../core/python-invariants.md)); detection corpus runs on every rule change.
- [ ] Secrets absent from logs/tickets/exports ([I15](../core/python-invariants.md)); rotation/revocation documented.
- [ ] Rule versioning + kill switch exist; bad-rule rollback rehearsed.
- [ ] Artifact retention/access policy defined; provenance recorded on every finding.
