# Engineering Principles

## Contents

- [1. Simplicity before architecture](#1-simplicity-before-architecture)
- [2. Conditional judgment over slogans](#2-conditional-judgment-over-slogans)
- [3. Evidence before optimization](#3-evidence-before-optimization)
- [4. Explicit ownership](#4-explicit-ownership)
- [5. Generated code is untrusted proposed code](#5-generated-code-is-untrusted-proposed-code)
- [6. Repository evidence outranks ecosystem preference](#6-repository-evidence-outranks-ecosystem-preference)
- [7. Proportionality](#7-proportionality)
- [8. Make behavior visible](#8-make-behavior-visible)
- [9. Verification is part of engineering](#9-verification-is-part-of-engineering)

The judgment layer of the Skill. These principles convert "senior engineer" from a tone into observable
behavior. Decision procedures live in [decision-model.md](decision-model.md); hard guardrails in
[python-invariants.md](python-invariants.md); evidence discipline in [evidence-rules.md](evidence-rules.md).

## 1. Simplicity before architecture

Prefer the least complex design that correctly satisfies the actual constraints and expected evolution.
Complexity must pay rent: every added indirection names the problem it solves, the alternative it beats,
and the cost it adds.

Things that require an explicit justification (not a ban — a justification):

dependency injection containers · repository layers · service layers · factories · plugin systems ·
event buses · CQRS · message queues · distributed systems · microservices · deep class hierarchies ·
aggressive async · caching · native extensions · additional dependencies · new infrastructure services.

Justification template: *"We add X because requirement/constraint R makes the simpler form Y materially
costly or risky in way F; X addresses F by mechanism M; cost is C (indirection, operational load, test
surface); the decision is reversible/irreversible."* If that sentence cannot be completed, keep the
simpler form.

A one-file utility is allowed to remain a one-file utility. A modular monolith is allowed to remain a
modular monolith. Small is not immature; unjustified indirection is.

[HEURISTIC] Each significant boundary should earn its maintenance cost. If removing a layer changes
nothing meaningful (clarity, testability, ownership, deployment, substitutability), the layer may be
ceremony. Conversely, dogmatic refusal of an abstraction (e.g., cramming multi-step business workflows,
transaction boundaries, and external API dispatches directly into web route handlers or CLI scripts across
multiple entrypoints) is under-engineering. The senior standard is the **least complex design that correctly
satisfies actual constraints and expected evolution**.

## 2. Conditional judgment over slogans

Never encode a slogan as a rule. Every maxim hides at least one condition. Structure decisions as:
`constraint → options → trade-offs → decision`.

Banned slogans and the conditional forms that replace them (mechanisms in
[decision-model.md](decision-model.md)):

| Slogan | Replace with |
|---|---|
| "Async is faster" | Async multiplexes waits; it does not speed up CPU work or blocking deps |
| "Repositories are best practice" | Abstraction justified only by a real boundary (alternates, ownership, test policy) |
| "Simplicity means zero abstractions" | The least complex design that satisfies constraints; under-engineering multi-entrypoint/transactional logic creates integrity debt |
| "Everything should be strictly typed" | Typing depth follows boundary value vs annotation cost |
| "Threads are useless because of the GIL" | Threads cover blocking I/O and native-release sections; pure-Python CPU parallelism needs processes, separate interpreters, validated free-threading, or native work |
| "Free-threading makes shared state safe" | It removes one lock, not data races or the need for ownership |
| "Microservices scale better" | Distribution adds failure modes; scale/ownership/fault domains must justify them |
| "ORMs are inherently slow" | Query shape and round trips dominate; measure SQL before blaming the ORM |
| "Dataclasses are automatically domain models" | A dataclass is a record; invariants and behavior are separate design work |
| "Don't repeat yourself" | Extract when the same rule must stay true in more than one place; leave copies that will change for different reasons ([architecture.md](../references/architecture.md)) |
| "Open for extension means add the hierarchy now" | Extend when a second real variant exists; a speculative subclass is ceremony |
| "Design patterns are best practice" | A pattern answers a problem you can point at in the current code; otherwise it is indirection (I11) |
| "A leading underscore makes it private" | A single leading underscore is a convention [LANGUAGE]; it does not block callers |
| "uv is a Python packaging standard" | Standards are pyproject.toml/pylock.toml; frontends are workflow choices |
| "Ruff replaces every Python tool" | Tool consolidation is a repo-level trade-off decision |
| "Python is too slow for ML" | Python usually orchestrates native kernels; measure where time actually goes |
| "PyPI attestations make dependencies trustworthy" | Provenance ≠ safety; review and pinning still required |

Operational form: **IF** conditions C hold **THEN** consider X **BUT IF** constraints D hold **THEN**
prefer Y. If a piece of guidance cannot survive being made conditional, it does not belong in this Skill.

## 3. Evidence before optimization

Performance work follows representative measurement: define workload → measure → classify bottleneck →
improve the dominant cost → re-measure. Migration work names a concrete defect, evidence that the new
choice addresses it, and transition cost. Full protocol: [evidence-rules.md](evidence-rules.md).
"Python looks slow in a hot system" is not evidence for a Rust rewrite; a profile naming the cost center is.

## 4. Explicit ownership

Ambiguous ownership is an architectural smell, not a detail. For every one of the following, be able to
name the owner and the release point: mutable state · database sessions · transactions · files/sockets/
connections · locks · tasks · processes · queues · configuration · caches · lifecycle (startup/shutdown) ·
retries · cancellation. If two modules can mutate the same state and neither owns it, fix that before
adding features.

Ownership questions that expose problems quickly:

- Who creates this, who destroys it, and when?
- Which request/task/thread is allowed to touch it concurrently (if any)?
- What happens to it on cancellation, timeout, and shutdown?
- Where is its failure visible — and where could it be silently swallowed?

## 5. Generated code is untrusted proposed code

[HEURISTIC] Treat code produced by an agent as a proposal requiring verification. Syntactic plausibility
is not correctness, and a green test run is not a
design review: leaked steps, a type that cannot stand in for its base, and a pattern with no problem
still count ([architecture.md](../references/architecture.md)). Inspect with heightened scrutiny
anything crossing: authentication · authorization · secrets · subprocesses · shell execution ·
serialization/deserialization · filesystem access · SQL and database behavior · network boundaries ·
privilege boundaries · dependency additions · concurrency structures.

An agent's own checklist is self-review, not independent validation. For security-critical changes,
seek an independent reviewer or independent checks proportionate to risk; report the checklist result
([code-review.md](../reviews/code-review.md), and [security-review.md](../reviews/security-review.md)
where trust boundaries are involved), what was verified, and what remains unverified.

## 6. Repository evidence outranks ecosystem preference

Local conventions, tooling, and architecture are the starting point for that repository. Propose change
when a named correctness, security, requirement, or maintenance problem warrants it. Procedure:
[existing-codebase.md](../playbooks/existing-codebase.md).
The same restraint applies to versions and tools: time-sensitive facts are in
[modern-python-baseline.md](../references/modern-python-baseline.md), and pre-release or
[EXPERIMENTAL] capabilities are never ordinary defaults.

## 7. Proportionality

Effort, ceremony, and paranoia scale with **risk × blast radius**, not with aspiration:

- A throwaway analyst script does not need DI, layered architecture, or a full CI matrix.
- An internet-facing payment endpoint does not get "it probably works".
- Test depth, typing depth, review depth, and observability depth are all chosen per risk
  ([testing](../references/testing.md), [observability](../references/observability.md)).

Proportionality also governs questions: ask when the missing fact would change the decision; decide when
it would not. Endless requirement questioning is failure to engineer; a stated assumption plus a cheaply
reversible decision is usually the senior move.

## 8. Make behavior visible

Failure behavior, retries, timeouts, and side effects must be visible in the code and in the design:
explicit over implicit (imports, globals, environment reads), visible over swallowed (exceptions),
documented over assumed (transaction boundaries, idempotency). Readability is an engineering property —
[HEURISTIC] "Pythonic" means readable and predictable use of Python's object model, not clever compression.
PEP 20 is informational [STANDARD]; its aphorisms balance purity against practicality.

## 9. Verification is part of engineering

A claim about behavior carries evidence: a test that runs, a reproduction, a measured number, or a cited
specification/documentation page. "Should work" is not a delivery state for code crossing trust
boundaries or data-critical paths. Where evidence is impossible now, mark the assumption and the cheapest
way to close it later.
