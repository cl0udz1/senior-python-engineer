#!/usr/bin/env python3
"""Copy a validated runtime into a new output directory; never include maintainers."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from validate_skill import DEFAULT_SKILL, validate


def build(skill: Path, output: Path) -> dict:
    skill = skill.resolve()
    output = output.resolve()
    if output == skill or output.is_relative_to(skill) or skill.is_relative_to(output):
        raise ValueError("Output must not overlap the source skill")
    if output.exists():
        raise ValueError("Output must be new; existing artifacts are never overwritten")
    result = validate(skill)
    if not result["ok"]:
        raise ValueError("Source validation failed: " + "; ".join(result["errors"]))
    output.mkdir(parents=True, exist_ok=False)
    target = output / skill.name
    shutil.copytree(skill, target)
    final = validate(target)
    if not final["ok"] or final["files"] != result["files"]:
        raise RuntimeError("Copied runtime failed integrity comparison; inspect output")
    manifest = {"schema_version": 1, "skill": skill.name,
                "metrics": result["metrics"], "files": result["files"]}
    (output / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"runtime": str(target), "manifest": str(output / "runtime-manifest.json"),
            "files": len(result["files"]), "verified": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", type=Path, default=DEFAULT_SKILL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.skill, args.output), indent=2))
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
