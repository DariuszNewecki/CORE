from __future__ import annotations

from unittest.mock import MagicMock, patch

from will.autonomy.proposal_execution_pipeline import rollback_proposal


# ID: 871ae9a7-ca53-4eda-9126-cab5a6294595
def test_rollback_proposal():
    git_service = MagicMock()
    git_service.restore_paths = MagicMock(return_value=[])

    action_results = {"paths": ["src/a.py", "src/b.py"]}

    with patch(
        "will.autonomy.proposal_execution_pipeline.compute_production_set",
        return_value=["src/a.py", "src/b.py"],
    ) as mock_compute:
        result = rollback_proposal(
            git_service=git_service,
            proposal_id="prop-123",
            action_results=action_results,
            pre_sha="abcdef1234567890",
        )

    assert result is None
    mock_compute.assert_called_once_with(action_results)
    git_service.restore_paths.assert_called_once_with(
        ["src/a.py", "src/b.py"], source="abcdef1234567890"
    )
