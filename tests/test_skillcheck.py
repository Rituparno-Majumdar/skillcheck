from pathlib import Path

from skillcheck.cli import (
    collect_references,
    parse_frontmatter,
    parse_list,
    scan_skills,
    validate_skill,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_skill_passes():
    issues = validate_skill(FIXTURES / "valid-skill")
    assert issues == []


def test_missing_skill_md():
    issues = validate_skill(FIXTURES / "not-a-skill")
    assert any(i.kind == "missing" for i in issues)


def test_invalid_skill_reports_issues():
    issues = validate_skill(FIXTURES / "invalid-skill")
    kinds = {i.kind for i in issues}
    assert "invalid-name" in kinds
    assert "invalid-field" in kinds


def test_weak_description():
    issues = validate_skill(FIXTURES / "invalid-skill")
    assert any(i.kind == "weak-description" for i in issues)


def test_broken_reference():
    issues = validate_skill(FIXTURES / "broken-ref-skill")
    assert any(i.kind == "broken-reference" for i in issues)


def test_scan_skills_finds_all():
    issues = scan_skills(FIXTURES, [])
    found = {i.skill for i in issues}
    assert "valid-skill" not in found
    assert "invalid-skill" in found
    assert "broken-ref-skill" in found


def test_parse_frontmatter_block():
    text = "---\nname: foo\n---\nbody"
    fields, errors = parse_frontmatter(text)
    assert errors == []
    assert fields["name"] == "foo"


def test_parse_list_inline():
    assert parse_list("[a, b, c]") == ["a", "b", "c"]


def test_parse_list_block():
    assert parse_list("- a\n- b") == ["a", "b"]


def test_collect_references_ignores_links():
    body = "See `scripts/run.sh` and [docs](../x.md) and https://example.com"
    refs = collect_references(body)
    assert "scripts/run.sh" in refs
    assert not any(r.startswith("http") for r in refs)


def test_main_exit_codes(capsys):
    from skillcheck.cli import main

    assert main([str(FIXTURES), "--json"]) == 1
    assert main([str(FIXTURES / "valid-skill")]) == 0
