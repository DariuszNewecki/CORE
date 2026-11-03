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




# ID: 4268886d-d554-4ceb-9f59-938c39e9a06a
async def test_persist_campaign():
    from will.agents.strategic_auditor.effects import persist_campaign

    campaign = MagicMock()
    campaign.campaign_id = "camp-123"
    campaign.system_summary = "A summary of the strategic campaign"
    campaign.total_findings = 5
    campaign.autonomous_task_count = 1
    campaign.escalation_count = 1

    cluster = MagicMock()
    cluster.cluster_id = "cluster-1"
    cluster.proposed_fix = "Fix the bug"
    cluster.root_cause = "Root cause"
    cluster.affected_files = ["a.py"]
    cluster.finding_ids = ["f1"]
    cluster.confidence = 0.9
    cluster.estimated_impact = "high"
    cluster.workflow_type = "auto"

    escalation = MagicMock()
    escalation.cluster_id = "cluster-2"
    escalation.proposed_fix = "Needs amendment"
    escalation.root_cause = "Root cause 2"
    escalation.affected_files = ["b.py"]

    campaign.clusters = [cluster]
    campaign.escalations = [escalation]

    parent_id = uuid4()
    parent_task = MagicMock()
    parent_task.id = parent_id

    child_task_1 = MagicMock()
    child_task_1.id = uuid4()
    child_task_2 = MagicMock()
    child_task_2.id = uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(side_effect=[parent_task, child_task_1, child_task_2])

    with patch(
        "will.agents.strategic_auditor.effects.TaskRepository",
        return_value=mock_repo,
    ):
        result = await persist_campaign(session, campaign)

    assert result == parent_id
    assert mock_repo.create.await_count == 3
    assert session.commit.await_count == 2
