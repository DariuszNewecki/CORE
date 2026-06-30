"""
Unit tests for ProposalPipelineShopManager._retire_stuck_proposal.

Verifies the three behavioural invariants of the status-guarded termination
path — no real DB required; session interactions are mocked.

Invariants:
  1. executing proposal    → UPDATE rowcount=1 → revive_and_report called → True
  2. non-executing proposal → UPDATE rowcount=0 → revive_and_report skipped → False
  3. DB error              → exception swallowed → revive_and_report skipped → False
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session(rowcount: int) -> MagicMock:
    """Mock SQLAlchemy async session with a single execute returning rowcount."""
    result = MagicMock()
    result.rowcount = rowcount

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=begin_ctx)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_ctx)

    return session


@asynccontextmanager
async def _session_ctx(session: MagicMock):  # type: ignore[no-untyped-def]
    yield session


def _make_worker_instance() -> object:
    """Bypass Worker.__init__ (reads .intent/) — set minimal attributes by hand."""
    from will.workers.proposal_pipeline_shop_manager import ProposalPipelineShopManager

    w = object.__new__(ProposalPipelineShopManager)
    w._declaration = {}
    w._max_interval = 300
    return w


def _patch_service_registry(session: MagicMock):  # type: ignore[no-untyped-def]
    """
    Return (mock_svc, orig) — replace body.services.service_registry.service_registry
    with a mock whose .session() context manager yields the given session.

    Callers are responsible for restoring orig in a finally block.
    """
    import body.services.service_registry as svc_mod

    orig = svc_mod.service_registry
    mock_svc = MagicMock()
    mock_svc.session = MagicMock(return_value=_session_ctx(session))
    svc_mod.service_registry = mock_svc
    return mock_svc, orig, svc_mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_retire_executing_proposal_terminates_and_revives() -> None:
    """
    When the status-guarded UPDATE matches a row (proposal was still executing),
    revive_and_report is called and the method returns True.
    """
    worker = _make_worker_instance()
    session = _mock_session(rowcount=1)
    revive_mock = AsyncMock()

    _, orig, svc_mod = _patch_service_registry(session)
    try:
        with patch(
            "will.workers.proposal_consumer_revival.revive_and_report",
            revive_mock,
        ):
            result = await worker._retire_stuck_proposal(  # type: ignore[attr-defined]
                "pid-executing", 950
            )
    finally:
        svc_mod.service_registry = orig

    assert result is True
    revive_mock.assert_awaited_once()
    call_args = revive_mock.await_args
    assert call_args.args[1] == "pid-executing"


async def test_retire_no_op_when_proposal_not_executing() -> None:
    """
    When the UPDATE matches zero rows (proposal transitioned before this call),
    revive_and_report is NOT called and the method returns False.
    """
    worker = _make_worker_instance()
    session = _mock_session(rowcount=0)
    revive_mock = AsyncMock()

    _, orig, svc_mod = _patch_service_registry(session)
    try:
        with patch(
            "will.workers.proposal_consumer_revival.revive_and_report",
            revive_mock,
        ):
            result = await worker._retire_stuck_proposal(  # type: ignore[attr-defined]
                "pid-not-executing", 1200
            )
    finally:
        svc_mod.service_registry = orig

    assert result is False
    revive_mock.assert_not_awaited()


async def test_retire_fail_soft_on_db_error() -> None:
    """
    A DB error during the UPDATE is caught and swallowed; revive_and_report is
    NOT called; the method returns False without propagating the exception.
    """
    worker = _make_worker_instance()

    exploding = AsyncMock()
    exploding.execute = AsyncMock(side_effect=RuntimeError("db down"))
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=begin_ctx)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    exploding.begin = MagicMock(return_value=begin_ctx)

    revive_mock = AsyncMock()

    _, orig, svc_mod = _patch_service_registry(exploding)
    try:
        with patch(
            "will.workers.proposal_consumer_revival.revive_and_report",
            revive_mock,
        ):
            result = await worker._retire_stuck_proposal(  # type: ignore[attr-defined]
                "pid-error", 900
            )
    finally:
        svc_mod.service_registry = orig

    assert result is False
    revive_mock.assert_not_awaited()
