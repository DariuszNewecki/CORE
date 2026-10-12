# tests/will/autonomy/test_proposal_executor_pending_dry_run.py
"""A PENDING proposal may be dry-run (its pre-approval run), never written.

Governor redesign 2026-10-12: will.autonomy.pending_proposal_gate dry-runs a
proposal before the governor sees it. A write still needs APPROVED.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.action_types import ActionImpact, ActionResult
from will.autonomy.proposal import ProposalStatus
from will.autonomy.proposal_executor import ProposalExecutor


def _proposal(status: ProposalStatus) -> MagicMock:
    proposal = MagicMock()
    proposal.proposal_id = "p-pending"
    proposal.goal = "pre-approval run"
    proposal.status = status
    proposal.constitutional_constraints = {}
    proposal.scope = MagicMock()
    proposal.scope.policies = []
    action = MagicMock()
    action.ref_id = "fix.format"
    action.ref_kind = "action"
    action.order = 0
    action.parameters = {}
    proposal.actions = [action]
    return proposal


async def _run(status: ProposalStatus, write: bool) -> tuple[dict, MagicMock]:
    executor = ProposalExecutor.__new__(ProposalExecutor)
    executor.core_context = MagicMock()
    executor.action_executor = MagicMock()
    executor.action_executor.execute = AsyncMock(
        return_value=ActionResult(
            action_id="fix.format",
            ok=True,
            data={"files_changed": []},
            impact=ActionImpact.READ_ONLY,
            duration_sec=0.01,
        )
    )
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=_proposal(status))
    with (
        patch(
            "will.autonomy.proposal_executor.load_vocabulary_projection",
            return_value={"vocab": "ok"},
        ),
        patch("will.autonomy.proposal_executor.service_registry") as registry,
        patch("will.autonomy.proposal_executor.capture_git_sha", return_value="abc"),
        patch("will.autonomy.proposal_executor.ProposalRepository", return_value=repo),
    ):
        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
        session_ctx.__aexit__ = AsyncMock(return_value=False)
        registry.session.return_value = session_ctx
        result = await executor._execute("p-pending", None, write)
    return result, executor.action_executor.execute


async def test_a_pending_proposal_can_be_dry_run() -> None:
    result, execute = await _run(ProposalStatus.PENDING, write=False)
    assert result["ok"] is True
    execute.assert_awaited_once()


@pytest.mark.parametrize("status", [ProposalStatus.PENDING, ProposalStatus.REJECTED])
async def test_a_write_still_needs_approval(status: ProposalStatus) -> None:
    result, execute = await _run(status, write=True)
    assert result["ok"] is False
    assert "not approved" in result["error"]
    execute.assert_not_called()
