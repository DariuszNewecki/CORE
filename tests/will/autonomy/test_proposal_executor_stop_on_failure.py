# tests/will/autonomy/test_proposal_executor_stop_on_failure.py

"""Unit tests for stop-on-failure behavior in ProposalExecutor (#709).

ProposalExecutor.execute() MUST stop processing remaining actions as soon as
any action returns ok=False or raises an exception.  Verified in dry-run
(write=False) mode to avoid DB state management and git complexity.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.action_types import ActionImpact, ActionResult
from will.autonomy.proposal import ProposalStatus
from will.autonomy.proposal_executor import ProposalExecutor


def _make_proposal(action_ids: list[str]) -> MagicMock:
    """Build a mock proposal with numbered actions."""
    proposal = MagicMock()
    proposal.proposal_id = "test-stop-p1"
    proposal.goal = "stop-on-failure test"
    proposal.status = ProposalStatus.APPROVED
    proposal.constitutional_constraints = {}
    proposal.scope = MagicMock()
    proposal.scope.policies = []

    actions = []
    for i, action_id in enumerate(action_ids):
        a = MagicMock()
        a.ref_id = action_id
        a.ref_kind = "action"
        a.order = i
        a.parameters = {}
        actions.append(a)

    proposal.actions = actions
    return proposal


def _ok_result(action_id: str) -> ActionResult:
    return ActionResult(
        action_id=action_id,
        ok=True,
        data={"files_changed": []},
        impact=ActionImpact.READ_ONLY,
        duration_sec=0.01,
    )


def _fail_result(action_id: str) -> ActionResult:
    return ActionResult(
        action_id=action_id,
        ok=False,
        data={"error": "injected failure"},
        impact=ActionImpact.READ_ONLY,
        duration_sec=0.01,
    )


@pytest.fixture()
def executor() -> ProposalExecutor:
    core_context = MagicMock()
    ex = ProposalExecutor.__new__(ProposalExecutor)
    ex.core_context = core_context
    ex.action_executor = MagicMock()
    return ex


async def test_stops_after_first_failing_action(executor: ProposalExecutor) -> None:
    """When action[0] fails, action[1] and action[2] are never executed (#709)."""
    proposal = _make_proposal(["fix.format", "fix.imports", "fix.docstrings"])

    call_count = 0

    async def side_effect(action_id, **kwargs):
        nonlocal call_count
        call_count += 1
        if action_id == "fix.format":
            return _fail_result(action_id)
        return _ok_result(action_id)

    executor.action_executor.execute = side_effect

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=proposal)

    with (
        patch(
            "will.autonomy.proposal_executor.load_vocabulary_projection",
            return_value={"vocab": "ok"},
        ),
        patch("will.autonomy.proposal_executor.service_registry") as mock_registry,
        patch(
            "will.autonomy.proposal_executor.capture_git_sha",
            return_value="abc123",
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalRepository",
            return_value=repo,
        ),
    ):
        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
        session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_registry.session.return_value = session_ctx

        result = await executor.execute("test-stop-p1", claimed_by=None, write=False)

    assert call_count == 1, f"Expected 1 action call, got {call_count}"
    assert result["actions_executed"] == 1
    assert result["actions_failed"] == 1
    assert result["ok"] is False


async def test_stops_on_exception_from_action(executor: ProposalExecutor) -> None:
    """When action[0] raises an exception, action[1] is never executed (#709)."""
    proposal = _make_proposal(["fix.format", "fix.imports"])

    call_count = 0

    async def side_effect(action_id, **kwargs):
        nonlocal call_count
        call_count += 1
        if action_id == "fix.format":
            raise RuntimeError("executor crash")
        return _ok_result(action_id)

    executor.action_executor.execute = side_effect

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=proposal)

    with (
        patch(
            "will.autonomy.proposal_executor.load_vocabulary_projection",
            return_value={"vocab": "ok"},
        ),
        patch("will.autonomy.proposal_executor.service_registry") as mock_registry,
        patch(
            "will.autonomy.proposal_executor.capture_git_sha",
            return_value="abc123",
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalRepository",
            return_value=repo,
        ),
    ):
        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
        session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_registry.session.return_value = session_ctx

        result = await executor.execute("test-stop-p1", claimed_by=None, write=False)

    assert call_count == 1, f"Expected 1 action call, got {call_count}"
    assert result["actions_executed"] == 1
    assert result["ok"] is False


async def test_all_actions_run_when_all_succeed(executor: ProposalExecutor) -> None:
    """When all actions succeed, every action is executed (#709 regression guard)."""
    proposal = _make_proposal(["fix.format", "fix.imports", "fix.docstrings"])

    call_count = 0

    async def side_effect(action_id, **kwargs):
        nonlocal call_count
        call_count += 1
        return _ok_result(action_id)

    executor.action_executor.execute = side_effect

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=proposal)

    with (
        patch(
            "will.autonomy.proposal_executor.load_vocabulary_projection",
            return_value={"vocab": "ok"},
        ),
        patch("will.autonomy.proposal_executor.service_registry") as mock_registry,
        patch(
            "will.autonomy.proposal_executor.capture_git_sha",
            return_value="abc123",
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalRepository",
            return_value=repo,
        ),
    ):
        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
        session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_registry.session.return_value = session_ctx

        result = await executor.execute("test-stop-p1", claimed_by=None, write=False)

    assert call_count == 3
    assert result["actions_executed"] == 3
    assert result["actions_succeeded"] == 3
    assert result["ok"] is True
