"""Release-tool checks: reject contamination, broken navigation, and unsafe copies."""
import shutil
import re
import tempfile
import unittest
from pathlib import Path

from build_runtime import build
from validate_skill import DEFAULT_SKILL, anchors, links, validate


class PackageToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / "source" / "senior-python-engineer"
        shutil.copytree(DEFAULT_SKILL, self.skill)

    def test_current_package_validates(self):
        result = validate(self.skill)
        self.assertTrue(result["ok"], result["errors"])

    def test_typing_and_fenced_examples_are_not_links(self):
        example = "`type Vector[T] = list[T]`\n```python\n[missing](missing.md)\n```\n[real](real.md)"
        self.assertEqual(list(links(example)), [(5, "real.md")])

    def test_claim_label_is_not_a_reference_definition(self):
        self.assertEqual(list(links("[HEURISTIC]: pick the existing tool.")), [])
        self.assertEqual(anchors("## A `real` heading\n## A `real` heading"),
                         {"a-real-heading", "a-real-heading-1"})

    def test_bad_link_and_escape_are_rejected(self):
        entry = self.skill / "SKILL.md"
        entry.write_text(entry.read_text() + "\n[bad](no-such-file.md)\n[escape](../answer-key.md)\n")
        errors = validate(self.skill)["errors"]
        self.assertTrue(any("missing file" in x for x in errors))
        self.assertTrue(any("leaves runtime" in x for x in errors))

    def test_maintainer_material_and_symlink_rejected(self):
        (self.skill / "evals").mkdir()
        (self.skill / "evals/key.md").write_text("answers")
        (self.skill / "references/linked.md").symlink_to(self.root / "secret.md")
        errors = validate(self.skill)["errors"]
        self.assertTrue(any("Not runtime material" in x for x in errors))
        self.assertTrue(any("Symlink" in x for x in errors))

    def test_name_and_empty_description_rejected(self):
        entry = self.skill / "SKILL.md"
        text = entry.read_text().replace("name: senior-python-engineer", "name: another-skill")
        text = "\n".join("description: " if line.startswith("description:") else line for line in text.splitlines())
        entry.write_text(text)
        self.assertFalse(validate(self.skill)["ok"])

    def test_ambiguous_yaml_scalars_cannot_be_built(self):
        entry = self.skill / "SKILL.md"
        original = entry.read_text()
        for value in ["Review Python: inspect the code.", "true", "Use Python # truncated", "'quoted'", "|", "2026-10-26"]:
            with self.subTest(value=value):
                entry.write_text(re.sub(r"^description:.*$", "description: " + value, original, flags=re.M))
                self.assertFalse(validate(self.skill)["ok"])
                with self.assertRaises(ValueError):
                    build(self.skill, self.root / "invalid-output")

    def test_build_preserves_hashes_and_refuses_overwrite(self):
        output = self.root / "dist"
        result = build(self.skill, output)
        self.assertTrue(result["verified"])
        self.assertEqual(validate(self.skill)["files"], validate(output / self.skill.name)["files"])
        self.assertFalse((output / self.skill.name / "evals").exists())
        with self.assertRaises(ValueError):
            build(self.skill, output)
        with self.assertRaises(ValueError):
            build(self.skill, self.skill / "nested")


if __name__ == "__main__":
    unittest.main()
