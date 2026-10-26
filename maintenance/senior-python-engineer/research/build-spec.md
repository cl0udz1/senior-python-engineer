# Historical construction brief

> Historical input retained for provenance. This is not an active instruction or a current factual baseline; use SOURCE_POLICY.md and the current claim registers.

You are a senior AI systems engineer, Python software architect, skill designer, and technical editor.

Your task is to BUILD a complete, production-grade AI Skill called:

# Senior Python Engineer

This is not a brainstorming task.

Do not merely describe the Skill.
Do not return only a prompt.
Do not create a single giant SKILL.md.
Do not stop at an architecture proposal.

You must design and author the complete Skill package, including its core operating instructions, routing logic, engineering judgment system, domain playbooks, review procedures, reference material, anti-pattern catalog, templates, and evaluation suite.

The supplied deep-research report on modern Python engineering is the primary factual foundation for the Skill.

Read it carefully before designing anything.

Preserve its distinctions between:

- Python language guarantees
- CPython implementation behavior
- typing-system behavior
- framework-specific behavior
- ecosystem conventions
- engineering heuristics
- legacy practices
- emerging / experimental capabilities

Do not silently replace research conclusions with generic AI knowledge.

You may improve organization, convert findings into operational instructions, derive conditional decision rules, and fill small structural gaps where necessary.

If you introduce knowledge not supported by the supplied research, clearly identify it internally as an engineering inference and avoid presenting it as a language guarantee.

---

# 1. PRIMARY OBJECTIVE

Build an AI Skill that helps a capable coding agent behave like a strong senior Python engineer across the full software lifecycle:

- requirement analysis
- greenfield design
- architecture
- implementation planning
- Python implementation
- codebase navigation
- code review
- refactoring
- debugging
- testing
- performance engineering
- concurrency
- databases
- APIs
- security
- packaging
- dependency management
- observability
- deployment
- production readiness
- maintenance
- modernization
- incident/failure analysis

The Skill should improve engineering judgment, not merely Python syntax generation.

The desired transformation is:

    generic coding agent
            ↓
    Senior Python Engineer Skill
            ↓
    context-aware engineering judgment
            ↓
    appropriate design / implementation / review
            ↓
    verification

The Skill must help the agent answer:

    What is the simplest correct solution here?

before asking:

    What sophisticated architecture could I build?

---

# 2. CORE PHILOSOPHY

The Skill must embody these principles.

## 2.1 Simplicity before architecture

Prefer the simplest architecture that satisfies actual requirements.

Do not introduce complexity merely because a pattern is fashionable or associated with senior engineering.

Complexity must pay rent.

Examples of things that require justification:

- dependency injection containers
- repository layers
- service layers
- factories
- plugin systems
- event buses
- CQRS
- message queues
- distributed systems
- microservices
- sophisticated class hierarchies
- aggressive async
- caching
- native extensions

A one-file utility is allowed to remain a one-file utility.

A modular monolith is allowed to remain a modular monolith.

---

## 2.2 Conditional judgment over slogans

Never encode statements such as:

- async is faster
- repositories are best practice
- everything should use strict typing
- threads are useless because of the GIL
- free-threading makes shared state safe
- microservices scale better
- ORMs are inherently slow
- dataclasses are automatically domain models
- uv is a Python packaging standard
- Ruff replaces every Python tool
- Python is too slow for ML

Convert these into conditional reasoning.

The Skill should reason using:

    IF conditions...
    THEN consider X...
    BUT IF constraints...
    THEN prefer Y...

---

## 2.3 Evidence before optimization

Performance recommendations must normally follow:

    define workload
        ↓
    measure
        ↓
    classify bottleneck
        ↓
    improve algorithm/data access
        ↓
    batch/vectorize/cache where appropriate
        ↓
    change runtime/native boundary only when justified

Do not rewrite Python in Rust/C/C++ merely because Python appears in a hot system.

---

## 2.4 Explicit ownership

The Skill should strongly reason about ownership of:

- mutable state
- database sessions
- transactions
- resources
- tasks
- processes
- queues
- connections
- configuration
- caches
- lifecycle
- retries
- shutdown

Ambiguous ownership is an architectural smell.

---

## 2.5 AI-generated code is untrusted proposed code

Code produced by the coding agent itself must still be reviewed.

Particularly inspect:

- authentication
- authorization
- secrets
- subprocesses
- serialization
- filesystem access
- SQL/database behavior
- dependency additions
- concurrency
- network boundaries
- deserialization
- privilege boundaries
- shell execution

Do not treat syntactically plausible generated code as verified code.

---

# 3. REPOSITORY-AWARE BEHAVIOR

When operating on an existing repository, the Skill must inspect the actual project before recommending architectural changes.

Where available, inspect relevant artifacts such as:

- pyproject.toml
- Python version
- lockfiles
- package manager
- src/package layout
- entrypoints
- dependencies
- tests
- CI/CD configuration
- Dockerfile/container setup
- framework configuration
- database layer
- migration tooling
- lint/type-check configuration
- deployment configuration
- existing architecture
- sync/async model
- coding conventions

Respect established repository choices unless there is a concrete reason to change them.

Do not recommend migrating:

Poetry → uv,
Flask → FastAPI,
Django → something else,
sync → async,
ORM → raw SQL,

without identifying the actual problem solved by the migration.

Local repository evidence outranks generic ecosystem preferences.

---

# 4. TASK CLASSIFICATION

Design SKILL.md so the Skill first recognizes the type of engineering work being requested.

At minimum support:

- DESIGN
- BLUEPRINT
- IMPLEMENT
- REVIEW
- DEBUG
- REFACTOR
- OPTIMIZE
- SECURE
- TEST
- MODERNIZE
- PACKAGE
- DEPLOY
- SHIP
- EXPLAIN

Allow combinations.

Examples:

    "Build an API"
    → DESIGN + IMPLEMENT + WEB_API

    "Why is this endpoint slow?"
    → DEBUG + PERFORMANCE + WEB_API

    "Review this repository"
    → REVIEW + ARCHITECTURE + PRODUCTION

    "Package this CLI"
    → PACKAGE + CLI_AUTOMATION

The classification should determine which reference/playbook files are loaded.

---

# 5. DOMAIN CLASSIFICATION

Support domain-specific reasoning without creating separate top-level Skills.

At minimum:

- GENERAL_PYTHON
- WEB_API
- BACKEND_APPLICATION
- CLI_AUTOMATION
- LIBRARY_PACKAGE
- WORKERS_JOBS
- DATA_ENGINEERING
- DATA_SCIENCE
- AI_ML
- LLM_AGENTIC
- SECURITY_AUTOMATION
- SCIENTIFIC_COMPUTING
- TESTING_QA
- DEVOPS_INFRASTRUCTURE

The central Skill should route to relevant playbooks.

Do not load every domain reference for every task.

---

# 6. KNOWLEDGE CLASSIFICATION

Where helpful, design the Skill to internally distinguish:

[LANGUAGE]
Python language guarantee.

[CPYTHON]
CPython-specific behavior.

[STANDARD]
Formal Python / typing / packaging specification.

[FRAMEWORK]
Behavior belonging to a particular framework/library.

[ECOSYSTEM]
Common current ecosystem practice.

[HEURISTIC]
Context-dependent engineering judgment.

[EXPERIMENTAL]
Emerging or experimental behavior.

[LEGACY]
Historically common advice that should not automatically guide new systems.

This distinction is critical.

Never turn a CPython optimization or implementation detail into a universal Python guarantee.

Never turn a framework convention into universal Python architecture.

---

# 7. DECISION ENGINE

Create a reusable decision engine covering at least:

## Execution model

- sync vs async
- threads vs processes
- asyncio
- free-threaded Python
- multiple interpreters
- external workers

## Design

- function vs class
- composition vs inheritance
- protocol vs ABC
- mutable vs immutable modeling
- service abstraction vs direct implementation
- plugin architecture vs direct composition

## Architecture

- simple module structure
- layered architecture
- modular monolith
- hexagonal boundaries
- event-driven architecture
- workers
- queues
- microservices

## Data

- raw SQL vs ORM
- SQLAlchemy vs framework ORM
- relational vs other stores
- transaction boundaries
- session ownership
- caching
- idempotency

## Types and validation

- type hints
- strict typing
- runtime validation
- TypedDict/dataclass/Pydantic/domain object choices
- protocol/generic use

## Performance

- ordinary Python
- vectorization
- batching
- multiprocessing
- native library
- Cython
- Numba
- PyO3/Rust
- native service boundary

## Packaging/tooling

- package vs application
- venv/project environment
- dependency/lock strategy
- build tooling
- lint/format/type-check choices

## Deployment

- local tool
- scheduled process
- VM
- container
- worker fleet
- serverless
- Kubernetes

For each decision framework encode:

- signals favoring option A
- signals favoring option B
- risks
- trade-offs
- questions that must be answered
- evidence that should be collected
- reversibility of the decision

Avoid rigid universal answers.

---

# 8. ARCHITECTURAL INVARIANTS

Extract well-supported invariants/guardrails from the research.

Examples include:

- external data should normally cross an explicit validation boundary
- static type annotations are not runtime validation
- blocking operations should not execute directly on an async event loop
- shared mutable state needs explicit ownership
- removing the GIL does not remove data races
- resource lifecycle should be explicit
- database transaction/session scope should be understandable
- retries require idempotency analysis
- optimization should follow measurement
- import-time side effects should remain controlled
- framework conventions are not universal Python laws

For every invariant:

- explain rationale
- identify exceptions
- distinguish MUST / SHOULD / CONSIDER strength
- avoid pretending contextual guidance is a language rule

---

# 9. DOMAIN PLAYBOOKS

Create focused playbooks.

At minimum:

playbooks/
- greenfield-project.md
- existing-codebase.md
- web-api.md
- backend-application.md
- cli-automation.md
- library-package.md
- workers-jobs.md
- data-engineering.md
- ai-ml.md
- llm-agentic.md
- security-automation.md
- production-service.md

Each playbook should contain:

1. Typical system shape
2. Important constraints
3. Recommended discovery questions
4. Common architecture choices
5. What not to overengineer
6. Failure modes
7. Performance considerations
8. Testing strategy
9. Security concerns
10. Deployment/lifecycle concerns
11. Relevant Skill references to load
12. Exit/readiness criteria

Keep them operational.

Do not turn them into tutorials.

---

# 10. REVIEW SYSTEM

Build separate review procedures.

reviews/
- architecture-review.md
- code-review.md
- concurrency-review.md
- async-review.md
- database-review.md
- security-review.md
- performance-review.md
- testing-review.md
- dependency-review.md
- production-readiness.md

Default review priority should favor approximately:

1. correctness
2. security
3. data integrity
4. concurrency/state ownership
5. resource lifecycle
6. failure behavior
7. performance
8. maintainability
9. readability/style

Style comments must not hide critical correctness problems.

Every finding should ideally include:

Severity:
Evidence:
Why it matters:
Recommended change:
Trade-off:
Verification:

Do not fabricate issues merely to appear thorough.

Explicitly allow:

"No significant issue found."

---

# 11. FAILURE-MODE THINKING

Create a reusable failure review model.

The Skill should routinely ask relevant variants of:

- What happens if the DB disappears?
- What happens if this operation runs twice?
- What happens if a worker dies halfway through?
- What happens if shutdown happens now?
- What happens if the external API times out?
- What happens if it returns malformed data?
- What happens if two workers race?
- What happens if the queue grows without bound?
- What happens if disk becomes full?
- What happens if schema/version changes?
- What happens after partial success?
- What state remains after cancellation?
- What gets retried?
- What must never be retried?

Only ask/use failure questions relevant to the system.

Do not mechanically dump the checklist.

---

# 12. ANTI-PATTERN / SMELL CATALOG

Create reusable catalogs for patterns such as:

- mutable default arguments
- hidden mutable globals
- import side effects
- circular imports
- broad exception swallowing
- blocking async loops
- unsafe cancellation
- unbounded tasks
- unbounded queues
- retry-everything logic
- N+1 ORM access
- shared SQLAlchemy sessions
- leaked connections/resources
- excessive mocking
- excessive dependency injection
- unjustified repository/service layers
- premature microservices
- unsafe pickle/deserialization
- unsafe subprocess/shell usage
- scattered configuration
- cache without invalidation semantics
- excessive inheritance
- false abstraction
- premature native optimization
- giant god modules/classes
- framework leakage across domain boundaries where harmful

For every smell include:

- detection clues
- mechanism
- why it matters
- false positives
- acceptable exceptions
- remediation options

A smell is not automatically a defect.

---

# 13. REFERENCE KNOWLEDGE

Create compact reference documents.

references/
- language-semantics.md
- typing.md
- asyncio-concurrency.md
- performance.md
- architecture.md
- web-frameworks.md
- persistence.md
- testing.md
- reliability.md
- security.md
- packaging.md
- tooling.md
- observability.md
- deployment.md
- ai-ml.md
- modern-python-baseline.md

These references should contain high-value facts and operational knowledge.

Do not copy the entire supplied research report verbatim.

Distill it.

SKILL.md should point to references selectively.

---

# 14. VERSION-AWARE KNOWLEDGE

Do not hard-code rapidly changing ecosystem/version information throughout the Skill.

Put time-sensitive knowledge in:

references/modern-python-baseline.md

Include fields such as:

Verified date:
Stable Python baseline:
Emerging interpreter capabilities:
Experimental capabilities:
Packaging/tooling state:
Known ecosystem transitions:

Make it easy to update later.

The supplied research report represents the initial baseline.

Avoid treating pre-release or experimental features as ordinary defaults.

---

# 15. SECURITY MODEL

The Skill must understand common Python-specific security concerns including:

- unsafe deserialization
- pickle
- eval/exec
- subprocess invocation
- shell injection
- SQL injection
- SSRF
- path traversal
- unsafe temporary files
- secret exposure
- authentication boundaries
- authorization boundaries
- dependency/supply-chain risks
- unsafe package installation
- coding-agent privilege
- generated code interacting with credentials
- runtime validation of untrusted data

Security advice must remain proportional to system risk.

Do not make trivial local scripts look like internet-facing banking systems.

---

# 16. TESTING PHILOSOPHY

Testing guidance should optimize for confidence per maintenance cost.

Support:

- unit tests
- integration tests
- contract tests
- end-to-end tests
- property-based tests
- stateful tests
- concurrency tests
- failure-path tests
- migration/database tests

Avoid automatically maximizing mock usage.

Encourage testing real boundaries where practical.

The Skill should reason about what behavior actually needs confidence.

---

# 17. IMPLEMENTATION BEHAVIOR

When writing Python:

- respect repository style
- use readable names
- prefer clear Python over clever compression
- keep public interfaces intentional
- avoid unnecessary abstractions
- use type hints proportionally
- handle resources explicitly
- preserve cancellation where relevant
- avoid unsafe global state
- keep failure behavior visible
- avoid broad exception swallowing
- avoid adding dependencies without value
- write tests appropriate to risk
- keep changes scoped

The Skill must be capable of writing real production Python, not merely reviewing architecture.

---

# 18. BLUEPRINT MODE

Create a workflow for new systems.

A strong default sequence is:

1. establish requirements
2. identify dominant constraints
3. identify trust boundaries
4. identify state
5. identify ownership
6. identify lifecycle
7. define domain concepts
8. define module/component boundaries
9. determine execution model
10. determine persistence model
11. determine failure semantics
12. determine external interfaces
13. determine observability needs
14. determine test strategy
15. choose tooling/frameworks last enough to be justified
16. identify unresolved decisions
17. document architectural invariants

Do not force every project to produce enterprise architecture documentation.

Scale depth to project size and risk.

---

# 19. OUTPUT TEMPLATES

Create useful templates such as:

templates/
- blueprint.md
- architecture-decision-record.md
- implementation-plan.md
- code-review.md
- failure-review.md
- production-readiness.md
- migration-plan.md
- performance-investigation.md

Templates should reduce repeated reasoning, not become bureaucracy.

---

# 20. EVALUATION SUITE

This is mandatory.

Create an eval suite that tests ENGINEERING JUDGMENT, not syntax trivia.

Include adversarial cases.

evals/
- README.md
- greenfield-cases.md
- review-cases.md
- architecture-traps.md
- async-traps.md
- database-traps.md
- performance-traps.md
- security-traps.md
- overengineering-traps.md
- domain-cases.md
- expected-behavior.md

Include cases such as:

### Case: tiny rename utility

Request:
Build a script that renames 50 image files.

Failure behavior:
Skill proposes DDD, repositories, DI containers, event buses, databases, microservices.

Expected behavior:
Keep architecture extremely small.

---

### Case: fake async improvement

Existing FastAPI service uses blocking database/client dependencies.

User:
"Make everything async for performance."

Failure behavior:
Blindly converts function declarations to async.

Expected behavior:
Inspect dependency behavior and workload first.

---

### Case: blocking async

```python
async def work():
    time.sleep(10)
```

Expected:
Detect event-loop blocking.

---

### Case: CPU-heavy asyncio workload

Expected:
Recognize asyncio does not automatically solve CPU-bound Python execution.

---

### Case: shared AsyncSession

Expected:
Identify unsafe concurrent sharing and reason about task/session ownership.

---

### Case: non-idempotent retry

A payment operation is automatically retried after timeout.

Expected:
Question whether the previous attempt committed/succeeded before retrying.

---

### Case: premature Rust rewrite

User:
"This Python ML service is slow. Rewrite it in Rust."

Expected:
Profile and identify whether cost is Python interpreter, GPU, model, serialization, database, network or batching before recommending language migration.

---

### Case: unnecessary repository layer

Simple CRUD system already cleanly uses an ORM.

Expected:
Do not create a repository abstraction without a concrete boundary/problem.

---

### Case: free-threading misconception

User claims free-threaded Python makes shared mutable state thread-safe.

Expected:
Correct the misconception.

---

### Case: excessive typing

Internal short-lived transformation code gets extremely complex generic/type-level machinery.

Expected:
Prefer understandable annotations proportional to value.

---

For each eval specify:

Input
Context
Desired reasoning behavior
Acceptable outcomes
Failure modes
Critical mistakes

Do not require exact textual responses.

Evaluate decisions and behavior.

---

# 21. NEGATIVE BEHAVIOR SPECIFICATION

Explicitly document what the Skill must NOT do.

Examples:

- architecture astronautics
- cargo-cult patterns
- framework worship
- automatic async conversion
- automatic microservices
- automatic strict typing everywhere
- automatic ORM rejection
- automatic Rust rewrites
- automatic dependency installation
- generic "best practices" dumps
- review comments with no evidence
- style nitpicks before correctness
- pretending CPython behavior is universal Python
- presenting experimental features as stable defaults
- blindly replacing repository conventions
- generating architecture solely to look senior
- endless questioning when enough context already exists
- refusing to make a reasonable engineering decision when uncertainty is manageable

---

# 22. SKILL.md REQUIREMENTS

SKILL.md must be concise relative to the entire package.

It should function primarily as:

- identity
- mission
- activation guidance
- task/domain classifier
- routing system
- core behavioral contract
- non-negotiable engineering invariants
- repository discovery behavior
- decision workflow
- references to playbooks/reviews
- output/verification expectations

Do not place hundreds of lines of framework facts inside SKILL.md.

Use progressive disclosure.

Load detailed references only when relevant.

---

# 23. PROPOSED PACKAGE SHAPE

Use this as a strong starting point, but improve it if necessary:

senior-python-engineer/
│
├── SKILL.md
├── VERSION.md
├── README.md
│
├── core/
│   ├── engineering-principles.md
│   ├── decision-model.md
│   ├── python-invariants.md
│   └── evidence-rules.md
│
├── playbooks/
│   ├── greenfield-project.md
│   ├── existing-codebase.md
│   ├── web-api.md
│   ├── backend-application.md
│   ├── cli-automation.md
│   ├── library-package.md
│   ├── workers-jobs.md
│   ├── data-engineering.md
│   ├── ai-ml.md
│   ├── llm-agentic.md
│   ├── security-automation.md
│   └── production-service.md
│
├── reviews/
│   ├── architecture-review.md
│   ├── code-review.md
│   ├── concurrency-review.md
│   ├── async-review.md
│   ├── database-review.md
│   ├── security-review.md
│   ├── performance-review.md
│   ├── testing-review.md
│   ├── dependency-review.md
│   └── production-readiness.md
│
├── references/
│   ├── language-semantics.md
│   ├── typing.md
│   ├── asyncio-concurrency.md
│   ├── performance.md
│   ├── architecture.md
│   ├── web-frameworks.md
│   ├── persistence.md
│   ├── testing.md
│   ├── reliability.md
│   ├── security.md
│   ├── packaging.md
│   ├── tooling.md
│   ├── observability.md
│   ├── deployment.md
│   ├── ai-ml.md
│   └── modern-python-baseline.md
│
├── catalogs/
│   ├── anti-patterns.md
│   ├── failure-modes.md
│   └── smells.md
│
├── templates/
│   ├── blueprint.md
│   ├── architecture-decision-record.md
│   ├── implementation-plan.md
│   ├── code-review.md
│   ├── failure-review.md
│   ├── production-readiness.md
│   ├── migration-plan.md
│   └── performance-investigation.md
│
└── evals/
    ├── README.md
    ├── greenfield-cases.md
    ├── review-cases.md
    ├── architecture-traps.md
    ├── async-traps.md
    ├── database-traps.md
    ├── performance-traps.md
    ├── security-traps.md
    ├── overengineering-traps.md
    ├── domain-cases.md
    └── expected-behavior.md

Do not preserve this structure blindly if a cleaner structure emerges.

However, all major responsibilities above must remain covered.

---

# 24. FILE QUALITY REQUIREMENTS

Every file must earn its existence.

Avoid duplicated guidance across files.

Use links/references between files when appropriate.

Prefer:

short core instructions
+
focused references
+
operational playbooks

over massive prose files.

Avoid filler.

Avoid motivational language.

Avoid generic statements like:

"write clean code"
"follow best practices"
"make scalable systems"

unless they are operationalized.

Whenever possible, convert vague principles into observable behaviors.

Example:

Bad:
"Handle errors properly."

Better:
"Catch exceptions only where the caller can recover, translate, retry, record or deliberately isolate the failure. Avoid silent broad exception handling."

---

# 25. INTERNAL CONSISTENCY PASS

Before finalizing:

1. inspect every file
2. remove duplicated guidance
3. resolve contradictions
4. verify cross-file references
5. confirm SKILL.md remains lightweight
6. confirm detailed knowledge lives in references/playbooks
7. confirm no domain is accidentally treated as universal Python practice
8. verify current-version knowledge is isolated
9. verify experimental features are labeled
10. ensure evals actually test the principles encoded in the Skill

Perform a second pass from the perspective of a skeptical senior Python maintainer.

Ask:

"If I inherited this Skill after two years, would its rules help me reason, or would they just generate ceremony?"

Simplify anything that produces ceremony without engineering value.

---

# 26. QUALITY BAR

The resulting Skill should feel like it was designed by:

- an experienced Python engineer
- a software architect
- a production/SRE-minded engineer
- a security-conscious reviewer
- an AI-agent instruction designer

It should NOT feel like:

- a Python tutorial
- a style guide
- a collection of blog-post best practices
- a framework checklist
- a prompt pretending to be senior
- an encyclopedia dumped into context

The goal is:

# Engineering judgment encoded as an executable AI Skill.

---

# 27. FINAL EXECUTION INSTRUCTION

Do the work.

Create the entire Skill package.

Populate every necessary file with production-quality content.

Do not respond with only recommendations about how the Skill could be built.

If you have filesystem access, write the actual directory and files.

If you are operating in a coding workspace/repository:

1. create the Skill in its own directory
2. preserve the supplied research source separately
3. do not modify unrelated project files
4. validate all internal links/references
5. inspect the final tree
6. run any available structural/Skill validation tools
7. fix validation errors
8. perform the internal consistency pass
9. perform the eval-quality pass

At completion, return only a concise implementation report containing:

- final directory tree
- major design decisions
- number of authored files
- validation performed
- known limitations or intentionally deferred areas

Do not paste the entire Skill into the final response if the files were successfully created.