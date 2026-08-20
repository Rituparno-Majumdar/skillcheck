# skillcheck

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![CLI](https://img.shields.io/badge/CLI-ready-2ea043?style=for-the-badge)
![Zero Dependencies](https://img.shields.io/badge/Dependencies-0-4c1d95?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)
![PyPI](https://img.shields.io/pypi/v/skillcheck?style=for-the-badge&logo=pypi&logoColor=white&color=3776AB)

</div>


**Validate Agent Skills (SKILL.md) directories** — catch missing fields, malformed frontmatter, and broken file references before your agent silently loses a skill.

```bash
pip install skillcheck
skillcheck ./
```

## The Problem

Agent Skills are the fastest-growing way to give AI agents durable capability. A skill is a directory with a `SKILL.md` containing YAML frontmatter:

```markdown
---
name: my-skill
description: What this skill does and when to use it
allowed-tools: [bash, webfetch]
---

Use `scripts/run.sh` to do the thing.
```

But they're **hand-written markdown with hand-written YAML** — and a single mistake silently breaks the skill. There is no runtime error: the agent just never loads it, and you don't find out until the skill is needed in production.

Existing tools validate MCP server configs, JSON schemas, and markdown structure — **nobody validates the Agent Skill directory itself**.

## What it checks

| Check | Why it matters |
| :--- | :--- |
| `SKILL.md` exists | A skill directory without it is invisible to the agent |
| `name` present & valid slug | Loaders reject non-slug names; `name` must also match the directory name |
| `description` present & ≥20 chars | Empty descriptions make the skill unfindable by the agent's tool-selection |
| `allowed-tools` is a string list | Wrong type silently drops tool permissions |
| `license` is a string | Malformed license blocks ingestion |
| Referenced files exist | A missing `scripts/run.sh` means the skill runs but fails at the worst moment |
| Frontmatter parses | A broken `---` block makes the whole file unreadable |

## Usage

```bash
# Scan the current directory (recursively)
skillcheck

# Scan specific skill directories or search roots
skillcheck ~/.claude/skills ./my-skills

# Machine-readable output for CI
skillcheck --json

# Validate a single SKILL.md file directly
skillcheck path/to/SKILL.md
```

**Exit codes**: `0` = all skills OK, `1` = one or more issues found.

## Example

```bash
$ skillcheck ~/.claude/skills
~/.claude/skills/valid-skill OK
~/.claude/skills/broken-skill [missing-field] missing required frontmatter field: description
~/.claude/skills/broken-skill [broken-reference] referenced file missing: scripts/run.sh
```

## Why you should care

The 2026 agentic era runs on skills — Claude Code, opencode, and every major agent framework load them from directories. `skillcheck` is the **zero-dependency lint pass** for those directories: run it in CI before you ship a skill pack, or ad-hoc whenever you hand-edit a `SKILL.md`.

## Requirements

- Python 3.10+
- **Zero external dependencies**

## Install

```bash
# From PyPI (once published)
pip install skillcheck

# Or directly from source
git clone https://github.com/Rituparno-Majumdar/skillcheck
cd skillcheck
pip install -e .
```

## Development

```bash
pip install -e .[dev]
ruff check src/ tests/
bandit -r src/
pytest tests/ -v
```

## License

MIT — free to use, modify, and distribute.