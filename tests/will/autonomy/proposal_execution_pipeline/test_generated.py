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


from unittest.mock import AsyncMock

import pytest

from will.autonomy.proposal_execution_pipeline import resolve_deferred_findings


@pytest.mark.asyncio
# ID: aa626ee3-65b3-4169-99b3-fdb180480ab2
async def test_resolve_deferred_findings():
    mock_bb_service = AsyncMock()
    mock_bb_service.resolve_deferred_entries_for_completed_proposal = AsyncMock(
        return_value={"resolved_count": 3}
    )

    with patch(
        "body.services.service_registry.service_registry.get_blackboard_service",
        new=AsyncMock(return_value=mock_bb_service),
    ):
        result = await resolve_deferred_findings("prop-123")

    assert result is True
    mock_bb_service.resolve_deferred_entries_for_completed_proposal.assert_awaited_once_with(
        "prop-123"
    )



from will.autonomy.proposal_execution_pipeline import capture_git_sha


# ID: 34eb9510-319c-479e-bbf6-f5980cddfb42
def test_capture_git_sha():
    git_service = MagicMock()
    git_service.get_current_commit.return_value = "abc123def456"

    result = capture_git_sha(git_service, phase="pre", proposal_id="prop-1")

    assert result == "abc123def456"
    git_service.get_current_commit.assert_called_once_with()
