# tests/mind/logic/engines/test_artifact_gate__register_casing.py

"""Fixture pair for governance.vocabulary_registers.operational_fields_must_be_lowercase
(#854, ADR-158).

Closes the #854 gap: the rule's mapping declared engine: python_runtime with
no consumer implemented anywhere -- both this rule and its now-retired
sibling (diagnostic_fields_must_be_uppercase) fired on nothing regardless of
content. Real mechanism: artifact_gate's register_casing_validation
check_type, backed by shared.infrastructure.intent.vocabulary_register_validator
(the same module IntentRepository.__init__ uses as a fail-closed bootstrap
guard -- see that module's docstring).

The path-qualified design (not bare-field-name matching) is the point of
these fixtures: a naive "any key named 'class'/'status'/'authority' must be
lowercase" implementation would false-positive on real, correct content
elsewhere in the live corpus (a worker's `implementation.class:
RepoCrawlerWorker`, a remediation entry's `status: ACTIVE`). Each test below
is grounded in a real occurrence found during #854's corpus inventory, not
invented.
"""

from __future__ import annotations

from pathlib import Path

from mind.logic.engines.artifact_gate import _check_register_casing


def _scaffold_intent(tmp_path: Path, files: dict[str, str]) -> Path:
    """Write files under <tmp_path>/.intent/<rel_path>. Also seeds a minimal
    enums.json with the four ratified definitions so the ratification-guard
    half of the check has something real to read, unless a test overrides it."""
    intent_root = tmp_path / ".intent"
    for rel, content in files.items():
        dest = intent_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    if "META/enums.json" not in files:
        enums_path = intent_root / "META" / "enums.json"
        enums_path.parent.mkdir(parents=True, exist_ok=True)
        enums_path.write_text(
            """\
{
  "definitions": {
    "authority": {"type": "string", "enum": ["meta", "constitution", "policy", "code"]},
    "phase": {"type": "string", "enum": ["interpret", "parse", "load", "audit", "runtime", "execution"]},
    "strength": {"type": "string", "enum": ["blocking", "reporting", "advisory"]},
    "audit_severity": {"type": "string", "enum": ["info", "low", "medium", "high", "block"]}
  }
}
""",
            encoding="utf-8",
        )
    return tmp_path


# ---------------------------------------------------------------------------
# Governed-path field-instance casing
# ---------------------------------------------------------------------------


def test_register_casing_fires_on_uppercase_metadata_authority(tmp_path: Path) -> None:
    """metadata.authority is a real governed path (194 live occurrences,
    #854 corpus inventory). Title-case value must fire."""
    repo = _scaffold_intent(
        tmp_path,
        {
            "rules/example.json": (
                '{"metadata": {"authority": "Policy", "phase": "parse", '
                '"status": "active"}, "rules": []}'
            )
        },
    )
    result = _check_register_casing(repo, "register_casing_validation")

    assert not result.ok
    assert any("metadata.authority" in v for v in result.violations)


def test_register_casing_clean_for_lowercase_metadata_fields(tmp_path: Path) -> None:
    repo = _scaffold_intent(
        tmp_path,
        {
            "rules/example.json": (
                '{"metadata": {"authority": "policy", "phase": "parse", '
                '"status": "active"}, "rules": []}'
            )
        },
    )
    result = _check_register_casing(repo, "register_casing_validation")

    assert result.ok
    assert not result.violations


def test_register_casing_checks_nested_ordering_mode(tmp_path: Path) -> None:
    """ordering.mode (ADR-158 D3) -- nested, not the bare `ordering:` block
    every workflow-stage file actually uses."""
    repo = _scaffold_intent(
        tmp_path,
        {
            "workflows/stages/example.yaml": (
                "phase: parse\nordering:\n  mode: SEQUENTIAL\n  depends_on: []\n"
            )
        },
    )
    result = _check_register_casing(repo, "register_casing_validation")

    assert not result.ok
    assert any("ordering.mode" in v for v in result.violations)


# ---------------------------------------------------------------------------
# Excluded paths must NOT false-positive -- proves path-qualification is
# real, not decorative. Both grounded in actual #854 corpus findings.
# ---------------------------------------------------------------------------


def test_register_casing_ignores_implementation_class(tmp_path: Path) -> None:
    """implementation.class names a Python class (PascalCase, correct);
    identity.class is the real governed operational-register field."""
    repo = _scaffold_intent(
        tmp_path,
        {
            "workers/example.yaml": (
                "identity:\n  class: sensing\n"
                "implementation:\n  module: will.workers.example\n"
                "  class: ExampleWorker\n"
            )
        },
    )
    result = _check_register_casing(repo, "register_casing_validation")

    assert result.ok
    assert not result.violations


def test_register_casing_ignores_remediation_status_vocabulary(tmp_path: Path) -> None:
    """auto_remediation.yaml's mappings.<rule_id>.status carries an unrelated
    ACTIVE/DELEGATE/PENDING routing vocabulary, not the operational register."""
    repo = _scaffold_intent(
        tmp_path,
        {
            "enforcement/remediation/auto_remediation.yaml": (
                "mappings:\n  some.rule.id:\n    action: fix.modularity\n"
                "    status: DELEGATE\n"
            )
        },
    )
    result = _check_register_casing(repo, "register_casing_validation")

    assert result.ok
    assert not result.violations


# ---------------------------------------------------------------------------
# Drift guard -- an occurrence of a watched field name at an unclassified
# path is itself a finding, not a silent pass.
# ---------------------------------------------------------------------------


def test_register_casing_flags_unclassified_occurrence(tmp_path: Path) -> None:
    repo = _scaffold_intent(
        tmp_path,
        {"rules/weird.json": '{"unexpected": {"authority": "policy"}}'},
    )
    result = _check_register_casing(repo, "register_casing_validation")

    assert not result.ok
    assert any("unclassified occurrence" in v for v in result.violations)


# ---------------------------------------------------------------------------
# enums.json ratification guard -- catches a silent revert of the vocabulary
# declaration independent of whether any field currently uses it.
# ---------------------------------------------------------------------------


def test_register_casing_fires_on_reverted_audit_severity_enum(tmp_path: Path) -> None:
    repo = _scaffold_intent(
        tmp_path,
        {
            "META/enums.json": """\
{
  "definitions": {
    "audit_severity": {"type": "string", "enum": ["INFO", "LOW", "MEDIUM", "HIGH", "BLOCK"]}
  }
}
"""
        },
    )
    result = _check_register_casing(repo, "register_casing_validation")

    assert not result.ok
    assert any("audit_severity" in v for v in result.violations)


def test_register_casing_clean_for_ratified_audit_severity_enum(tmp_path: Path) -> None:
    repo = _scaffold_intent(tmp_path, {})  # default seeded enums.json is already lowercase
    result = _check_register_casing(repo, "register_casing_validation")

    assert result.ok
    assert not result.violations
