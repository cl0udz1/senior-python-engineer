# LLM & Agentic Systems

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

**Modes:** DESIGN, IMPLEMENT, REVIEW · **Concerns:** SECURE · **Domains:** LLM_AGENTIC
Procedure for LLM-powered applications and agents. Governing rule: the model call is the *least*
deterministic component in the system — **bound it with validation, loop limits, and evaluation**
([Security](../references/security.md), [I6](../core/python-invariants.md)).

## 1. Typical system shape

- Loop shape: **prompt/context assembly → model call → tool execution → validation of result**, with explicit state and memory boundaries (what persists, where, for how long).
- The deterministic skeleton (tool schemas, validators, state machine, budgets) is real software; the model fills slots inside it. Design the skeleton first [HEURISTIC].
- Single-chain pipelines stay single-chain; "agents" are a loop with tool access and a stop condition — name the stop condition on day one.
- IF the task is a fixed sequence of LLM calls → a pipeline (functions in order) is complete architecture; orchestration frameworks add value only at named scale/complexity (§4).
- Prompt text is code: versioned, reviewed, and deployed like code — a prompt change alters behavior as much as a code change [HEURISTIC].

## 2. Important constraints

- **Latency variability**: model calls are seconds-scale with long tails; user-facing budgets and async/streaming UX are design inputs, not afterthoughts.
- **Cost per call**: tokens in/out × price is a unit-economics constraint; context growth per turn compounds ([Observability](../references/observability.md) for tracking).
- **Tool-call trust boundaries**: every tool is an actuator with real authority (file writes, HTTP, DB, code exec). The model's *suggestion* to call a tool is untrusted input, not authorization ([Security](../references/security.md)).
- **Non-determinism**: same input, different output; correctness must live in validators, contracts, and evals — not in "the prompt is right now".
- **Context growth**: unbounded history/memory degrades quality and explodes cost; retention policy is a design decision ([I6](../core/python-invariants.md) bounds apply to loops and memory alike).

## 3. Recommended discovery questions

Ask only what changes the design:
- What decisions does the model actually make, and what is the cost of a wrong one? (Validation depth, human-in-the-loop.)
- Which tools does it need, and what is the blast radius of each? (Permission model, sandboxing, §9.)
- Latency and cost budget per user interaction? (Model tier, caching, streaming, context size.)
- What must be consistent across turns/users — conversation state, memory, retrieval corpus? (State boundaries.)
- How will quality be judged — labeled examples, pairwise comparison, task success rate? (Eval design gates release, §8.)
- What are the adversarial inputs — untrusted web content, user uploads, multi-tenant data? (Prompt-injection surface, §9.)
- Expected concurrency? (Sync vs async, rate-limit planning, [Decision Model](../core/decision-model.md) §1.)
- Which outputs reach humans vs systems? (Validation and approval depth scales with actuation.)
- What happens when the provider is down or rate-limited? (Degraded mode, queue, or fail-fast — [Reliability](../references/reliability.md).)

## 4. Common architecture choices

- **Orchestration framework vs direct SDK** [ECOSYSTEM]: IF the app is one chain/few calls → direct SDK calls inside plain functions; observable, debuggable, no framework lock-in. BUT IF there are many tool types, durable execution, replay, or multi-step state machines with team scale → an orchestration framework earns its dependency ([I12](../core/python-invariants.md)). Both are ecosystem choices; the determinism discipline is identical.
- **Sync vs async** ([Decision Model](../core/decision-model.md) §1): IF many concurrent user sessions each waiting on model/tool I/O → async fits (async-native SDKs, bounded concurrency). BUT IF a batch pipeline calls models sequentially → sync; async adds cancellation complexity for no concurrency gain.
- **Caching**: IF identical prompts recur and staleness is acceptable → cache with explicit key, TTL, and stated staleness semantics ([Decision Model](../core/decision-model.md) §4). BUT IF outputs feed decisions where freshness matters → no cache, or cache only the deterministic sub-steps (retrieval, parsing).
- **Retrieval vs long context** [HEURISTIC]: choose using content size, relevance, update frequency,
  access boundaries, answer quality, latency, and cost. A few large or permission-separated documents
  can justify retrieval; many tiny documents may fit a simple context. Start with direct selection or
  lexical search where sufficient; add vector search when semantic matching earns its operational cost.
  Compare approaches on representative queries rather than imposing a document-count threshold.
- **Tool loop bound**: every agent loop has a max-iterations/deadline/token budget that *stops* the loop and reports (§6; [I6](../core/python-invariants.md)).
- **Human-in-the-loop**: IF the action's blast radius exceeds the validation's confidence → require explicit approval before the tool executes (least-privilege actuation, §9).

## 5. What not to overengineer

- Multi-agent frameworks for a single-chain task — each agent boundary is a latency + cost + eval multiplier ([I11](../core/python-invariants.md)).
- A vector database without a demonstrated retrieval need or advantage over simpler selection/search;
  fitting in a context window alone does not establish relevant, authorized, or cost-effective context.
- Custom memory architectures before basic conversation state is correct; reflection/planning loops without a measurable task where they help.
- Fine-tuning before prompt + retrieval + structured output has been measured and found insufficient [HEURISTIC]; fine-tuning is a data/eval commitment, not a prompt shortcut.
- Framework abstraction over one provider's SDK "for portability" nobody needs.
- Observability platforms with LLM-specific dashboards before basic per-call traces and token counts are logged.

## 6. Failure modes

Domain-relevant subset of [Failure Modes](../catalogs/failure-modes.md):
- **Unbounded tool loops** — agent retries/refines forever, burning money and side-effecting repeatedly; bound iterations, wall-clock, and tokens ([I6](../core/python-invariants.md)).
- **Prompt injection via tool output** — web pages, documents, emails, and DB rows contain instructions; the model obeys content over system intent. **External content is untrusted data, never instructions** ([Security](../references/security.md)); isolate it in context and never let it grant tool authority.
- **Retries doubling cost/side effects** — naive retry of a timed-out model call that already executed tools; retries need idempotency analysis like any other call ([I8](../core/python-invariants.md)).
- **No eval of quality** — prompt changes "look better" and ship; regressions discovered by users. Quality is a measured property (§8).
- **Context/memory growth** — quality and cost degrade as history accumulates; retention and compaction policy missing.
- **Tool over-permission** — one compromised/prompt-injected turn can write files and exfiltrate data because the process has full credentials ([Security](../references/security.md)).
- **Schema drift on structured output** — model returns plausible-but-wrong JSON; validate every structured response ([I1](../core/python-invariants.md)).

## 7. Performance considerations

- Evidence-first ([I9](../core/python-invariants.md), [Evidence Rules](../core/evidence-rules.md) §3): measure **cost per completed task** and latency distribution (p50/p95), not tokens alone.
- Dominant levers, in order: model tier choice per task difficulty → context size (trim history, retrieve narrowly) → parallelize independent calls ([Decision Model](../core/decision-model.md) §1) → cache with staleness semantics. Caching a stochastic output must state what "stale" costs.
- Prompt-token reduction (fewer, better examples; compact schemas) is usually the highest-leverage "optimization" [HEURISTIC].
- Streaming changes perceived latency without changing total latency; it does not fix slow tools ([web-api.md](web-api.md) UX notes apply).
- Attribute latency from a trace: a remote model call often dominates, while retrieval, tool I/O,
  local inference, or serialization may dominate in another system ([Evidence Rules](../core/evidence-rules.md) §3).
- Speculative parallel calls (fan-out several candidate responses) trade cost for latency — adopt only with a measured quality benefit [HEURISTIC].

## 8. Testing strategy

- Follow [Testing](../references/testing.md), adapted for nondeterminism:
  - **Deterministic skeleton tested conventionally**: tool schemas, validators, parsers, state transitions, budget enforcement — plain unit tests.
  - **Evaluation suite** for model-dependent behavior: task set + outcome metrics and calibrated rubrics.
    Run relevant cases after behavior changes; expand for release risk. Keep development cases separate
    from untouched evaluation tasks, and keep answer keys outside the agent workspace.
  - **Adversarial cases**: prompt-injection attempts via tool outputs, oversized/malformed tool responses, tool errors mid-loop.
  - **Loop/dry-run mode**: use a scripted fake-model harness for deterministic CI checks. Schedule
    live-model evaluations by behavior risk and cost; a cheap relevant subset may belong in PR checks,
    while broader repeated trials may suit a release gate [HEURISTIC].
- Golden transcripts for regression where outputs are snapshot-stable; tolerance for wording variance in free-text judgments.
- Chaos tests on the tool layer: tools timing out, returning garbage, or failing halfway through a loop.

## 9. Security concerns

- Treat the whole loop as a trust-boundary machine ([Security](../references/security.md), [Security Review](../reviews/security-review.md)):
  - **Prompt injection**: external content (retrieved docs, tool output, user uploads) is untrusted data; it must not modify instructions or grant capabilities. Separate instruction channels from data channels in context assembly.
  - **Tool permissions**: least privilege per tool; allowlists for commands/URLs/paths; human approval for high-blast-radius actions; sandbox where feasible.
  - **Output validation** ([I1](../core/python-invariants.md)): structured outputs schema-validated before acting; SQL/code generated by models goes through the same review gates as human code.
  - **Secrets** ([I15](../core/python-invariants.md)): the model and its logs see everything — never place secrets in prompts or context that is logged; redact tool outputs before logging.
  - Multi-tenant isolation: memory/retrieval stores scoped per user/tenant.

## 10. Deployment/lifecycle concerns

- Provider/SDK dependencies pinned ([packaging](../references/packaging.md)); model versions and prompt versions are deployable artifacts (prompts change behavior as much as code does [HEURISTIC]).
- Rate limits and quotas are capacity constraints; plan concurrency and backoff against provider limits ([Reliability](../references/reliability.md)).
- Observability: traces per call with model, tokens, latency, tool calls, and outcome ([Observability](../references/observability.md)); cost dashboards per feature; eval scores tracked over time.
- Rollback = previous prompt/model/tool config, deployable independently of code [HEURISTIC].

## 11. References for unresolved questions

Read only the section that answers an active question; this list is a menu, not a reading sequence.

- [references/security.md](../references/security.md) — prompt injection, tool authority, untrusted content handling (the core of this domain).
- [core/python-invariants.md](../core/python-invariants.md) — I1 (output validation), I6 (loop bounds/cancellation), I8 (retry idempotency).
- [core/decision-model.md](../core/decision-model.md) §1, §4 — sync/async per concurrency; caching staleness semantics.
- [references/testing.md](../references/testing.md) — eval/test strategy for nondeterministic systems.
- [references/observability.md](../references/observability.md) — tracing, token/cost metrics.
- [references/reliability.md](../references/reliability.md) — retries, rate limits, timeouts.
- [references/ai-ml.md](../references/ai-ml.md) — when fine-tuning/training enters the picture.
- [production-service.md](production-service.md) — when the app is a user-facing service.

## 12. Exit/readiness criteria

Apply the [mode-specific completion rules](../SKILL.md#task-modes) to the relevant criteria below.
Operational checks are release gates only when release readiness is in scope. Report actual evidence
and label proposed or unavailable checks.

### DESIGN completion

Specify tool authority, state/retention boundaries, loop budgets, failure and retry semantics, and an
appropriate evaluation and rollout plan. Record cost/latency assumptions and the proposed measurements.
A live provider, running evaluation suite, or production dashboard is not required for design completion.

### IMPLEMENT / release evidence

Apply the relevant items below to the delivered slice; live-provider and operational checks belong to
release readiness only when requested or required by the project gate.

- [ ] Tool permissions explicit: allowlist per tool, blast radius stated, approval gate for destructive actions.
- [ ] Loop bounds set and enforced: max iterations + wall-clock + token budget; exceeded = defined failure path ([I6](../core/python-invariants.md)).
- [ ] Relevant evaluation cases run and results recorded; distinguish deterministic harness checks from
      live-model trials. Release gates and remaining coverage are explicit.
- [ ] Cost/latency budgets stated; when a capacity or release claim is made, support it with measurements
      at the relevant concurrency rather than estimates presented as results.
- [ ] Prompt-injection posture stated: external content treated as data; structured outputs validated ([I1](../core/python-invariants.md)).
- [ ] Retry policy idempotency-analyzed, including tool side effects ([I8](../core/python-invariants.md)).
- [ ] Prompt/model/tool versions and rollback path recorded; production cost and quality monitoring
      verified when operational readiness is in scope ([Observability](../references/observability.md)).
- [ ] Provider outage behavior defined (degraded mode, queue, or fail-fast) and tested with a stubbed provider ([Reliability](../references/reliability.md)).
- [ ] Prompt changes flow through the same review/eval gate as code changes.
