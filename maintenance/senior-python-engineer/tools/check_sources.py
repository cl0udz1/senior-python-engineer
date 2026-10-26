#!/usr/bin/env python3
"""Validate source-register structure and report review dates, without network I/O."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from validate_skill import DEFAULT_SKILL

DEFAULT_RESEARCH = Path(__file__).resolve().parents[1] / "research"


def check(registers: list[Path], skill: Path, as_of: dt.date) -> dict:
    errors, due, seen = [], [], set()
    count = 0
    for register in registers:
        try:
            data = json.loads(register.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"{register.name}: {exc}")
            continue
        if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("claims"), list):
            errors.append(f"{register.name}: invalid register shape")
            continue
        for claim in data["claims"]:
            count += 1
            if not isinstance(claim, dict):
                errors.append(f"{register.name}: claim must be an object")
                continue
            identifier = claim.get("id")
            if not isinstance(identifier, str) or not identifier or identifier in seen:
                errors.append(f"{register.name}: empty or duplicate claim ID: {identifier!r}")
                continue
            seen.add(identifier)
            for key in ("claim", "layer", "review_trigger"):
                if not isinstance(claim.get(key), str) or not claim[key].strip():
                    errors.append(f"{identifier}: missing {key}")
            if not isinstance(claim.get("scope"), dict) or not claim["scope"]:
                errors.append(f"{identifier}: explicit scope required")
            paths = claim.get("files")
            if not isinstance(paths, list) or not paths:
                errors.append(f"{identifier}: affected files required")
            else:
                for relative in paths:
                    if not isinstance(relative, str):
                        errors.append(f"{identifier}: invalid file path")
                        continue
                    target = (skill / relative).resolve()
                    if not target.is_relative_to(skill.resolve()) or not target.is_file():
                        errors.append(f"{identifier}: missing/outside runtime file: {relative}")
            sources = claim.get("sources")
            if not isinstance(sources, list) or not sources:
                errors.append(f"{identifier}: primary source URLs required")
            else:
                for source in sources:
                    if not isinstance(source, str) or urlsplit(source).scheme != "https" or not urlsplit(source).netloc:
                        errors.append(f"{identifier}: invalid source URL")
            try:
                verified = dt.date.fromisoformat(claim["verified_on"])
                interval = claim.get("review_after_days", 180)
                if isinstance(interval, bool) or not isinstance(interval, int) or interval < 1:
                    raise ValueError("review_after_days must be a positive integer")
                if verified > as_of:
                    errors.append(f"{identifier}: verification is after as-of date")
                review_on = verified + dt.timedelta(days=interval)
                if review_on <= as_of:
                    due.append({"id": identifier, "review_on": review_on.isoformat(),
                                "trigger": claim.get("review_trigger")})
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                errors.append(f"{identifier}: invalid verification/review date: {exc}")
    return {"ok": not errors, "claims": count, "as_of": as_of.isoformat(),
            "errors": errors, "review_due": due,
            "limits": "Offline structure/age check only; URLs and factual currency are not verified."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registers", nargs="*", type=Path)
    parser.add_argument("--skill", type=Path, default=DEFAULT_SKILL)
    parser.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.date.today())
    parser.add_argument("--fail-on-due", action="store_true")
    args = parser.parse_args()
    registers = args.registers or [DEFAULT_RESEARCH / "technical-claims.json", DEFAULT_RESEARCH / "authoring-claims.json"]
    result = check(registers, args.skill, args.as_of)
    print(json.dumps(result, indent=2))
    return 1 if result["errors"] or (args.fail_on_due and result["review_due"]) else 0


if __name__ == "__main__":
    sys.exit(main())
