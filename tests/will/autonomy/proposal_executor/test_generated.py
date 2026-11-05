from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.proposal_executor import ProposalExecutor


# ID: eef2b050-7a23-44af-91a3-99901ec88c6e
async def test_ProposalExecutor_execute():
    core_context = MagicMock()
    core_context.git_service.repo_path = "/tmp/repo"
    core_context.file_handler = MagicMock()

    with patch(
        "will.autonomy.proposal_executor.ActionExecutor",
        return_value=MagicMock(),
    ):
        executor = ProposalExecutor(core_context)

    claimed_by = MagicMock()
    expected_result = {"status": "ok", "proposal_id": "prop-1"}

    lock_cm = MagicMock()
    lock_cm.__aenter__ = AsyncMock(return_value=None)
    lock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_lock = MagicMock(return_value=lock_cm)

    with (
        patch(
            "will.autonomy.proposal_executor.async_repo_lock",
            mock_lock,
        ),
        patch.object(
            executor,
            "_execute",
            new=AsyncMock(return_value=expected_result),
        ) as mock_execute,
    ):
        result = await executor.execute("prop-1", claimed_by, write=True)

    assert result == expected_result
    mock_execute.assert_awaited_once_with("prop-1", claimed_by, True)
    mock_lock.assert_called_once_with("/tmp/repo", core_context.file_handler)
