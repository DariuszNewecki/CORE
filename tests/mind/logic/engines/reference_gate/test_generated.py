from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mind.logic.engines.reference_gate import find_dangling_references


# ID: 8995ebd2-090e-45dc-8b3b-fa3dee0d3efe
def test_find_dangling_references(tmp_path: Path) -> None:
    repo_root = tmp_path

    with (
        patch("mind.logic.engines.reference_gate.IntentRepository") as mock_repo,
        patch("mind.logic.engines.reference_gate.intent_root_for") as mock_intent_root,
        patch("mind.logic.engines.reference_gate._flow_action_refs") as mock_flow,
        patch("mind.logic.engines.reference_gate._test_coverage_files") as mock_tests,
        patch(
            "mind.logic.engines.reference_gate._mapping_entry_points"
        ) as mock_mapping,
        patch(
            "mind.logic.engines.reference_gate._worker_implementations"
        ) as mock_workers,
        patch("mind.logic.engines.reference_gate._namespace_manifest_paths") as mock_ns,
        patch(
            "mind.logic.engines.reference_gate._remediation_targets"
        ) as mock_remediation,
    ):
        mock_intent_root.return_value = tmp_path / ".intent"
        mock_repo.return_value = MagicMock()

        declaring = repo_root / ".intent" / "flows" / "flow.yaml"

        mock_flow.return_value = [
            (declaring, "action", "ghost_action", "does not exist"),
        ]
        mock_tests.return_value = []
        mock_mapping.return_value = []
        mock_workers.return_value = []
        mock_ns.return_value = []
        mock_remediation.return_value = []

        findings = find_dangling_references(repo_root)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == "architecture.intent.references_resolve"
    assert finding.file_path == ".intent/flows/flow.yaml"
    assert finding.context == {"field": "action", "reference": "ghost_action"}

    mock_repo.assert_called_once_with(root=tmp_path / ".intent", strict=False)
    mock_flow.assert_called_once()
    mock_tests.assert_called_once()
    mock_mapping.assert_called_once()
    mock_workers.assert_called_once()
    mock_ns.assert_called_once()
    mock_remediation.assert_called_once()


from mind.logic.engines.reference_gate import ReferenceGateEngine


# ID: b81943fe-b18d-47cc-925d-b030c8606fc5
async def test_ReferenceGateEngine_verify_context() -> None:
    engine = ReferenceGateEngine(path_resolver=MagicMock())

    mock_context = MagicMock()
    mock_context.repo_path = "/some/repo/path"

    mock_findings = [MagicMock(), MagicMock()]

    with patch(
        "mind.logic.engines.reference_gate.find_dangling_references",
        return_value=mock_findings,
    ) as mock_find:
        params = {"check_type": "intent_references_resolve"}

        result = await engine.verify_context(mock_context, params)

    mock_find.assert_called_once()
    called_path = mock_find.call_args[0][0]
    assert str(called_path) == "/some/repo/path"
    assert result is mock_findings


import asyncio


# ID: 37aa78fd-1c19-41f7-a960-86cb02331dad
def test_ReferenceGateEngine_verify() -> None:
    path_resolver = MagicMock()
    engine = ReferenceGateEngine(path_resolver)

    file_path = Path("/tmp/some_file.py")
    params = {"check_type": "context_level_check"}

    result = asyncio.run(engine.verify(file_path, params))

    assert result.ok is False
    assert "context_level_check" in result.message
    assert "verify_context" in result.message
    assert result.violations == []
    assert result.engine_id == engine.engine_id



import pytest


@pytest.mark.asyncio
# ID: a7f15ae5-913f-46c9-917e-ca4e41a0a5b4
async def test_ReferenceGateEngine() -> None:
    path_resolver = MagicMock()
    engine = ReferenceGateEngine(path_resolver)

    # verify() reports that per-file dispatch is a mis-mapping.
    params = {"check_type": "intent_references_resolve"}
    result = await engine.verify(Path("/repo/.intent/foo.md"), params)
    assert result.ok is False
    assert result.engine_id == engine.engine_id
    assert result.violations == []

    # verify_context() delegates to find_dangling_references for the valid check.
    context = MagicMock()
    context.repo_path = "/repo"
    fake_findings = [MagicMock()]
    with patch(
        "mind.logic.engines.reference_gate.find_dangling_references",
        return_value=fake_findings,
    ) as mock_find:
        findings = await engine.verify_context(context, params)

    mock_find.assert_called_once_with(Path("/repo"))
    assert findings == fake_findings

    # Unknown check_type yields a single BLOCK finding.
    unknown_params = {"check_type": "bogus"}
    with patch(
        "mind.logic.engines.reference_gate.find_dangling_references"
    ) as mock_find2:
        unknown_findings = await engine.verify_context(context, unknown_params)

    mock_find2.assert_not_called()
    assert len(unknown_findings) == 1
    assert unknown_findings[0].check_id == "reference_gate.unknown_check_type"
