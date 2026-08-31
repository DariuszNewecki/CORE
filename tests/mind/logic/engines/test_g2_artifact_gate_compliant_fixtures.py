# tests/mind/logic/engines/test_g2_artifact_gate_compliant_fixtures.py

"""#842 Unit G: artifact_gate compliant-fixture completion.

Five of the eleven artifact_gate blocking rules already had a genuine
violating fixture that exercises the real dispatch path -- planted in
tests/mind/governance/test_adr_076_firing_coverage.py, which drives them
through execute_rule(), the real audit dispatch entry point (not a
mapping-shape check). What was missing was the compliant half: a fixture
proving the same check function returns ok=True for a clean input, so the
registry's "violating AND compliant" pair requirement is satisfied for:

- ai.prompt.artifact.required_fields       -> _check_required_fields
- ai.prompt.artifact.no_provider_leak      -> _check_no_provider_leak
- ai.prompt.artifact.role_abstraction      -> _check_role_abstraction
- governance.namespace.classification_complete -> _check_namespace_manifest_completeness
- governance.quarantine.namespace_has_drainer  -> _check_namespace_has_drainer

Each test below calls the real module-level check function directly (the
same symbol test_adr_076_firing_coverage.py's violating fixtures dispatch
into via ArtifactGateEngine.verify/verify_context), with an isolated
tmp_path tree standing in for repository structure where the check walks
directory content (namespace_manifest_completeness, namespace_has_drainer).

The other six artifact_gate rules (governed_prompt_must_have_anchor,
remediation.active_routing_claimed_by_action, remediation.all_rules_mapped,
and the three vocabulary.* rules) already have complete violating+compliant
pairs in dedicated test files -- test_artifact_gate__governed_prompt_has_anchor.py,
test_artifact_gate__active_routing_claimed_by_action.py,
test_artifact_gate_all_rules_mapped.py, test_artifact_gate_vocabulary.py --
and are cited from those files directly in the registry, not duplicated here.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import yaml

from mind.logic.engines.artifact_gate import (
    ArtifactGateEngine,
    _check_namespace_has_drainer,
    _check_namespace_manifest_completeness,
)


_COMPLIANT_MANIFEST = {
    "id": "x",
    "version": "1.0",
    "role": "Architect",
    "success_criteria": ["ok"],
    "input": {"required": ["q"]},
    "output": {"format": "text"},
}


# ---------------------------------------------------------------------------
# ai.prompt.artifact.required_fields -- compliant half
# ---------------------------------------------------------------------------


def test_required_fields_passes_for_complete_manifest() -> None:
    engine = ArtifactGateEngine()
    result = engine._check_required_fields(Path("model.yaml"), _COMPLIANT_MANIFEST)
    assert result.ok is True
    assert result.violations == []


# ---------------------------------------------------------------------------
# ai.prompt.artifact.no_provider_leak -- compliant half
# ---------------------------------------------------------------------------


def test_no_provider_leak_passes_for_capability_class_preference() -> None:
    manifest = {**_COMPLIANT_MANIFEST, "model": {"preference": "local"}}
    engine = ArtifactGateEngine()
    result = engine._check_no_provider_leak(Path("model.yaml"), manifest)
    assert result.ok is True
    assert result.violations == []


# ---------------------------------------------------------------------------
# ai.prompt.artifact.role_abstraction -- compliant half
# ---------------------------------------------------------------------------


def test_role_abstraction_passes_for_declared_cognitive_role() -> None:
    """'Architect' is declared in .intent/taxonomies/cognitive_roles.yaml."""
    engine = ArtifactGateEngine()
    result = engine._check_role_abstraction(Path("model.yaml"), _COMPLIANT_MANIFEST)
    assert result.ok is True
    assert result.violations == []


# ---------------------------------------------------------------------------
# governance.namespace.classification_complete -- compliant half
# ---------------------------------------------------------------------------


def test_namespace_manifest_completeness_passes_when_every_file_classified(
    tmp_path: Path,
) -> None:
    repo = tmp_path
    (repo / ".intent" / "governance").mkdir(parents=True)
    (repo / ".intent" / "rules").mkdir(parents=True)
    (repo / ".specs").mkdir()

    rule_doc = repo / ".intent" / "rules" / "a.json"
    rule_doc.write_text("{}", encoding="utf-8")
    manifest_path = repo / ".intent" / "governance" / "namespace_manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "classifications": [
                    {"path": str(rule_doc.relative_to(repo))},
                    {"path": str(manifest_path.relative_to(repo))},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = _check_namespace_manifest_completeness(
        repo, "namespace_manifest_completeness"
    )
    assert result.ok is True
    assert result.violations == []


# ---------------------------------------------------------------------------
# governance.quarantine.namespace_has_drainer -- compliant half
# ---------------------------------------------------------------------------


async def test_namespace_has_drainer_passes_when_namespace_registered(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path
    (repo / ".intent" / "enforcement" / "quarantine").mkdir(parents=True)
    (repo / ".specs").mkdir()
    registry_path = (
        repo / ".intent" / "enforcement" / "quarantine" / "drainer_registry.yaml"
    )
    registry_path.write_text(
        yaml.safe_dump({"namespaces": [{"prefix": "audit"}]}), encoding="utf-8"
    )

    fake_repo = MagicMock()
    fake_repo.resolve_rel = MagicMock(return_value=Path("dummy"))
    fake_repo.load_document = MagicMock(return_value={"namespaces": [{"prefix": "audit"}]})

    from mind.logic.engines import artifact_gate as agate

    monkeypatch.setattr(agate, "get_intent_repository", lambda: fake_repo)

    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=[("audit",)])
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await _check_namespace_has_drainer(
        repo,
        "namespace_has_drainer",
        {"_context": MagicMock(db_session=mock_session)},
    )
    assert result.ok is True
    assert result.violations == []
