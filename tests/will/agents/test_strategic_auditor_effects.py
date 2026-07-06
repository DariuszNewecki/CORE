"""StrategicAuditor effects — approved-cluster execution contract.

Covers the per-cluster review surface (ADR-110 D4): execute_approved_clusters
runs only the children the governor moved to status='approved' (and only
autonomous ones, not escalations), dispatches each to develop_from_goal with a
signature autospec enforces (regression guard for the #115 session= bug), and
moves each executed cluster's Task to completed/failed.

Also covers (new, this session):
  - workflow alias normalization: full_feature_development → code_modification
  - affected_files disk filter: hallucinated paths stripped before goal augmentation
  - goal augmentation: real file anchors appended when real_files is non-empty

The tests mock the repository and develop_from_goal; no DB, LLM, or orchestrator
path is exercised.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

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


# ID: 7137eec0-6924-4b57-b1d1-9330e94d5eb6
async def test_workflow_alias_full_feature_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """full_feature_development in cluster context is aliased to code_modification."""
    approved = _child(
        "pending",
        requires_approval=False,
        workflow_type="full_feature_development",
        intent="do a thing",
        int_id=10,
    )
    _, mock_dfg = _wire(monkeypatch, [approved])

    ctx = MagicMock(name="CoreContext")
    ctx.git_service.repo_path = "/opt/dev/CORE"

    await execute_approved_clusters(ctx, MagicMock(name="session"), uuid.UUID(int=99))

    _, kwargs = mock_dfg.await_args
    assert kwargs["workflow_type"] == "code_modification"


# ID: f5630fdd-a07f-4ae6-9508-0b3c25063210
async def test_affected_files_hallucinated_paths_stripped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Paths in affected_files that don't exist on disk are excluded from the goal."""
    task = MagicMock(name="Task[pending]")
    task.id = uuid.UUID(int=11)
    task.status = "pending"
    task.requires_approval = False
    task.assigned_role = "AutonomousDeveloper"
    task.intent = "fix something"
    task.context = {
        "workflow_type": "code_modification",
        "affected_files": ["src/body/services/unknown.py", "src/real/module.py"],
    }

    _, mock_dfg = _wire(monkeypatch, [task])

    ctx = MagicMock(name="CoreContext")
    ctx.git_service.repo_path = "/repo"

    def _exists_only_real(path: Path) -> bool:
        return path.name == "module.py"

    with patch.object(Path, "exists", _exists_only_real):
        await execute_approved_clusters(ctx, MagicMock(name="session"), uuid.UUID(int=99))

    _, kwargs = mock_dfg.await_args
    assert "src/body/services/unknown.py" not in kwargs["goal"]
    assert "src/real/module.py" in kwargs["goal"]


# ID: e23df1a2-1054-442b-b827-c3bb61499500
async def test_no_real_files_goal_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When all affected_files are invented, the goal is passed as-is (no augmentation)."""
    task = MagicMock(name="Task[pending]")
    task.id = uuid.UUID(int=12)
    task.status = "pending"
    task.requires_approval = False
    task.assigned_role = "AutonomousDeveloper"
    task.intent = "original goal text"
    task.context = {
        "workflow_type": "code_modification",
        "affected_files": ["src/made/up.py"],
    }

    _, mock_dfg = _wire(monkeypatch, [task])

    ctx = MagicMock(name="CoreContext")
    ctx.git_service.repo_path = "/repo"

    with patch.object(Path, "exists", return_value=False):
        await execute_approved_clusters(ctx, MagicMock(name="session"), uuid.UUID(int=99))

    _, kwargs = mock_dfg.await_args
    assert kwargs["goal"] == "original goal text"


# ID: 9df032f8-7ffe-4fc9-8cd3-16cab78284ae
async def test_real_files_appended_to_goal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real affected_files are appended to the goal as target anchors."""
    task = MagicMock(name="Task[pending]")
    task.id = uuid.UUID(int=13)
    task.status = "pending"
    task.requires_approval = False
    task.assigned_role = "AutonomousDeveloper"
    task.intent = "fix the code"
    task.context = {
        "workflow_type": "code_modification",
        "affected_files": ["src/will/agents/strategic_auditor/effects.py"],
    }

    _, mock_dfg = _wire(monkeypatch, [task])

    ctx = MagicMock(name="CoreContext")
    ctx.git_service.repo_path = "/repo"

    with patch.object(Path, "exists", return_value=True):
        await execute_approved_clusters(ctx, MagicMock(name="session"), uuid.UUID(int=99))

    _, kwargs = mock_dfg.await_args
    goal = kwargs["goal"]
    assert goal.startswith("fix the code")
    assert "Target files (from audit findings):" in goal
    assert "src/will/agents/strategic_auditor/effects.py" in goal
