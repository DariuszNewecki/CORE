# tests/will/autonomy/test_pending_proposal_gate.py
"""Pending-proposal gate (governor redesign 2026-10-12).

A proposal that needs the governor is dry-run first: a clean run marks it
``pre_approval_run`` (then it is listed and approvable); a failed run rejects
it, which revives its findings. Anything pending over 72h is rejected as
expired so the loop regenerates it against current code.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from will.autonomy import pending_proposal_gate as gate


NOW = datetime(2026, 10, 12, 18, 0, tzinfo=UTC)


def _proposal(pid: str, age_hours: float, results: dict | None = None, required=True):
    return SimpleNamespace(
        proposal_id=pid,
        approval_required=required,
        created_at=NOW - timedelta(hours=age_hours),
        validation_results=results or {},
    )


async def _screen(proposals: list[Any], run_ok: dict[str, bool]):
    session = MagicMock()
    session.commit = AsyncMock()

    @asynccontextmanager
    async def _session():
        yield session

    repo = MagicMock()
    repo.list_by_status = AsyncMock(return_value=proposals)
    repo.update_fields = AsyncMock()
    service = MagicMock()
    service.reject = AsyncMock(return_value=1)
    executor = MagicMock()
    executor.execute = AsyncMock(
        side_effect=lambda pid, _by, write: {"ok": run_ok[pid], "error": "boom"}
    )
    with (
        patch("body.services.service_registry.service_registry.session", _session),
        patch(
            "will.autonomy.proposal_repository.ProposalRepository", return_value=repo
        ),
        patch("will.autonomy.proposal_service.ProposalService", return_value=service),
        patch(
            "will.autonomy.proposal_executor.ProposalExecutor", return_value=executor
        ),
    ):
        outcome = await gate.screen_pending_proposals(MagicMock(), uuid4(), now=NOW)
    return outcome, repo, service, executor


async def test_a_clean_dry_run_marks_the_proposal_ready() -> None:
    outcome, repo, service, executor = await _screen([_proposal("p1", 1)], {"p1": True})
    assert outcome.passed == ["p1"]
    assert executor.execute.await_args.kwargs == {"write": False}
    repo.update_fields.assert_awaited_once_with(
        "p1", {"validation_results": {"pre_approval_run": True}}
    )
    service.reject.assert_not_called()


async def test_a_failed_dry_run_is_rejected_back_to_the_loop() -> None:
    outcome, repo, service, _ = await _screen([_proposal("p1", 1)], {"p1": False})
    assert outcome.failed == ["p1"]
    service.reject.assert_awaited_once()
    assert "pre-approval run" in service.reject.await_args.args[1]
    repo.update_fields.assert_not_called()


async def test_older_than_72h_expires_without_running() -> None:
    outcome, _, service, executor = await _screen([_proposal("p1", 73)], {})
    assert outcome.expired == ["p1"]
    assert "Expired" in service.reject.await_args.args[1]
    executor.execute.assert_not_called()


async def test_already_screened_and_no_approval_needed_are_left_alone() -> None:
    proposals = [
        _proposal("ready", 1, {"pre_approval_run": True}),
        _proposal("auto", 1, required=False),
    ]
    outcome, _, service, executor = await _screen(proposals, {})
    assert outcome.as_payload() == {
        "pre_approval_passed": [],
        "pre_approval_failed": [],
        "expired": [],
    }
    executor.execute.assert_not_called()
    service.reject.assert_not_called()
