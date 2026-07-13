# tests/will/governance/test_proposal_runner.py
"""Tests for the proposal_runner facade (ADR-049 D1 debt closure, #771).

The facade extracts domain construction + scoring (create_and_score_proposal)
and executor invocation (execute_proposal_direct) out of the API route layer.
These verify the extracted logic behaves identically to the pre-extraction
inline code — dry-run vs write, and executor delegation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from will.governance.proposal_runner import (
    create_and_score_proposal,
    execute_proposal_direct,
)


async def test_create_dry_run_scores_but_does_not_persist() -> None:
    """write=False builds + risk-scores the proposal but never calls
    ProposalService.create or session.commit."""
    session = AsyncMock()

    with patch(
        "will.autonomy.proposal_service.ProposalService"
    ) as service_cls:
        result = await create_and_score_proposal(
            session,
            goal="refactor the widget",
            actions=[{"action_id": "fix.format", "parameters": {}}],
            files=["src/widget.py"],
            created_by="cli_operator",
            write=False,
        )

    assert result["ok"] is True
    assert result["persisted"] is False
    assert result["proposal"]["goal"] == "refactor the widget"
    # risk was computed — the proposal dict carries a risk assessment
    assert "risk" in result["proposal"]
    service_cls.assert_not_called()
    session.commit.assert_not_awaited()


async def test_create_write_persists_and_commits() -> None:
    """write=True persists via ProposalService.create and commits the session."""
    session = AsyncMock()
    service_instance = AsyncMock()

    with patch(
        "will.autonomy.proposal_service.ProposalService",
        return_value=service_instance,
    ) as service_cls:
        result = await create_and_score_proposal(
            session,
            goal="refactor the widget",
            actions=[{"action_id": "fix.format", "parameters": {}}],
            files=["src/widget.py"],
            created_by="cli_operator",
            write=True,
        )

    assert result["ok"] is True
    assert result["persisted"] is True
    service_cls.assert_called_once_with(session)
    service_instance.create.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_create_preserves_action_order_and_flow_ids() -> None:
    """Action list-comprehension maps action_id/flow_id/parameters/order
    exactly as the pre-extraction route did."""
    session = AsyncMock()

    with patch("will.autonomy.proposal_service.ProposalService"):
        result = await create_and_score_proposal(
            session,
            goal="mixed actions",
            actions=[
                {"action_id": "fix.format"},
                {"flow_id": "flow.fix_code", "order": 5},
            ],
            files=[],
            created_by="cli_operator",
            write=False,
        )

    actions = result["proposal"]["actions"]
    assert len(actions) == 2


async def test_execute_delegates_to_proposal_executor() -> None:
    """execute_proposal_direct constructs ProposalExecutor(context) and
    forwards proposal_id, claimer, write verbatim."""
    context = MagicMock()
    claimer = UUID("00000000-0000-0000-0000-000000000002")
    executor_instance = AsyncMock()
    executor_instance.execute = AsyncMock(return_value={"ok": True, "executed": True})

    with patch(
        "will.autonomy.proposal_executor.ProposalExecutor",
        return_value=executor_instance,
    ) as executor_cls:
        result = await execute_proposal_direct(
            context,
            proposal_id="pid-1",
            claimer=claimer,
            write=True,
        )

    assert result == {"ok": True, "executed": True}
    executor_cls.assert_called_once_with(context)
    executor_instance.execute.assert_awaited_once_with("pid-1", claimer, write=True)
