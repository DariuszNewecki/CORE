from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ID: 9bd5e011-9973-4207-b4d5-ea136a897fe6
def test_check_audited_commit():
    from will.audit_violation.staleness import check_audited_commit

    audited = MagicMock()
    audited.behind = True
    audited.audited = "abc123"
    audited.upstream = "def456"

    git_service = MagicMock()
    core_context = MagicMock()
    core_context.git_service = git_service
    blackboard = MagicMock()
    core_context.registry.get_blackboard_service = AsyncMock(return_value=blackboard)

    worker = MagicMock()

    with (
        patch(
            "will.audit_violation.staleness.audited_commit", return_value=audited
        ) as mock_audited_commit,
        patch(
            "body.infrastructure.repo_sync.upstream_branch", return_value="origin/main"
        ),
        patch(
            "will.audit_violation.staleness.guard_stale_audit", new_callable=AsyncMock
        ) as mock_guard,
    ):
        result_audited, result_behind = asyncio.run(
            check_audited_commit(worker, core_context, behind_cycles=2)
        )

    assert result_audited is audited
    assert result_behind == 3
    mock_audited_commit.assert_called_once_with(git_service, "origin/main")
    core_context.registry.get_blackboard_service.assert_awaited_once()
    mock_guard.assert_awaited_once_with(worker, blackboard, audited, 3)
