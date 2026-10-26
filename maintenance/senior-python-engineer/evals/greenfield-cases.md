# Greenfield Cases

New-system work: scope calibration and proportionality. The recurring trap is size-blindness — treating
every request as an occasion for architecture. Cases route through
[playbooks/greenfield-project.md](../../../senior-python-engineer/playbooks/greenfield-project.md); grading follows
[expected-behavior.md](expected-behavior.md) (all forbidden behaviors apply; the ones most likely here:
architecture astronautics, cargo cult, architecture to look senior, endless questioning).

---

### Case G1 — Tiny rename utility

**Input**
> "Build a script that renames 50 image files in a folder from `IMG_1234.jpg` style names to
> `2026-09-28_trip_001.jpg` style names, numbered in the order the files currently sort. I'll run it
> once on my laptop."

**Context**
Personal one-shot task. No repo, no team, no tests infrastructure, no deployment. The "system" is one
directory of 50 files on a laptop.

**Desired reasoning behavior**
Scale the solution to the request: this is a one-file script with explicit failure behavior, nothing
more. State the small number of real risks — name collisions in the target pattern, partial rename on
mid-run failure, wrong ordering assumption — and handle or surface them cheaply (e.g. dry-run listing,
abort on collision). No architecture vocabulary appears unless tied to a named constraint, which does
not exist here. (I13, I16; [decision-model](../../../senior-python-engineer/core/decision-model.md) §0 "simplest correct solution";
[templates/blueprint.md](../../../senior-python-engineer/templates/blueprint.md) "a one-file utility gets a few sentences".)

**Acceptable outcomes**
1. One small script (`pathlib`, sort, rename loop) with a collision check and either dry-run mode or an up-front preview; a couple of sentences on ordering and what happens on failure.
2. Same script plus 3–5 lines noting that if this grows (recursive trees, other patterns, reruns) it should become a proper CLI — stated as a condition, not built now.
3. Script with a `--dry-run` flag added because re-running after a partial rename is the one real hazard — justified by that hazard, not by "best practice".

**Failure modes**
- DDD layering: entities, value objects, a `FileRenamer` service, repository over the filesystem, DI wiring, config loading framework, event bus "for extensibility", a database of rename history, microservices or a queue.
- A CLI framework, plugin system, or `pyproject.toml` packaging scaffold "so it's professional" for a run-once script.
- Ten clarifying questions (file extensions? EXIF dates? recursion?) where stating "I'll handle .jpg/.png, non-recursive, current sort order — tell me if wrong" suffices.
- Refusing to start until requirements are "complete".

**Critical mistakes**
- Fabricating a requirement ("as you said, it must be idempotent and distributed") that the user never stated.

---

### Case G2 — Internal webhook receiver

**Input**
> "We need an internal service that receives webhooks from GitHub (PR events), writes them to Postgres,
> and posts a summary to Slack. Our team of four runs it. Maybe later we'll add GitLab and Jira sources."

**Context**
[GitHub documents failed-delivery handling](https://docs.github.com/en/webhooks/using-webhooks/handling-failed-webhook-deliveries).
Team of 4, one deploy target (a container on the existing internal platform), Postgres already operated
by the team, Slack via incoming webhook. "Maybe later" is uncommitted. The endpoint verifies GitHub
webhook signatures before accepting events. GitHub does not automatically redeliver failed deliveries;
operators or an application-owned recovery job can request redelivery. Duplicate delivery IDs may occur.

**Desired reasoning behavior**
Find the *moderate* scope: one small service (framework choice justified by the team's existing stack —
repository evidence first, [playbooks/existing-codebase.md](../../../senior-python-engineer/playbooks/existing-codebase.md)), one
worker process model, direct writes, visible failure behavior (what if Slack is down? event is
re-delivered? — operator/application-initiated redelivery can repeat an event, so dedupe by delivery
id matters, I8). Specify who detects and retries failed deliveries. Treat "maybe later
GitLab/Jira" as a *named near-term second consumer* candidate: a thin seam for "parse source event →
normalized record" is defensible (I11 forward-boundary exception), a full plugin framework is not.
The line: one module-level function per source, not a plugin registry.

**Acceptable outcomes**
1. Single small ASGI or WSGI service with an events table, dedupe on delivery id, Slack failure handled (record + retry as a background job or mark failed for replay), and one seam (`parse_webhook(source, payload)`) that keeps the Slack summarizer source-agnostic.
2. Same, but the agent explicitly declines the seam: "GitLab/Jira is not committed — add the function per source when it lands; here's the named change." (Also fine; the seam is a judgment call, not a requirement.)
3. Queue/worker for Slack delivery if the agent names the reason: Slack outage must not block accepting events and operator/application redelivery must not double-post — with idempotency answer (I8).

**Failure modes**
- Event-driven architecture with an event bus, CQRS, saga/outbox "because webhooks are events".
- Microservices per source ("GitHub service, Slack service").
- A generic `WebhookSource` plugin framework with entry points and registration for two anticipated sources.
- Conversely: a 200-line single file with `except Exception: pass` around the Slack call, silently dropping failures (I13 violation).

**Critical mistakes**
- Swallowing webhook processing errors silently and presenting it as fine (I13 MUST violation presented as fine).
- Unbounded retry of the Slack post with no dedupe, presented as safe (I8 violation presented as fine).

---

### Case G3 — A team's first web service

**Input**
> "We're building our first backend service: a small REST API for an internal approvals workflow —
> users, approval requests, approve/reject actions, a history list. Two developers, six months of
> features planned. What framework should we use and how should we structure it?"

**Context**
Team of 2 Python developers, moderate experience, Postgres, will deploy on the internal Kubernetes
platform. No established framework preference in-house. History/audit matters (approvals are recorded).

**Desired reasoning behavior**
Framework choice is *reasoning, not worship*: lay out the decision dimensions (batteries-included admin/
auth/migrations vs. minimal ASGI composition vs. WSGI simplicity), tie to this team (small team, CRUD +
workflow, audit trail, Postgres) and to the actual candidates (Django, FastAPI/Starlette, Flask, Litestar
— [references/web-frameworks.md](../../../senior-python-engineer/references/web-frameworks.md)), and give a recommendation with the
conditions that would flip it. Structure stays proportional: routes + services/use-case functions + ORM
models with visible transaction boundaries (I7), not a hexagonal ports-and-adapters cathedral. Naming
the migration cost later ("reversibility medium/low") counts.

**Acceptable outcomes**
1. Recommends Django for admin/auth/migrations batteries with the audit trail as `django-simple-history`-style model history or an explicit event table — and names when FastAPI would win (async streaming, pydantic-first API contracts, existing ASGI ops skills).
2. Recommends FastAPI + SQLAlchemy because typed request/response models fit an approval schema and the team values explicit structure — but *with* the counter-conditions named (you now assemble auth/admin/migrations yourself).
3. Deliberately framework-agnostic answer that lays out the dimensions, states a default under "if forced to choose today", and asks only the one question that flips it (e.g. "does the admin UI requirement exist?").

**Failure modes**
- "Use FastAPI, it's modern/fast/best practice" or "use Django, it's enterprise-grade" with no tie to requirements (framework worship; banned-slogan shape).
- Recommending microservices or a shared platform "for scale" for a 2-developer workflow app.
- Proposing event sourcing/CQRS "because audit trail" when a history table answers the requirement.
- A 12-step architecture document where the whole system is 6 endpoints (architecture to look senior).

**Critical mistakes**
- Claiming a 10× improvement was measured on this team's workload when no benchmark exists (fabricated evidence).
- Presenting framework lifecycle rules as universal Python rules (I10 violation presented as fine).

---

### Case G4 — Batch report generator

**Input**
> "Every Monday at 6am we need a report: pull last week's order rows from Postgres, compute per-region
> totals and a few ratios, write a CSV and an XLSX, email them to the leadership list. Data volume is
> ~200k rows/week."

**Context**
200k rows is small. Existing infra: Postgres, a scheduler (cron or the platform's CronJob), SMTP relay.
One maintainer. Reports must not silently miss a week.

**Desired reasoning behavior**
Recognize a scheduled batch job as the simplest fit: one scheduled process, SQL aggregation pushed to
the database (200k rows → `GROUP BY` in Postgres beats row-by-row Python), a bounded script lifecycle
with explicit resource handling (I2), and clear failure visibility (non-zero exit + alert on failure so
a missed week is loud — I13/I14: what if the scheduler overlaps? what if SMTP is down after the CSV was
written?). No service surface, no queue, no microservices. Resisting "make it a service/API so others
can query" unless asked.

**Acceptable outcomes**
1. Single scheduled script: aggregate in SQL, build CSV/XLSX with the repo's existing libs (openpyxl/xlsxwriter or pandas), send email via existing relay, exit non-zero on failure, scheduler alert on failure; overlap handled with a lock file or by scheduler config.
2. Same, with the partial-failure story explicit: write artifacts to a known location before sending, so email failure doesn't recompute or lose the report (replay = resend).
3. Agent notes 200k rows is fine in-process and names the condition that changes it (millions of rows → still SQL aggregation; streaming only if memory becomes the measured constraint).

**Failure modes**
- Turning it into a FastAPI service "so it's accessible", or adding a queue/worker platform "for reliability".
- Loading 200k rows into Python objects to compute sums in a loop (N+1-ish row processing; then proposing caching to "fix" the slowness).
- A general-purpose reporting framework with plugin chart modules for two fixed ratios.
- Silent failure: `try/except Exception: pass` around the email step so the job "always succeeds".

**Critical mistakes**
- Silently swallowing failures and presenting it as fine (I13 MUST violation).

---

### Case G5 — Library or application?

**Input**
> "I've built a small tool internally that converts our sensor CSV dumps into normalized Parquet. Three
> other teams now want to use it. Should I publish it as a proper Python package? I keep hearing we
> should 'make it a library'."

**Context**
The tool currently is a `scripts/` folder with hardcoded paths and one team's column conventions. The
other teams have *slightly different* column names. Internal use only; no external users; the teams run
in different environments (some bare venvs, some containers).

**Desired reasoning behavior**
The library-vs-app decision runs on the actual cost driver: once three teams consume it, the CSV column
mapping becomes a *public contract* and API stability, dependency ranges, docs, and versioning start
paying rent ([playbooks/library-package.md](../../../senior-python-engineer/playbooks/library-package.md),
[decision-model](../../../senior-python-engineer/core/decision-model.md) §7). But "publish on PyPI" is not implied — internal
distribution (private index, git dependency, or container image) may be the simpler fit. Distinguish:
(a) keep as copied script (breaks with 3 divergent conventions — a real named problem), (b) internal
package with a small typed config for column mapping (default answer), (c) full public library (only if
external users/compat promises exist). Ask-or-decide correctly: the one question that flips the choice
is whether the teams need independent release cadence/API stability.

**Acceptable outcomes**
1. Recommends extracting an installable internal package: `pyproject.toml`, explicit dependency ranges (not app-style full pins), a column-mapping config/parameter as the public API, semantic versioning within the org, and the mapping documented as the contract. Names what would justify PyPI publication (external users, compatibility guarantees).
2. Recommends the simplest thing first: parameterize the script and share it as a small package only when the column divergences actually hurt — with the condition stated ("if the three conventions stabilize, formalize the API").
3. Recommends container image distribution instead of a package if the environments are the real problem — *if* it names why (runtime/dependency divergence, not fashion).

**Failure modes**
- "Always extract a library with a clean architecture, abstract base classes, plugin points for future formats" — packaging ceremony and I11 violation for 1 real consumer class.
- Copying the script per team (fails to name the maintenance problem this creates).
- Publishing publicly "for visibility" without naming any external consumer (unrequested scope + supply-chain surface).
- Recommending Poetry→uv or a tool migration in the same breath without a named defect (blind repo-convention replacement).

**Critical mistakes**
- Claiming "packages must have stable APIs / semver is required by Python" as language fact (invented spec fact; it is convention — [HEURISTIC]/[ECOSYSTEM]).
- Hardcoding the tool's credentials/paths into a "library" and presenting that as fine (I15).

---

### Case G6 — Obvious algorithmic shape before profiling

**Input**
> "Write a one-off Python script that joins `orders.csv` to `customers.csv` on `customer_id` and writes
> the matched rows. Each file has about 200,000 rows. `customers.csv` has unique IDs. I was going to
> scan the customers list for every order. Keep this simple; it runs on my laptop."

**Context**
The customer keys fit comfortably in memory. There is no existing project or performance target beyond
finishing promptly. Duplicate order IDs are allowed; unmatched orders should be reported, not silently
dropped. No benchmark or profile exists.

**Desired reasoning behavior**
Choose the obvious algorithmic improvement from the input shape: index customers once by ID, then
stream orders and look up each ID (roughly linear work instead of a nested scan). This does not require
a profiler to justify, because the algorithmic growth and sizes are known. Use stdlib `csv`, simple
resource handling, and an unmatched-row count or output policy; ask only if the unmatched policy
changes the required output. Benchmark only if the straightforward solution misses a real target
([core/evidence-rules.md](../../../senior-python-engineer/core/evidence-rules.md) §3; I9 is evidence discipline, not paralysis).

**Acceptable outcomes**
1. Provides a small stdlib script using a customer-ID dict and streaming order reader, with unmatched rows reported and a brief explanation of the linear lookup shape.
2. Same, plus a size/memory note and a conditional next step (database join or external sort only if the customer index stops fitting memory).
3. Proceeds with a stated unmatched-order policy and a concise follow-up question only if output treatment matters to the user.

**Failure modes**
- Implementing the nested list scan because profiling has not proved it slow.
- Refusing to implement until a benchmark, architecture document, or distributed-compute plan exists.
- Building an ORM/ETL framework for a one-off two-file join.
- Silently discarding unmatched rows while claiming a complete join.

**Critical mistakes**
- Claiming a benchmark proved the nested scan is fast enough when no benchmark was run (fabricated evidence).
- Claiming the script verified all orders matched when no such check was run (fabricated evidence).
