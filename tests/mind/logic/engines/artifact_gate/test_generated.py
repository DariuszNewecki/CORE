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
