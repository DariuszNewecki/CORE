# tests/mind/logic/engines/test_taxonomy_gate__action_support.py
"""ADR-121 D5 / ADR-092-A — TaxonomyGateEngine action_supported_by_declaration tests.

Tests 5-6 from the ADR-121 verification matrix:
  5. Symmetric authored ↔ introspected sets → no finding.
  6. Asymmetry in either direction → one finding per mismatched pair.

Both tests mock get_intent_repository() to inject controlled artifact types and
write a minimal action_risk.yaml under tmp_path — no real IntentRepository disk
bootstrap required.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

from mind.logic.engines.taxonomy_gate import TaxonomyGateEngine
from shared.infrastructure.intent.intent_repository import ArtifactTypeRef
from shared.path_resolver import PathResolver


_ACTION_SUPPORT_CHECK = "action_supported_by_declaration"


# ── Helpers ───────────────────────────────────────────────────────────────────


# ID: 558946e8-9853-4af5-a0c1-1f924498a543
def _fake_context(repo_root: Path) -> SimpleNamespace:
    return SimpleNamespace(repo_path=repo_root)


# ID: d5f9c88b-3867-40a6-b83e-f55868f21a8e
def _engine(repo: Path) -> TaxonomyGateEngine:
    return TaxonomyGateEngine(path_resolver=PathResolver(repo_root=repo))


# ID: 5ecb4d41-7da5-45ee-854f-b252957b36de
def _make_type_ref(type_id: str, supported_actions: list[str]) -> ArtifactTypeRef:
    return ArtifactTypeRef(
        id=type_id,
        path=Path(f".intent/artifact_types/{type_id}.yaml"),
        content={"id": type_id, "supported_actions": supported_actions},
    )


# ID: 416d40bd-cbf5-4624-b082-a77969874fca
def _write_action_risk(repo: Path, entries: dict[str, dict[str, object]]) -> None:
    """Write a minimal action_risk.yaml under .intent/enforcement/config/."""
    config_dir = repo / ".intent" / "enforcement" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "action_risk.yaml").write_text(
        yaml.dump(entries),
        encoding="utf-8",
    )


# ── Test 5: symmetric → no finding ────────────────────────────────────────────


async def test_action_supported_by_declaration_symmetric(tmp_path: Path) -> None:
    """Test 5 (ADR-121): symmetric authored and introspected sets → no findings."""
    _write_action_risk(
        tmp_path,
        {
            "document.run.gap_analysis": {
                "impact_level": "safe",
                "artifact_types": ["document_corpus"],
            },
        },
    )

    mock_repo = MagicMock()
    mock_repo.initialize.return_value = None
    mock_repo.list_artifact_types.return_value = [
        _make_type_ref("document_corpus", ["document.run.gap_analysis"]),
    ]

    with patch(
        "mind.logic.engines.taxonomy_gate.get_intent_repository",
        return_value=mock_repo,
    ):
        findings = await _engine(tmp_path).verify_context(
            _fake_context(tmp_path), {"check_type": _ACTION_SUPPORT_CHECK}
        )

    assert findings == [], f"unexpected findings: {findings}"


# ── Test 6: asymmetric → one finding per mismatch ─────────────────────────────


async def test_action_supported_by_declaration_asymmetric(tmp_path: Path) -> None:
    """Test 6 (ADR-121): action_risk.yaml has artifact_type not in supported_actions → one finding."""
    _write_action_risk(
        tmp_path,
        {
            "document.run.gap_analysis": {
                "impact_level": "safe",
                "artifact_types": ["document_corpus"],
            },
        },
    )

    # artifact type lists NO supported_actions → asymmetry
    mock_repo = MagicMock()
    mock_repo.initialize.return_value = None
    mock_repo.list_artifact_types.return_value = [
        _make_type_ref("document_corpus", []),  # missing document.run.gap_analysis
    ]

    with patch(
        "mind.logic.engines.taxonomy_gate.get_intent_repository",
        return_value=mock_repo,
    ):
        findings = await _engine(tmp_path).verify_context(
            _fake_context(tmp_path), {"check_type": _ACTION_SUPPORT_CHECK}
        )

    assert len(findings) == 1
    f = findings[0]
    assert f.check_id == "governance.taxonomy.action_supported_by_declaration"
    assert "document_corpus" in f.message
    assert "document.run.gap_analysis" in f.message
    assert f.context["artifact_type_id"] == "document_corpus"
    assert f.context["action_id"] == "document.run.gap_analysis"
    assert f.context["direction"] == "introspected_not_authored"
