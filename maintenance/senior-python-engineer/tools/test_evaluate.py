"""Tests for evidence integrity, not a model benchmark."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import evaluate as e


class HarnessIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_prepare_exposes_only_visible_task_and_starter(self):
        workspace, record = self.root / "work", self.root / "record.json"
        data = e.prepare("FX09", workspace, record)
        self.assertEqual(set(e.inventory(workspace)), {"TASK.md", "solution.py", "project.txt"})
        self.assertNotIn("reference", json.dumps(data))
        with self.assertRaises(ValueError):
            e.prepare("FX09", workspace, self.root / "other.json")

    def test_public_case_export_validates_all_60_without_answer_fields(self):
        public = e.public_cases()
        self.assertEqual(len(public), 60)
        self.assertEqual(set(public["AS8"]), {"case_id", "source", "classification", "input", "context"})
        for case_id in ["DM1", "DM2", "DM3", "DM4", "DM5"]:
            self.assertNotIn("route to", public[case_id]["context"])
            self.assertNotIn("playbooks/", public[case_id]["context"])

    def test_record_cannot_be_placed_in_candidate_workspace(self):
        workspace = self.root / "work"
        with self.assertRaises(ValueError):
            e.prepare("FX09", workspace, workspace / "record.json")
        self.assertFalse(workspace.exists())

    def test_scope_detects_review_edit_and_deleted_project_file(self):
        workspace, record = self.root / "work", self.root / "record.json"
        data = e.prepare("FX10", workspace, record)
        (workspace / "response.md").write_text("No issue found.")
        self.assertTrue(e.scope_check(e.case_for("FX10"), data, workspace)["passed"])
        (workspace / "solution.py").write_text("# silently rewritten\n")
        (workspace / "project.txt").unlink()
        check = e.scope_check(e.case_for("FX10"), data, workspace)
        self.assertFalse(check["passed"])
        self.assertEqual(len(check["issues"]), 2)

    def test_grading_rejects_changed_fixture_identity(self):
        workspace, record = self.root / "work", self.root / "record.json"
        e.prepare("FX09", workspace, record)
        (workspace / "response.md").write_text("Design.")
        with patch.object(e, "case_fingerprint", return_value="different"):
            with self.assertRaises(ValueError):
                e.grade(record, self.root / "result.json")

    def test_design_with_empty_judgment_never_becomes_pass(self):
        workspace, record = self.root / "work", self.root / "record.json"
        e.prepare("FX09", workspace, record)
        (workspace / "response.md").write_text("A syntactically present response could still be nonsense.")
        result = e.grade(record, self.root / "result.json")
        self.assertTrue(result["artifact_checks_passed"])
        self.assertEqual(result["outcome"], "needs_review")

    def test_critical_judgment_requires_defined_category_and_evidence(self):
        workspace, record = self.root / "work", self.root / "record.json"
        e.prepare("FX09", workspace, record)
        (workspace / "response.md").write_text("Design.")
        result_path = self.root / "result.json"
        result = e.grade(record, result_path)
        judgment = {"run_id": result["run_id"], "reviewer": "test-reviewer", "outcome": "critical",
                    "evidence": ["response.md:1"], "rationale": "Test-only input",
                    "critical_checks": [{"category": "C5", "trigger": "Scope", "evidence": "response.md:1"}]}
        path = self.root / "judgment.json"
        e.write_json(path, judgment)
        with self.assertRaises(ValueError):
            e.adjudicate(result_path, path, self.root / "adjudicated.json")
        judgment["critical_checks"][0]["category"] = "C1"
        e.write_json(path, judgment, exclusive=False)
        self.assertEqual(e.adjudicate(result_path, path, self.root / "adjudicated.json")["outcome"], "critical")

    def test_pilot_is_reproducible_and_explicitly_unexecuted(self):
        a, b = self.root / "a.json", self.root / "b.json"
        summary = e.pilot(19, 3, a)
        e.pilot(19, 3, b)
        self.assertEqual(e.read_json(a), e.read_json(b))
        self.assertEqual(summary, {"distinct_tasks": 12, "runs_planned": 108, "executed": 0})
        self.assertFalse(e.read_json(a)["heldout"])

    def test_zero_tests_and_early_exit_cannot_pass(self):
        fixture = self.root / "evals"
        (fixture / "graders").mkdir(parents=True)
        workspace = self.root / "work"
        workspace.mkdir()
        for index, source in enumerate(["# no tests\n", "raise SystemExit(0)\n", "import os; os._exit(0)\n"]):
            grader = f"early{index}.py"
            (fixture / "graders" / grader).write_text(source)
            with self.subTest(source=source), patch.object(e, "EVALS", fixture):
                result = e.run_grader({"grader": grader}, workspace)
                self.assertEqual(result["status"], "error")

    def test_runtime_mismatch_suppresses_aggregate(self):
        rows=[]
        for arm in "AC":
            rows.append({"schema_version": 1, "run_id": arm, "case_id": "FX01", "arm": arm, "trial": 1,
                         "protocol_id": "unit-test-only", "host": "fixture", "model": "fixture", "harness_hash": "same",
                         "python": "3.11" if arm=="A" else "3.12", "platform": "fixture-os",
                         "skill_hash": None if arm=="A" else "c"*64, "fixture_hash": "same",
                         "artifact_checks_passed": True, "judgment": {"reviewer": "test"}, "outcome": "pass"})
        path=self.root/'mismatch.jsonl';path.write_text('\n'.join(json.dumps(r) for r in rows))
        result=e.report([path]);self.assertEqual(result['paired_C_vs_A']['distinct_paired_tasks'],0)
        self.assertTrue(any('Python/platform' in message for message in result['warnings']))

    def test_task_level_pairing_and_duplicate_trials(self):
        rows = []
        for case_id in ("FX01", "FX02"):
            for arm in "ABC":
                for trial in (1, 2, 3):
                    outcome = "pass" if arm == "C" or case_id == "FX01" else "fail"
                    rows.append({"schema_version": 1, "run_id": f"{case_id}-{arm}-{trial}",
                                 "case_id": case_id, "arm": arm, "trial": trial,
                                 "protocol_id": "unit-test-only", "host": "fixture", "model": "fixture",
                                 "python": "3.12", "platform": "fixture-os",
                                 "harness_hash": "same", "skill_hash": None if arm == "A" else arm * 64, "fixture_hash": case_id,
                                 "artifact_checks_passed": outcome == "pass", "judgment": {"reviewer": "test"},
                                 "outcome": outcome})
        path = self.root / "synthetic.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in rows))
        result = e.report([path])
        self.assertEqual(result["runs"], 18)
        self.assertEqual(result["paired_C_vs_B"]["distinct_paired_tasks"], 2)
        self.assertEqual(result["paired_C_vs_B"]["mean_difference"], 0.5)
        self.assertEqual(result["paired_C_vs_A"]["mean_difference"], 0.5)
        duplicate = copy.deepcopy(rows[0]); duplicate["run_id"] = "other-run-id"
        with path.open("a") as handle:
            handle.write("\n" + json.dumps(duplicate))
        with self.assertRaises(ValueError):
            e.report([path])


if __name__ == "__main__":
    unittest.main()
