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
