#!/usr/bin/env python3
"""Offline integrity checks for this repository's deliberately simple skill format.

This is a project validator, not a general YAML or CommonMark parser. Frontmatter
uses exactly two unquoted, single-line string fields, with an ASCII-letter start
and no colon-space, comment delimiter, or YAML implicit scalar type. Inline and reference-style
Markdown links and GitHub-style headings are supported; code spans are ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

RUNTIME_DIRS = {"agents", "core", "playbooks", "reviews", "references", "catalogs", "templates"}
DEFAULT_SKILL = Path(__file__).resolve().parents[3] / "senior-python-engineer"


def prose_lines(text: str, strip_inline: bool = True):
    """Yield numbered lines outside fenced code with inline code removed."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield number, re.sub(r"(`+)(.*?)\1", "", line) if strip_inline else line


def anchors(text: str) -> set[str]:
    seen: dict[str, int] = {}
    result = set()
    for _, line in prose_lines(text, strip_inline=False):
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        heading = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", match[1])
        slug = re.sub(r"[^\w\-\s]", "", heading.lower()).replace(" ", "-")
        duplicate = seen.get(slug, 0)
        seen[slug] = duplicate + 1
        result.add(f"{slug}-{duplicate}" if duplicate else slug)
    return result


def links(text: str):
    lines = list(prose_lines(text))
    definitions = {}
    for number, line in lines:
        match = re.fullmatch(r"\s{0,3}\[([^]]+)\]:\s*<?([^\s>]+)>?(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*", line)
        if match:
            definitions[match[1].strip().casefold()] = match[2]
            yield number, match[2]
    for number, line in lines:
        for match in re.finditer(r"!?\[[^]\n]*\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+[\"'][^\n]*?[\"'])?\s*\)", line):
            yield number, match[1] or match[2]
        for match in re.finditer(r"!?\[([^]\n]+)\]\[([^]\n]*)\]", line):
            key = (match[2] or match[1]).strip().casefold()
            if key in definitions:
                yield number, definitions[key]
            else:
                yield number, f"UNRESOLVED_REFERENCE:{key}"


def validate(skill: Path) -> dict:
    skill = skill.resolve()
    errors = []
    warnings = []
    files = []
    if not skill.is_dir():
        return {"ok": False, "errors": [f"Skill directory missing: {skill}"], "warnings": []}
    for path in sorted(skill.rglob("*")):
        relative = path.relative_to(skill)
        if path.is_symlink():
            errors.append(f"Symlink is not distributable: {relative}")
            continue
        if relative.parts[0] not in RUNTIME_DIRS and relative.parts[0] != "SKILL.md":
            errors.append(f"Not runtime material: {relative}")
        if path.is_file():
            if path.suffix != ".md" and relative.as_posix() != "agents/openai.yaml":
                errors.append(f"Unexpected runtime file type: {relative}")
            files.append(path)
    entry = skill / "SKILL.md"
    if not entry.is_file() or entry.is_symlink():
        return {"ok": False, "errors": errors + ["Missing ordinary SKILL.md"], "warnings": warnings}
    content = entry.read_text(encoding="utf-8")
    frontmatter = re.match(r"\A---\n(.*?)\n---\n", content, re.S)
    meta = {}
    if not frontmatter:
        errors.append("Missing YAML frontmatter")
    else:
        for line in frontmatter[1].splitlines():
            match = re.fullmatch(r"(name|description): (\S.*)", line)
            if not match or match[1] in meta:
                errors.append("Use exactly one single-line name and description field")
            else:
                meta[match[1]] = match[2]
        if set(meta) != {"name", "description"}:
            errors.append("Frontmatter requires nonempty name and description")
    name = meta.get("name", "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
        errors.append("Invalid skill name")
    if name != skill.name:
        errors.append(f"Folder/name mismatch: {skill.name!r} versus {name!r}")
    description = meta.get("description", "")
    if not description or len(description) > 1024 or any(c in description for c in "<>"):
        errors.append("Invalid description")
    if (not re.match(r"^[A-Za-z]", description)
            or re.search(r":(?:\s|$)|\s#", description)
            or description.casefold() in {"null", "true", "false", "yes", "no", "on", "off"}):
        errors.append("Description must be a plain YAML string in this project's supported scalar subset")
    if len(content.splitlines()) > 500:
        errors.append("Entry point exceeds project limit of 500 lines")

    markdown = {p: p.read_text(encoding="utf-8") for p in files if p.suffix == ".md"}
    anchor_map = {p: anchors(text) for p, text in markdown.items()}
    entry_targets = set()
    local_links = 0
    for path, text in markdown.items():
        for number, target in links(text):
            where = f"{path.relative_to(skill)}:{number}"
            if target.startswith("UNRESOLVED_REFERENCE:"):
                errors.append(f"{where}: {target}")
                continue
            url = urlsplit(target)
            if url.scheme in {"https", "http", "mailto"}:
                continue
            if url.scheme or url.netloc:
                errors.append(f"{where}: unsupported link scheme: {target}")
                continue
            local_links += 1
            dest = (path.parent / unquote(url.path)).resolve() if url.path else path
            if not dest.is_relative_to(skill):
                errors.append(f"{where}: link leaves runtime: {target}")
                continue
            if not dest.is_file():
                errors.append(f"{where}: missing file: {target}")
            elif url.fragment and dest in anchor_map and unquote(url.fragment) not in anchor_map[dest]:
                errors.append(f"{where}: missing heading: {target}")
            if path == entry:
                entry_targets.add(dest)
    for path in markdown:
        if path != entry and path not in entry_targets:
            warnings.append(f"Not linked directly from SKILL.md: {path.relative_to(skill)}")
    invariant_path = skill / "core/python-invariants.md"
    invariant_text = markdown.get(invariant_path, "")
    ids = re.findall(r"^### (I\d+)\b", invariant_text, re.M)
    expected_ids = {f"I{i}" for i in range(1, 17)}
    if len(ids) != 16 or set(ids) != expected_ids:
        errors.append("Canonical invariant IDs must be exactly I1–I16 without duplicates")
    for path, text in markdown.items():
        for match in re.finditer(r"\bI\d+\b", text):
            if match[0] not in expected_ids:
                errors.append(f"{path.relative_to(skill)}: unknown invariant {match[0]}")
    return {
        "ok": not errors, "errors": errors, "warnings": warnings,
        "metrics": {"files": len(files), "markdown_files": len(markdown),
                    "bytes": sum(p.stat().st_size for p in files),
                    "words": sum(len(t.split()) for t in markdown.values()),
                    "entry_lines": len(content.splitlines()), "entry_words": len(content.split()),
                    "entry_bytes": len(content.encode()), "local_links_checked": local_links,
                    "note": "File sizes and whitespace word counts; not model tokens or observed retrieval cost."},
        "files": [{"path": p.relative_to(skill).as_posix(), "bytes": p.stat().st_size,
                   "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", type=Path, nargs="?", default=DEFAULT_SKILL)
    parser.add_argument("--json", action="store_true", help="Include metrics and checksums")
    args = parser.parse_args()
    result = validate(args.skill)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("PASS" if result["ok"] else "FAIL")
        for item in result["errors"]:
            print(f"ERROR: {item}")
        for item in result["warnings"]:
            print(f"WARNING: {item}")
        if "metrics" in result:
            print(json.dumps(result["metrics"], indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
