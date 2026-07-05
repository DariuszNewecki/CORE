"""StrategicAuditor effects — approved-cluster execution contract.

Covers the per-cluster review surface (ADR-110 D4): execute_approved_clusters
runs only the children the governor moved to status='approved' (and only
autonomous ones, not escalations), dispatches each to develop_from_goal with a
signature autospec enforces (regression guard for the #115 session= bug), and
moves each executed cluster's Task to completed/failed.

The tests mock the repository and develop_from_goal; no DB, LLM, or orchestrator
path is exercised.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

# body.atomic must finish loading before will.agents pulls in
# will.autonomy.proposal — pre-existing circular import otherwise.
import body.atomic  # noqa: F401  -- import-order side effect, not a usage
import will.agents.strategic_auditor.effects as effects_mod
import will.autonomy.autonomous_developer as autonomous_developer
from will.agents.strategic_auditor.effects import execute_approved_clusters


def _child(
    status: str,
    *,
    requires_approval: bool = False,
    role: str = "AutonomousDeveloper",
    workflow_type: str = "refactor_modularity",
    intent: str = "do the thing",
    int_id: int = 1,
):
    """A cluster Task. Approved-and-runnable = pending + requires_approval=False."""
    task = MagicMock(name=f"Task[{status},appr={requires_approval}]")
    task.id = uuid.UUID(int=int_id)
    task.status = status
    task.requires_approval = requires_approval
    task.assigned_role = role
    task.intent = intent
    task.context = {"workflow_type": workflow_type}
    return task


def _wire(monkeypatch, children):
    """Patch TaskRepository + develop_from_goal; return (mock_repo, mock_dfg)."""
    mock_repo = MagicMock(name="TaskRepository")
    mock_repo.list_children = AsyncMock(return_value=children)
    mock_repo.update_status = AsyncMock()
    monkeypatch.setattr(effects_mod, "TaskRepository", lambda session: mock_repo)

    mock_dfg = create_autospec(
        autonomous_developer.develop_from_goal, return_value=(True, "ok")
    )
    monkeypatch.setattr(autonomous_developer, "develop_from_goal", mock_dfg)
    return mock_repo, mock_dfg


# ID: 7a1b2c3d-4e5f-4061-9273-8495a6b7c8d9
async def test_runs_only_approved_autonomous_clusters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only cleared autonomous clusters (pending + requires_approval=False) dispatch."""
    approved = _child(
        "pending",
        requires_approval=False,
        workflow_type="refactor_modularity",
        int_id=1,
    )
    children = [
        approved,
        _child("pending", requires_approval=True, int_id=2),  # awaiting — skip
        _child("blocked", int_id=3),  # rejected — skip
        _child(
            "pending", requires_approval=False, role="Human", int_id=4
        ),  # escalation
    ]
    mock_repo, mock_dfg = _wire(monkeypatch, children)

    results = await execute_approved_clusters(
        MagicMock(name="CoreContext"), MagicMock(name="session"), uuid.UUID(int=99)
    )

    mock_dfg.assert_awaited_once()
    _, kwargs = mock_dfg.await_args
    assert "session" not in kwargs  # the #115 regression
    assert kwargs["write"] is True
    assert kwargs["workflow_type"] == "refactor_modularity"
    assert kwargs["goal"] == "do the thing"
    mock_repo.update_status.assert_awaited_once_with(approved.id, "completed")
    assert results == [(str(approved.id), True, "ok")]


# ID: 8b2c3d4e-5f60-4172-a384-95b6c7d8e9f0
async def test_no_approved_clusters_runs_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A campaign with nothing cleared dispatches no work and returns empty."""
    children = [
        _child("pending", requires_approval=True, int_id=1),  # awaiting review
        _child("blocked", int_id=2),  # rejected
    ]
    mock_repo, mock_dfg = _wire(monkeypatch, children)

    results = await execute_approved_clusters(
        MagicMock(name="CoreContext"), MagicMock(name="session"), uuid.UUID(int=99)
    )

    mock_dfg.assert_not_awaited()
    mock_repo.update_status.assert_not_awaited()
    assert results == []


# ID: 9c3d4e5f-6071-4283-b495-a6c7d8e9f001
async def test_failed_cluster_marked_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cluster whose workflow fails is moved to 'failed', not 'completed'."""
    approved = _child("pending", requires_approval=False, int_id=7)
    mock_repo, mock_dfg = _wire(monkeypatch, [approved])
    mock_dfg.return_value = (False, "boom")

    results = await execute_approved_clusters(
        MagicMock(name="CoreContext"), MagicMock(name="session"), uuid.UUID(int=99)
    )

    mock_repo.update_status.assert_awaited_once_with(approved.id, "failed")
    assert results == [(str(approved.id), False, "boom")]
