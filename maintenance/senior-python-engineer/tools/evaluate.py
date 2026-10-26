#!/usr/bin/env python3
"""Local development evaluation plumbing; does not invoke a model or create a sandbox.

Only run candidate code in an appropriately isolated executor. See evals/HARNESS.md.
All bundled tasks and reference answers are PUBLIC DEVELOPMENT material.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
CRITICAL_IDS = {"C1", "C2", "C3", "C4"}
IGNORED_DIRS = {"__pycache__", ".pytest_cache"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value, *, exclusive: bool = True):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Symlink not allowed in evaluation workspace: {rel}")
        if path.is_file():
            result[rel.as_posix()] = digest_bytes(path.read_bytes())
    return result


def tree_digest(root: Path) -> str:
    return digest_bytes(json.dumps(inventory(root), sort_keys=True).encode())


def cases() -> dict:
    data = read_json(EVALS / "fixtures.json")
    items = {item["id"]: item for item in data["cases"]}
    if len(items) != len(data["cases"]):
        raise ValueError("Duplicate fixture ID")
    return items


def case_for(case_id: str) -> dict:
    try:
        return cases()[case_id]
    except KeyError as exc:
        raise ValueError(f"Unknown case {case_id}") from exc


def public_cases() -> dict:
    """Validate the six-field legacy format and expose only Input/Context for delivery."""
    expected = ["Input", "Context", "Desired reasoning behavior", "Acceptable outcomes", "Failure modes", "Critical mistakes"]
    result = {}
    for path in sorted(EVALS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        headings = list(re.finditer(r"^### Case ([A-Z]+\d+)\s+[^\n]*", text, re.MULTILINE))
        for index, heading in enumerate(headings):
            block = text[heading.end():headings[index + 1].start() if index + 1 < len(headings) else len(text)]
            fields = list(re.finditer(r"^\*\*(Input|Context|Desired reasoning behavior|Acceptable outcomes|Failure modes|Critical mistakes)\*\*\s*$", block, re.MULTILINE))
            names = [field.group(1) for field in fields]
            if names != expected:
                raise ValueError(f"{path.name} {heading.group(1)} must contain exactly the six ordered fields")
            if heading.group(1) in result:
                raise ValueError(f"Duplicate public case ID {heading.group(1)}")
            values = {field.group(1): block[field.end():fields[i + 1].start() if i + 1 < len(fields) else len(block)].strip()
                      for i, field in enumerate(fields)}
            result[heading.group(1)] = {"case_id": heading.group(1), "source": path.name,
                                        "classification": "public_development", "input": values["Input"], "context": values["Context"]}
    return result


def is_inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def outside_workspace(path: Path, workspace: Path):
    if is_inside(path.resolve(), workspace.resolve()):
        raise ValueError("Evaluator records/results must be outside the candidate workspace")


def case_fingerprint(case: dict) -> str:
    data = {"case": case, "visible": tree_digest(EVALS / "fixtures" / case["id"])}
    if case["grader"]:
        data["grader"] = digest_bytes((EVALS / "graders" / case["grader"]).read_bytes())
    return digest_bytes(json.dumps(data, sort_keys=True).encode())


def prepare(case_id: str, workspace: Path, record_path: Path, *, arm: str = "dev",
            trial: int = 1, host: str | None = None, model: str | None = None,
            skill_hash: str | None = None, protocol_id: str | None = None) -> dict:
    case = case_for(case_id)
    workspace = workspace.resolve()
    record_path = record_path.resolve()
    outside_workspace(record_path, workspace)
    if workspace.exists() or record_path.exists():
        raise ValueError("Use fresh, nonexistent workspace and record paths; no overwrite/reset is implicit")
    if trial < 1:
        raise ValueError("Trial must be positive")
    if arm == "A" and skill_hash is not None:
        raise ValueError("Arm A is no skill; do not supply a skill hash")
    if arm in {"B", "C"} and not skill_hash:
        raise ValueError("Comparative skill arms require an exact distribution hash")
    if skill_hash and (len(skill_hash) != 64 or any(c not in "0123456789abcdef" for c in skill_hash)):
        raise ValueError("Skill hash must be a lowercase SHA-256 hex digest")
    fixture = EVALS / "fixtures" / case_id
    shutil.copytree(fixture / "starter", workspace)
    shutil.copy2(fixture / "task.md", workspace / "TASK.md")
    record = {
        "schema_version": 1, "run_id": f"{case_id}-{arm}-{trial}-{time.time_ns()}",
        "case_id": case_id, "arm": arm, "trial": trial, "workspace": str(workspace),
        "classification": "public_development", "created_utc": datetime.now(timezone.utc).isoformat(),
        "host": host, "model": model, "skill_hash": skill_hash, "protocol_id": protocol_id,
        "fixture_hash": case_fingerprint(case), "initial_files": inventory(workspace),
        "harness_hash": digest_bytes(Path(__file__).read_bytes()),
    }
    write_json(record_path, record)
    return record


def scope_check(case: dict, record: dict, workspace: Path) -> dict:
    before = record["initial_files"]
    after = inventory(workspace)
    changed = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
    unapproved = sorted(set(changed) - set(case["allowed_changes"]))
    response = workspace / "response.md"
    issues = [f"Out-of-scope file change: {name}" for name in unapproved]
    if not response.is_file() or not response.read_text(encoding="utf-8").strip():
        issues.append("A nonempty response.md is required; content still needs judgment")
    if case["id"] == "FX09" and response.is_file() and len(response.read_text().split()) > 700:
        issues.append("Design response exceeds the visible 700-word limit")
    return {"passed": not issues, "changed_files": changed, "issues": issues,
            "final_files": after, "limitation": "Final snapshots cannot detect temporary reverted edits or unauthorized commands; inspect host traces."}


def run_grader(case: dict, workspace: Path, timeout: float = 15) -> dict:
    if not case["grader"]:
        return {"status": "not_applicable", "reason": "Design/review correctness requires adjudication"}
    grader = EVALS / "graders" / case["grader"]
    # Explicit import path keeps artifacts local; this is NOT a security boundary.
    runner = """import json,runpy,sys,types,unittest
from pathlib import Path
workspace,target,completion=sys.argv[1:]
sys.path.insert(0,workspace)
sys.argv=[target]
namespace=runpy.run_path(target,run_name='evaluation_grader')
module=types.ModuleType('evaluation_grader')
module.__dict__.update(namespace)
sys.modules['evaluation_grader']=module
suite=unittest.defaultTestLoader.loadTestsFromModule(module)
result=unittest.TextTestRunner(verbosity=1).run(suite)
summary={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'successful':result.wasSuccessful()}
Path(completion).write_text(json.dumps(summary),encoding='utf-8')
sys.exit(0 if result.wasSuccessful() and result.testsRun>len(result.skipped) else 1)
"""
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "SYSTEMROOT", "WINDIR", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP"}}
    started = time.monotonic()
    # File-backed logs avoid unbounded capture buffers. The outer sandbox must enforce disk/process limits.
    with tempfile.TemporaryDirectory(prefix="skill-eval-grader-") as temp:
        log_path = Path(temp) / "grader.log"
        completion_path = Path(temp) / "completion.json"
        command = [sys.executable, "-I", "-B", "-c", runner, str(workspace), str(grader), str(completion_path)]
        with log_path.open("w+b") as log:
            proc = subprocess.Popen(command, cwd=workspace, env=env, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, start_new_session=os.name == "posix")
            timed_out = False
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                if os.name == "posix":
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
                proc.wait()
            log.seek(0)
            content = log.read(65536).decode("utf-8", errors="replace")
            truncated = log.read(1) != b""
        summary = None
        if completion_path.is_file():
            try:
                summary = read_json(completion_path)
                counts = [summary[key] for key in ["tests_run", "failures", "errors", "skipped"]]
                if any(type(value) is not int or value < 0 for value in counts) or type(summary.get("successful")) is not bool:
                    summary = None
            except (ValueError, KeyError, TypeError):
                summary = None
        completed_tests = summary is not None and summary["tests_run"] > summary["skipped"]
    status = "error" if timed_out or not completed_tests else "passed" if proc.returncode == 0 and summary["successful"] and summary["failures"] == summary["errors"] == 0 else "failed"
    return {"status": status, "test_summary": summary,
            "completion_record_present": summary is not None,
            "exit_code": proc.returncode, "timed_out": timed_out, "log": content,
            "log_truncated": truncated, "duration_seconds": time.monotonic() - started,
            "command": command,
            "limitation": "Runs candidate Python; external sandbox, network/process limits and grader-tamper review are caller responsibilities."}


def grade(record_path: Path, result_path: Path, timeout: float = 15) -> dict:
    record = read_json(record_path)
    case = case_for(record["case_id"])
    workspace = Path(record["workspace"]).resolve()
    outside_workspace(result_path, workspace)
    if result_path.exists():
        raise ValueError("Result path exists; use a new path to preserve prior evidence")
    if record["fixture_hash"] != case_fingerprint(case):
        raise ValueError("Fixture/grader changed after preparation; prepare a new run")
    if record["harness_hash"] != digest_bytes(Path(__file__).read_bytes()):
        raise ValueError("Harness changed after preparation; prepare a new run")
    # Check before and after tests because the candidate itself could change files when imported.
    before = scope_check(case, record, workspace)
    execution = run_grader(case, workspace, timeout)
    scope = scope_check(case, record, workspace)
    scope["issues"] = sorted(set(before["issues"] + scope["issues"]))
    scope["passed"] = not scope["issues"]
    code_ok = execution["status"] in {"passed", "not_applicable"}
    result = {key: record[key] for key in ["schema_version", "run_id", "case_id", "arm", "trial",
              "classification", "host", "model", "skill_hash", "protocol_id", "fixture_hash", "harness_hash"]}
    result.update({
        "family": case["family"], "mode": case["mode"],
        "graded_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "scope": scope, "execution": execution, "artifact_checks_passed": code_ok and scope["passed"],
        "judgment": None, "outcome": "needs_review" if execution["status"] == "error" or (code_ok and scope["passed"]) else "fail",
        "metrics": {"input_tokens": None, "output_tokens": None, "skill_tokens_loaded": None,
                    "tool_calls": None, "agent_wall_seconds": None, "cost_usd": None},
        "evidence": {"response_sha256": scope["final_files"].get("response.md"),
                     "host_trace": None, "metrics_source": None},
    })
    write_json(result_path, result)
    return result


def adjudicate(result_path: Path, judgment_path: Path, output: Path) -> dict:
    result = read_json(result_path)
    judgment = read_json(judgment_path)
    if result.get("judgment") is not None:
        raise ValueError("Result already adjudicated; preserve it and start a separately labelled re-review")
    if result["execution"]["status"] == "error":
        raise ValueError("Resolve the grader execution error and preserve a separately recorded regrade before adjudicating")
    if judgment.get("run_id") != result["run_id"]:
        raise ValueError("Judgment must name the exact run_id")
    if judgment.get("outcome") not in {"pass", "partial", "fail", "critical"}:
        raise ValueError("Judgment outcome must be pass/partial/fail/critical")
    if not judgment.get("reviewer") or not judgment.get("evidence") or not judgment.get("rationale"):
        raise ValueError("Reviewer, concrete evidence references, and rationale are required")
    if not isinstance(judgment.get("critical_checks", []), list):
        raise ValueError("critical_checks must be a list")
    for check in judgment.get("critical_checks", []):
        if check.get("category") not in CRITICAL_IDS or not check.get("trigger") or not check.get("evidence"):
            raise ValueError("Critical checks require C1–C4, observable trigger, and evidence")
    if (judgment["outcome"] == "critical") != bool(judgment.get("critical_checks")):
        raise ValueError("Critical outcome and critical-check evidence must agree")
    result["judgment"] = judgment
    result["outcome"] = judgment["outcome"] if result["artifact_checks_passed"] else (
        "critical" if judgment["outcome"] == "critical" else "fail")
    write_json(output, result)
    return result


def pilot(seed: int, repeats: int, output: Path):
    if repeats < 1:
        raise ValueError("Repeats must be positive")
    tasks = cases()
    trials = [{"case_id": case_id, "arm": arm, "trial": trial}
              for case_id in tasks for arm in "ABC" for trial in range(1, repeats + 1)]
    random.Random(seed).shuffle(trials)
    plan = {"schema_version": 1, "classification": "public_development_pilot", "seed": seed,
            "distinct_tasks": len(tasks), "trials": trials, "repeats_per_task_arm": repeats,
            "conditions": {
                "A": "No skill",
                "B": "Original v1.4.0 as distributed, including old public eval cases; only normalize enclosing folder if host requires, and record it",
                "C": "Revised v1.5.0 runtime distribution"},
            "required_before_execution": ["Freeze host, model, tool/permission budget, candidate hashes, task snapshots and protocol ID",
                "Mount only visible task/artifacts and the assigned skill; evaluator answers and prior runs inaccessible",
                "Reset context and writable workspace per trial; capture actual tool/read traces and usage",
                "Blind judges to condition/version; preserve raw output and failing trials"],
            "statistical_unit": "Task; repeats are correlated, not independent task types",
            "heldout": False,
            "limitation": "These 12 published fixture tasks are development checks, not unseen held-out evidence."}
    write_json(output, plan)
    return {"distinct_tasks": len(tasks), "runs_planned": len(trials), "executed": 0}


def load_results(paths: list[Path]) -> list[dict]:
    results = []
    for path in paths:
        if path.suffix == ".jsonl":
            results.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
        else:
            results.append(read_json(path))
    seen = set()
    trials = set()
    for result in results:
        if result.get("schema_version") != 1 or result.get("outcome") not in {"needs_review", "pass", "partial", "fail", "critical"}:
            raise ValueError("Unsupported or malformed run result")
        if result["run_id"] in seen:
            raise ValueError("Duplicate run_id: choose either raw or adjudicated record, not both")
        seen.add(result["run_id"])
        trial_key = (result["protocol_id"], result["host"], result["model"], result["case_id"], result["arm"], result["trial"])
        if trial_key in trials:
            raise ValueError("Duplicate task/arm/trial in one protocol; do not count reruns twice")
        trials.add(trial_key)
    return results


def report(paths: list[Path]) -> dict:
    results = load_results(paths)
    groups = {}
    for result in results:
        groups.setdefault((result["case_id"], result["arm"]), []).append(result)
    per_task = []
    for (case_id, arm), runs in sorted(groups.items()):
        reviewed = [r for r in runs if r["judgment"] is not None]
        successes = sum(r["outcome"] == "pass" for r in reviewed)
        per_task.append({"case_id": case_id, "arm": arm, "runs": len(runs), "adjudicated": len(reviewed),
                         "artifact_checks_passed": sum(r["artifact_checks_passed"] for r in runs),
                         "grading_errors": sum(r.get("execution", {}).get("status") == "error" for r in runs),
                         "pass_rate": successes / len(reviewed) if reviewed else None,
                         "any_success": bool(successes) if len(reviewed) == len(runs) else None,
                         "all_success": successes == len(runs) if len(reviewed) == len(runs) else None,
                         "critical": sum(r["outcome"] == "critical" for r in reviewed)})
    warnings = ["Public development results do not establish unseen-task generalization.",
                "Artifact checks alone are not complete task outcomes; unreviewed runs remain unscored."]
    environment = {(r["host"], r["model"], r["protocol_id"], r["harness_hash"], r.get("python"), r.get("platform")) for r in results}
    if len(environment) > 1 or any(not r["host"] or not r["model"] or not r["protocol_id"] or not r.get("python") or not r.get("platform") for r in results):
        warnings.append("Missing or mixed host/model/protocol/harness/Python/platform metadata: paired aggregates suppressed.")
        comparable = False
    else:
        comparable = True
    for arm in "BC":
        hashes = {r["skill_hash"] for r in results if r["arm"] == arm}
        if len(hashes) > 1 or None in hashes:
            warnings.append(f"Missing or mixed skill distributions for arm {arm}: paired aggregate suppressed.")
            comparable = False
    def paired_against(reference_arm):
        differences = []
        if comparable:
            by_key = {(r["case_id"], r["arm"]): r for r in per_task}
            for case_id in sorted({r["case_id"] for r in results}):
                baseline, candidate = by_key.get((case_id, reference_arm)), by_key.get((case_id, "C"))
                if baseline and candidate and baseline["runs"] == candidate["runs"] and baseline["adjudicated"] == baseline["runs"] and candidate["adjudicated"] == candidate["runs"]:
                    baseline_hashes = {r["fixture_hash"] for r in groups[(case_id, reference_arm)]}
                    candidate_hashes = {r["fixture_hash"] for r in groups[(case_id, "C")]}
                    if len(baseline_hashes) == 1 and baseline_hashes == candidate_hashes:
                        differences.append({"case_id": case_id, f"C_minus_{reference_arm}": candidate["pass_rate"] - baseline["pass_rate"]})
        paired = {"distinct_paired_tasks": len(differences), "per_task": differences, "mean_difference": None,
                  "exploratory_task_bootstrap_95_percent_interval": None}
        if differences:
            values = [r[f"C_minus_{reference_arm}"] for r in differences]
            paired["mean_difference"] = statistics.mean(values)
            if len(values) >= 2:
                rng = random.Random(8923)
                samples = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(2000))
                paired["exploratory_task_bootstrap_95_percent_interval"] = [samples[49], samples[1949]]
        return paired
    paired_b, paired_a = paired_against("B"), paired_against("A")
    if paired_b["mean_difference"] is not None or paired_a["mean_difference"] is not None:
        warnings.append("Bootstrap resamples task-level paired rates; small/convenience task sets limit inference.")
    return {"schema_version": 1, "runs": len(results), "distinct_tasks": len({r["case_id"] for r in results}),
            "per_task_arm": per_task, "paired_C_vs_B": paired_b, "paired_C_vs_A": paired_a, "warnings": warnings}


def selftest() -> dict:
    records = []
    with tempfile.TemporaryDirectory(prefix="skill-eval-selftest-") as temp:
        root = Path(temp)
        for case_id, case in cases().items():
            variants = ["baseline", "reference"] if case["reference"] else ["unchanged_scope"]
            for variant in variants:
                workspace = root / f"{case_id}-{variant}"
                record = root / f"{case_id}-{variant}.record.json"
                prepare(case_id, workspace, record)
                if variant == "reference":
                    shutil.copy2(EVALS / "reference" / case_id / "solution.py", workspace / "solution.py")
                (workspace / "response.md").write_text("Fixture plumbing self-test; this is not an agent outcome.\n")
                result = grade(record, root / f"{case_id}-{variant}.result.json")
                expected = variant != "baseline"
                actual = result["artifact_checks_passed"]
                records.append({"case_id": case_id, "variant": variant, "expected_artifact_pass": expected,
                                "actual_artifact_pass": actual, "as_expected": expected == actual,
                                "execution_status": result["execution"]["status"],
                                "failure_log": result["execution"].get("log") if expected != actual else None})
    return {"schema_version": 1, "kind": "fixture_and_grader_selftest", "passed": all(r["as_expected"] for r in records),
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "harness_hash": digest_bytes(Path(__file__).read_bytes()),
            "fixture_hashes": {case_id: case_fingerprint(case) for case_id, case in cases().items()},
            "python": sys.version.split()[0], "platform": platform.platform(), "checks": records,
            "not_measured": ["Agent quality", "Automatic skill activation", "Unseen-task generalization",
                             "Actual Windows shell execution", "PostgreSQL SQLSTATE behavior"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("public-list")
    export = sub.add_parser("export-case")
    export.add_argument("--case", required=True)
    export.add_argument("--out", required=True, type=Path)
    prep = sub.add_parser("prepare")
    prep.add_argument("--case", required=True)
    prep.add_argument("--workspace", required=True, type=Path)
    prep.add_argument("--record", required=True, type=Path)
    prep.add_argument("--arm", choices=["dev", "A", "B", "C"], default="dev")
    prep.add_argument("--trial", type=int, default=1)
    for field in ["host", "model", "skill-hash", "protocol-id"]:
        prep.add_argument("--" + field)
    grad = sub.add_parser("grade")
    grad.add_argument("--record", type=Path, required=True)
    grad.add_argument("--out", type=Path, required=True)
    grad.add_argument("--timeout", type=float, default=15)
    judge = sub.add_parser("adjudicate")
    judge.add_argument("--result", type=Path, required=True)
    judge.add_argument("--judgment", type=Path, required=True)
    judge.add_argument("--out", type=Path, required=True)
    plan = sub.add_parser("pilot")
    plan.add_argument("--seed", type=int, default=20261026)
    plan.add_argument("--repeats", type=int, default=3)
    plan.add_argument("--out", type=Path, required=True)
    rep = sub.add_parser("report")
    rep.add_argument("results", nargs="+", type=Path)
    rep.add_argument("--out", type=Path)
    check = sub.add_parser("selftest")
    check.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "list":
            value = [{key: case[key] for key in ["id", "family", "mode", "manual_outcome"]} for case in cases().values()]
        elif args.command == "public-list":
            value = [{"case_id": key, "source": item["source"]} for key, item in public_cases().items()]
        elif args.command == "export-case":
            public = public_cases()
            if args.case not in public:
                raise ValueError(f"Unknown public case {args.case}")
            value = public[args.case]
            write_json(args.out, value)
        elif args.command == "prepare":
            value = prepare(args.case, args.workspace, args.record, arm=args.arm, trial=args.trial,
                            host=args.host, model=args.model, skill_hash=args.skill_hash, protocol_id=args.protocol_id)
        elif args.command == "grade":
            value = grade(args.record, args.out, args.timeout)
        elif args.command == "adjudicate":
            value = adjudicate(args.result, args.judgment, args.out)
        elif args.command == "pilot":
            value = pilot(args.seed, args.repeats, args.out)
        elif args.command == "report":
            value = report(args.results)
            if args.out:
                write_json(args.out, value)
        else:
            value = selftest()
            if args.out:
                write_json(args.out, value)
        print(json.dumps(value, indent=2, sort_keys=True))
        return 1 if args.command == "selftest" and not value["passed"] else 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"Evaluation error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
