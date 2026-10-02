from __future__ import annotations

from unittest.mock import MagicMock, patch

from mind.logic.engines.artifact_gate import ArtifactGateEngine


# ID: 5ee43043-5368-42ab-8d61-c1ee5627239a
async def test_ArtifactGateEngine_verify_context() -> None:
    engine = MagicMock(spec=ArtifactGateEngine)
    engine.engine_id = "artifact_gate"

    context = MagicMock()
    context.repo_path = "/tmp/repo"

    params = {"check_type": "vocabulary_projection_consistency"}

    fake_findings = [MagicMock()]

    # ID: 539e8546-039f-4b93-a943-a2203ce73a42
    def fake_check(repo_root, check_type):
        return MagicMock()

    with (
        patch(
            "mind.logic.engines.artifact_gate._VOCAB_DISPATCH",
            {"vocabulary_projection_consistency": fake_check},
        ),
        patch(
            "mind.logic.engines.artifact_gate._result_to_findings",
            return_value=fake_findings,
        ) as mock_result_to_findings,
    ):
        result = await ArtifactGateEngine.verify_context(engine, context, params)

    assert result is fake_findings
    mock_result_to_findings.assert_called_once()
    called_args = mock_result_to_findings.call_args
    assert called_args.args[1] == "vocabulary_projection_consistency"
    assert called_args.args[2] == "artifact_gate"


from pathlib import Path

import pytest


@pytest.mark.asyncio
# ID: 5c0bfd62-a84e-418d-a288-22b82e66536f
async def test_artifact_gate_engine_verify(tmp_path: Path) -> None:
    engine = ArtifactGateEngine()

    manifest = tmp_path / "model.yaml"
    manifest.write_text("role: planner\n", encoding="utf-8")

    expected = MagicMock()
    engine._check_role_abstraction = MagicMock(return_value=expected)

    result = await engine.verify(manifest, {"check_type": "role_abstraction"})

    engine._check_role_abstraction.assert_called_once()
    call_args = engine._check_role_abstraction.call_args
    assert call_args[0][0] == manifest
    assert call_args[0][1] == {"role": "planner"}
    assert result is expected


# ID: 9b615a1b-da7c-4897-a013-d66ebc8a1275
def test_ArtifactGateEngine_is_context_level_for():
    # None -> False (per ADR-076 D1/D2/D3)
    assert ArtifactGateEngine.is_context_level_for(None) is False

    # Vocabulary check types -> True
    for check_type in (
        "vocabulary_projection_consistency",
        "vocabulary_canonical_format",
        "vocabulary_authoritative_paths",
        "register_casing_validation",
    ):
        assert ArtifactGateEngine.is_context_level_for(check_type) is True

    # Governance check types -> True
    for check_type in (
        "all_rules_mapped",
        "active_routing_claimed_by_action",
        "namespace_has_drainer",
        "namespace_manifest_completeness",
        "fs_operations_completeness",
    ):
        assert ArtifactGateEngine.is_context_level_for(check_type) is True

    # PromptModel / per-file check types -> False
    for check_type in (
        "required_fields",
        "no_provider_leak",
        "role_abstraction",
        "governed_prompt_has_anchor",
    ):
        assert ArtifactGateEngine.is_context_level_for(check_type) is False

    # Unknown check type -> False
    assert ArtifactGateEngine.is_context_level_for("unknown_check_type") is False





# ID: 97385fd3-710a-4150-af9a-bf42889ef33a
def test_ArtifactGateEngine(tmp_path: Path) -> None:
    manifest = tmp_path / "model.yaml"
    manifest.write_text(
        "id: my_prompt\n"
        "version: '1.0'\n"
        "role: analyst\n"
        "success_criteria:\n"
        "  - does the thing\n"
        "input:\n"
        "  required:\n"
        "    - question\n"
        "output:\n"
        "  format: markdown\n",
        encoding="utf-8",
    )

    engine = ArtifactGateEngine()
    with patch(
        "mind.logic.engines.artifact_gate.load_cognitive_roles",
        return_value={"analyst"},
    ):
        result = __import__("asyncio").run(
            engine.verify(manifest, {"check_type": "required_fields"})
        )

    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == "artifact_gate"
