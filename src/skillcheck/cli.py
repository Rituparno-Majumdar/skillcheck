"""skillcheck — validate Agent Skills (SKILL.md) directories.

Zero-dependency CLI that checks Claude Code / opencode style Agent Skill
directories for the mistakes that silently break skill loading: missing
SKILL.md, absent or malformed `name`/`description`, invalid `allowed-tools`,
bad license types, and broken references to files inside the skill directory.
Exit code 1 signals issues for CI gating.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

__version__ = "0.1.0"

REQUIRED_FIELDS = ("name", "description")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SCALAR_FIELDS = ("name", "description", "license")
LIST_FIELDS = ("allowed-tools",)
FIELD_RE = re.compile(r"^([a-zA-Z-]+):\s*(.*)$")
FENCE_RE = re.compile(r"```")
REF_INLINE = re.compile(r"`([^`\s]+)`")
REF_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
REF_FENCE_PATH = re.compile(r"\b[\w./-]+/[\w./-]+\b")


@dataclass
class Issue:
    skill: str
    kind: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"skill": self.skill, "type": self.kind, "message": self.message}

    def __str__(self) -> str:
        return f"{self.skill} [{self.kind}] {self.message}"


def parse_frontmatter(text: str) -> tuple[dict, list[str]]:
    """Parse a YAML-subset frontmatter block into fields and body lines."""
    fields: dict[str, str] = {}
    errors: list[str] = []

    if not text.startswith("---"):
        errors.append("missing frontmatter delimiters (must start with ---)")
        return fields, errors

    lines = text.splitlines()
    if len(lines) < 2 or not lines[1].strip():
        errors.append("empty frontmatter block")
        return fields, errors

    in_block = False
    block_key: str | None = None
    block_lines: list[str] = []

    for raw in lines[1:]:
        line = raw.rstrip()
        if line.strip() == "---" and not in_block:
            break
        if in_block:
            if line.startswith((" ", "\t")) or not line.strip():
                block_lines.append(line)
                continue
            fields[block_key] = "\n".join(block_lines).strip()
            in_block = False
            block_key = None
        if not in_block and line.strip() and not line.startswith("#"):
            m = FIELD_RE.match(line)
            if not m:
                errors.append(f"unparsable frontmatter line: {line!r}")
                continue
            key, value = m.group(1), m.group(2).strip()
            if value in ("|", "|-", ">"):
                in_block = True
                block_key = key
                block_lines = []
                continue
            fields[key] = value.strip('"')
    if in_block:
        fields[block_key] = "\n".join(block_lines).strip()

    return fields, errors


def parse_list(value: str) -> list[str] | None:
    """Parse a YAML inline list like '[a, b]' or a block of '- item' lines."""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"') for item in inner.split(",") if item.strip()]
    if "- " in value:
        return [ln.split("- ", 1)[1].strip() for ln in value.splitlines() if ln.strip().startswith("- ")]
    return None


def collect_references(body: str) -> list[str]:
    """Collect relative file references from backticks, links, and code fences."""
    refs: list[str] = list(REF_INLINE.findall(body)) + list(REF_LINK.findall(body))

    for fence in FENCE_RE.split(body)[1::2]:
        refs.extend(REF_FENCE_PATH.findall(fence))

    cleaned: list[str] = []
    for ref in refs:
        if "#" in ref:
            ref = ref.split("#", 1)[0]
        ref = ref.strip()
        if (
            ref
            and "/" in ref
            and not ref.startswith(("http://", "https://", "mailto:", "{{", "SKILL"))
            and not ref.endswith((".md",))
            and not ref.startswith(("#", "/", "~"))
        ):
            cleaned.append(ref)
    return cleaned


def validate_skill(skill_dir: Path) -> list[Issue]:
    """Validate a single Agent Skill directory."""
    issues: list[Issue] = []
    name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        issues.append(Issue(name, "missing", "no SKILL.md found in skill directory"))
        return issues

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    frontmatter, parse_errors = parse_frontmatter(text)

    for msg in parse_errors:
        issues.append(Issue(name, "frontmatter", msg))

    for field in REQUIRED_FIELDS:
        if field not in frontmatter:
            issues.append(Issue(name, "missing-field", f"missing required frontmatter field: {field}"))

    if "name" in frontmatter:
        if not SLUG_RE.match(frontmatter["name"]):
            issues.append(
                Issue(name, "invalid-name", f"name {frontmatter['name']!r} is not a valid slug (lowercase, hyphens)")
            )
        elif frontmatter["name"] != name:
            issues.append(
                Issue(name, "name-mismatch", f"frontmatter name {frontmatter['name']!r} != directory name {name!r}")
            )

    if "description" in frontmatter:
        desc = frontmatter["description"].strip()
        if len(desc) < 20:
            issues.append(Issue(name, "weak-description", "description is empty or too short (<20 chars)"))

    for field in LIST_FIELDS:
        if field in frontmatter:
            parsed = parse_list(frontmatter[field])
            if parsed is None or any(not isinstance(p, str) or not p for p in parsed):
                issues.append(Issue(name, "invalid-field", f"{field} must be a list of strings"))

    if "license" in frontmatter and not isinstance(frontmatter["license"], str):
        issues.append(Issue(name, "invalid-field", "license must be a string"))

    body = text
    if "---" in text:
        body = text.split("---", 2)[-1] if text.count("---") >= 2 else ""

    for ref in collect_references(body):
        if not (skill_dir / ref).exists():
            issues.append(Issue(name, "broken-reference", f"referenced file missing: {ref}"))

    return issues


def scan_skills(root: Path, paths: list[str]) -> list[Issue]:
    """Scan directories for SKILL.md, validating each containing directory."""
    all_issues: list[Issue] = []
    seen: set[Path] = set()

    targets = [Path(p).resolve() for p in paths] if paths else [root]
    for target in targets:
        if target.is_file():
            if target.name == "SKILL.md":
                candidate = target.parent
                if candidate not in seen:
                    seen.add(candidate)
                    all_issues.extend(validate_skill(candidate))
            continue
        for skill_md in target.rglob("SKILL.md"):
            candidate = skill_md.parent
            if candidate in seen:
                continue
            seen.add(candidate)
            all_issues.extend(validate_skill(candidate))

    return all_issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="skillcheck",
        description="Validate Agent Skills (SKILL.md) directories.",
    )
    parser.add_argument("paths", nargs="*", help="skill directories or search roots (default: cwd)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--version", action="version", version=f"skillcheck {__version__}")
    args = parser.parse_args(argv)

    issues = scan_skills(Path.cwd(), args.paths)

    if args.json:
        import json

        print(json.dumps([i.to_dict() for i in issues], indent=2))
    else:
        if issues:
            for issue in issues:
                print(str(issue))
        else:
            print("All skills OK")

    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
