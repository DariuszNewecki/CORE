from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


# ID: 63a412c6-df74-4402-ac59-07151d8e43a2
def test_execute_approved_clusters():
    from will.agents.strategic_auditor.effects import execute_approved_clusters

    child_id = uuid4()
    child = MagicMock()
    child.id = child_id
    child.assigned_role = "AutonomousDeveloper"
    child.status = "pending"
    child.requires_approval = False
    child.intent = "Add feature X"
    child.context = {"workflow_type": "full_feature_development", "affected_files": []}

    repo = MagicMock()
    repo.list_children = AsyncMock(return_value=[child])
    repo.update_status = AsyncMock()

    ctx = MagicMock()
    ctx.git_service.repo_path = "/tmp/repo"

    session = MagicMock()

    with (
        patch(
            "will.agents.strategic_auditor.effects.TaskRepository", return_value=repo
        ),
        patch(
            "will.autonomy.autonomous_developer.develop_from_goal",
            new=AsyncMock(return_value=(True, "done")),
        ) as mock_dev,
        patch("will.agents.strategic_auditor.effects.Path"),
    ):
        import asyncio

        results = asyncio.get_event_loop().run_until_complete(
            execute_approved_clusters(ctx, session, uuid4())
        )

    assert results == [(str(child_id), True, "done")]
    mock_dev.assert_awaited_once()
    _, kwargs = mock_dev.call_args
    assert kwargs["workflow_type"] == "code_modification"
    assert kwargs["write"] is True
    repo.update_status.assert_awaited_once_with(child_id, "completed")
