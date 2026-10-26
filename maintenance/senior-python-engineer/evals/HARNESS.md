# Runnable development evaluation

## Scope and evidence

The harness uses Python 3.11+ and the standard library. It does not call a model, install dependencies,
create an operating-system sandbox, supply credentials, or perform an actual-host activation test.
All bundled tasks, grader code, and reference solutions are public development assets. Passing the
reference solutions checks the fixture machinery; it is not a result for the skill or a coding agent.

There are 12 tasks across eight families:

| Tasks | Family | Observable checks |
|---|---|---|
| FX01–FX02 | Async lifetimes | Concurrent progress, billing fallback, ordinary errors, timeout/cancellation, awaited cleanup |
| FX03 | Transaction retry | Real SQLite writes/rollback, fresh connection per whole-unit retry, bounds, nonretryable errors, close |
| FX04 | Remote uncertain outcome | Intent before call, timeout after provider acceptance, crash before local acknowledgement, stable identity, changed amount |
| FX05 | Subtype contract | Accepted keys, missing-key/default identity, present None, behavior against the base contract |
| FX06 | Rolling migration | Old write after backfill, mixed-version authority, compatible dual write, retirement gate, final reconciliation |
| FX07–FX08 | Subprocess boundary | Actual native argv round trip on the host, Windows path policy and batch rejection |
| FX09–FX11 | Scope and review | Protected file snapshots; human judgment of design, clean review and matched bug review |
| FX12 | Narrow legacy fix | Return contract and preservation of an unrelated helper |

FX03's RetryableConflict is a deliberately simulated retry signal. It does not test PostgreSQL
SQLSTATEs, transaction abort states, isolation behavior or a live database server. FX04 is a fake
provider with an explicitly visible retention/idempotency contract; it does not prove exactly-once
external delivery or multiworker safety. FX06 models sequential state transitions, not a fleet or
concurrent migration. FX07/FX08 do not demonstrate Windows shell behavior on a Linux host.

## File separation and execution safety

Keep `evals/graders`, `evals/reference`, evaluator records, prior outputs, and judgment keys outside the
agent's **readable and writable mounts**. `prepare` copies only TASK.md and starter files to a fresh
workspace. A separate path or a directory called hidden is not access control. Enforce isolation in
the actual agent host/container, verify the mount configuration, and capture reads/tool calls. The
agent may see the assigned skill's runtime resources; it must not see the maintainer tree. Original
condition B deliberately includes its old public evaluation files because it is the as-distributed
baseline; the new comparison task's graders and answers remain excluded in every condition.

`grade` executes candidate Python. Run it only inside a suitable disposable executor with bounded
CPU, memory, disk, processes and network, no private credentials, and no access to production data.
A successful process exit alone is insufficient: the runner must finish a nonempty test suite and
write a completion record with counts. Missing completion, zero tests, all-skipped tests, and timeout
are grading errors requiring triage/regrading, not automatic passes. This record is an accidental-
bypass check, not protection against candidate introspection or tampering.

The subprocess timeout terminates its process group on POSIX; Windows uses process termination and
needs host-level child-process containment. File-backed logs cap the result excerpt but not disk use.
The harness is not a hostile-code security sandbox. Candidate code shares an interpreter with the
Python grader and can introspect it; audit suspected grader tampering and use stronger isolation for
adversarial benchmarks. Never claim hidden tests are cryptographically protected by this layout.

Final file snapshots detect persisted edits, additions and deletions outside allowed paths (except
incidental `__pycache__` and `.pytest_cache` directories, which are ignored). They do
not detect temporary changes that were reverted, network calls, installations, or reads of secrets.
Use a trusted host trace for those checks. The standard library tests judge outcomes, not keyword
inclusion or a required implementation primitive.

## Commands

Run these from `maintenance/senior-python-engineer` in the source project. Paths are examples; use
fresh directories and unique output names. Nothing silently overwrites a prior run.

```bash
python3 tools/evaluate.py list
python3 tools/evaluate.py public-list
python3 tools/evaluate.py export-case --case AS8 --out /tmp/as8-visible.json
python3 tools/evaluate.py selftest --out /tmp/fixture-selftest.json
python3 -m unittest discover -s tools -p 'test_evaluate.py' -v
```

The self-test runs the buggy starter and reference for each of nine implementation tasks: every
starter must fail and every reference must pass. It checks only unchanged-file/response mechanics
for the three design/review tasks, which still require human judgment. The runtime's agent capability
is not invoked. The self-test result records interpreter, platform and fixture/harness hashes.

Prepare a task:

```bash
python3 tools/evaluate.py prepare --case FX01 --workspace /tmp/fx01-work --record /tmp/fx01-record.json
```

Give an independent agent only that workspace, the task in TASK.md, and the assigned skill condition.
The visible task requests response.md as the final written answer. If the host returns a chat answer,
export that exact answer as response.md, record the export in the host trace, and do not edit the
substance. Preserve the raw transcript independently.

Then grade the artifact and scope outside the agent's accessible environment:

```bash
python3 tools/evaluate.py grade --record /tmp/fx01-record.json --out /tmp/fx01-result.json
python3 tools/evaluate.py adjudicate --result /tmp/fx01-result.json --judgment /tmp/fx01-judgment.json --out /tmp/fx01-reviewed.json
python3 tools/evaluate.py report /tmp/fx01-reviewed.json --out /tmp/fx01-report.json
```

`grade` does not promote a response to Pass merely because code checks pass. It emits `needs_review`
until a reviewer records an outcome. See [ADJUDICATION.md](ADJUDICATION.md). A failing artifact or
scope check cannot be overridden to Pass by a judgment file. Grading errors require investigation
and a separately preserved regrade before adjudication; a regrade of unchanged artifacts is not a
new agent trial. Reports accept JSON records or JSONL;
include the adjudicated result instead of both its raw and reviewed copies. Duplicate run IDs and
same-protocol task/arm/trial duplicates are rejected.

## A/B/C pilot

```bash
python3 tools/evaluate.py pilot --seed 20261026 --repeats 3 --out /tmp/pilot.json
```

This creates a reproducibly shuffled **plan**, with 12 tasks × 3 arms × 3 trials = 108 planned runs.
It executes zero agents. Conditions:

- A: no skill.
- B: original v1.4.0 as distributed, including old public cases; normalize only the enclosing folder
  when the host requires it and record that change. A runtime-only B is a separate condition.
- C: revised v1.5.0 runtime.

Before executing, freeze the model/host revision, tool and permission budget, task snapshots,
completion rules, skill distributions and protocol ID. Use `prepare --arm B|C --skill-hash <sha256>
--trial <n> --host <host> --model <model> --protocol-id <id>`. Hash the exact bytes of the distribution
used, record how a directory hash is constructed, and retain it. B/C preparation requires a hash;
A rejects one. Metadata presence is not attestation that the operator used the recorded host/hash.

Interleave the frozen plan, use fresh contexts/workspaces, blind judges to condition, record actual
read traces and costs, and preserve every failed attempt. Do not pass the expected answer, intended
fix, or prior review diagnosis into a forward-test prompt. All bundled tasks are development cases.
For a fair claim on these cases, avoid exposing their solutions to evaluated threads even though
the maintainer has published them.

`report` separates artifact checks, reviewed outcomes, critical errors, single-trial rates and
any/all-trial success. Missing outcomes remain unscored. Paired C-versus-B and C-versus-A aggregates require matching
fixture identity, equal completed trial counts, consistent skill distribution per arm, and common
host/model/protocol/harness metadata and matching recorded Python/platform. Python/platform here
identify the grader runtime; record the agent execution environment in the host protocol as well.
It averages within task first, then compares tasks. An optional
exploratory bootstrap resamples task-level paired differences, not individual repeated runs. Twelve
tasks are twelve task units, not 108 independent examples. Small convenience samples and public
cases limit inference; do not choose a release threshold after seeing a favorable result. Treat
missing/failed grading as missing evidence to investigate, never automatically as an agent defect.

[run-schema.json](run-schema.json) documents the JSON/JSONL result format for adapters. The CLI
checks the identities and reporting invariants it needs; it is not a general JSON Schema validator.

Token/cost fields default to null. Populate them only from actual trusted host/provider telemetry,
with source provenance; byte counts are not token counts. The current CLI leaves metric ingestion
to a host adapter or preserved external run record. It cannot observe tool reads or token usage itself.

## Holdout lifecycle

Use new tasks and untouched scenario variants for a final generalization claim. A collaborator may
prepare them outside the developer's readable context while freezing the candidate and protocol.
At evaluation time give the agent the visible request and necessary artifacts, keeping graders and
reference solutions inaccessible. Run the preregistered batch, including planned repeats, once.
If findings drive a change, that set becomes development material; use a fresh untouched set for a
later generalization claim. Moving these 60 prose cases or 12 fixture tasks to a holdout folder does
not make them unseen. This repository intentionally includes no claimed sealed holdout.

## Activation and resource selection

[activation-cases.json](activation-cases.json) is a small public trigger set. Run implicit cases under
actual skill discovery without forced activation and explicit cases with the named invocation.
Record activated skills and resource reads from the host, including irrelevant reads/repeated reads.
Metadata inspection or answer wording alone cannot establish activation. Distinguish false activation
from missed activation, and classify ambiguous cases explicitly. Relevance is judged against task
needs, not an obligatory file sequence or the total package's byte size.
