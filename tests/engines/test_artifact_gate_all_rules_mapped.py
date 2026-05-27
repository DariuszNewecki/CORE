"""Fixture tests for ArtifactGateEngine all_rules_mapped check_type.

Builds a minimal repo under tmp_path with .intent/rules/ and
.intent/enforcement/remediation/auto_remediation.yaml, then exercises
the engine end-to-end via verify(). Pure file-system checks — no DB.

See ADR-066 for the invariant under test.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mind.logic.engines.artifact_gate import ArtifactGateEngine


def _build_repo(
    tmp_path: Path,
    rule_documents: dict[str, dict],
    mapped_rule_ids: list[str],
) -> Path:
    """Construct a minimal .intent/ tree for testing.

    rule_documents: {relative_path: rule_document_dict}
    mapped_rule_ids: rule ids to write into auto_remediation.yaml
    """
    intent = tmp_path / ".intent"
    (intent / "rules").mkdir(parents=True)
    (intent / "enforcement" / "remediation").mkdir(parents=True)
    (tmp_path / ".specs").mkdir()

    for rel, doc in rule_documents.items():
        target = intent / "rules" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    body = ["mappings:"]
    for rid in mapped_rule_ids:
        body.append(f"  {rid}:")
        body.append("    action: fix.modularity")
        body.append("    status: DELEGATE")
    (intent / "enforcement" / "remediation" / "auto_remediation.yaml").write_text(
        "\n".join(body) + "\n", encoding="utf-8"
    )
    return tmp_path


def _verify(repo_root: Path) -> object:
    """Invoke the all_rules_mapped check via the engine entry point."""
    engine = ArtifactGateEngine()
    target = (
        repo_root / ".intent" / "enforcement" / "remediation" / "auto_remediation.yaml"
    )
    return asyncio.run(engine.verify(target, {"check_type": "all_rules_mapped"}))


def _doc(rule_id: str, enforcement: str = "reporting", status: str = "active") -> dict:
    return {
        "metadata": {
            "id": f"rules.test.{rule_id.replace('.', '_')}",
            "status": status,
        },
        "rules": [
            {
                "id": rule_id,
                "statement": "test rule",
                "enforcement": enforcement,
                "authority": "policy",
                "phase": "audit",
            }
        ],
    }


def test_all_mapped_passes(tmp_path: Path) -> None:
    repo = _build_repo(
        tmp_path,
        rule_documents={"a.json": _doc("test.alpha")},
        mapped_rule_ids=["test.alpha"],
    )
    result = _verify(repo)
    assert result.ok, f"expected pass, got violations: {result.violations}"


def test_unmapped_reporting_rule_fails(tmp_path: Path) -> None:
    repo = _build_repo(
        tmp_path,
        rule_documents={"a.json": _doc("test.alpha"), "b.json": _doc("test.beta")},
        mapped_rule_ids=["test.alpha"],
    )
    result = _verify(repo)
    assert not result.ok
    assert any("test.beta" in v for v in result.violations)
    assert not any("test.alpha" in v for v in result.violations)


def test_blocking_rule_excluded_from_scope(tmp_path: Path) -> None:
    repo = _build_repo(
        tmp_path,
        rule_documents={"a.json": _doc("test.blocker", enforcement="blocking")},
        mapped_rule_ids=[],
    )
    result = _verify(repo)
    assert result.ok, "blocking rules should not require an entry"


def test_advisory_rule_excluded_from_scope(tmp_path: Path) -> None:
    repo = _build_repo(
        tmp_path,
        rule_documents={"a.json": _doc("test.advisor", enforcement="advisory")},
        mapped_rule_ids=[],
    )
    result = _verify(repo)
    assert result.ok


def test_inactive_document_excluded_from_scope(tmp_path: Path) -> None:
    repo = _build_repo(
        tmp_path,
        rule_documents={"a.json": _doc("test.dormant", status="draft")},
        mapped_rule_ids=[],
    )
    result = _verify(repo)
    assert result.ok


def test_multiple_unmapped_all_reported(tmp_path: Path) -> None:
    repo = _build_repo(
        tmp_path,
        rule_documents={
            "a.json": _doc("test.alpha"),
            "b.json": _doc("test.beta"),
            "c.json": _doc("test.gamma"),
        },
        mapped_rule_ids=[],
    )
    result = _verify(repo)
    assert not result.ok
    assert len(result.violations) == 3
    joined = " ".join(result.violations)
    for rid in ("test.alpha", "test.beta", "test.gamma"):
        assert rid in joined


def test_malformed_rule_document_skipped(tmp_path: Path) -> None:
    """A broken JSON file is a separate failure mode — not this check's concern."""
    repo = _build_repo(
        tmp_path,
        rule_documents={"good.json": _doc("test.alpha")},
        mapped_rule_ids=["test.alpha"],
    )
    # Write a malformed JSON file alongside the good one
    (repo / ".intent" / "rules" / "broken.json").write_text(
        "{ this is not json", encoding="utf-8"
    )
    result = _verify(repo)
    assert result.ok, f"malformed file should not block the check: {result.violations}"


def test_missing_map_file_returns_config_error(tmp_path: Path) -> None:
    intent = tmp_path / ".intent"
    (intent / "rules").mkdir(parents=True)
    (tmp_path / ".specs").mkdir()
    (intent / "rules" / "a.json").write_text(
        json.dumps(_doc("test.alpha")), encoding="utf-8"
    )
    # auto_remediation.yaml deliberately absent
    engine = ArtifactGateEngine()
    target = intent / "enforcement" / "remediation" / "auto_remediation.yaml"
    result = asyncio.run(engine.verify(target, {"check_type": "all_rules_mapped"}))
    assert not result.ok
    # Either file-not-found (handled by engine before dispatch) or config error
    assert (
        "not found" in " ".join(result.violations).lower()
        or "missing" in result.message.lower()
    )
