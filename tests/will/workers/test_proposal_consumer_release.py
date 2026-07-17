# tests/will/workers/test_proposal_consumer_release.py
"""
Unit tests for release_executing_proposals (proposal_consumer_revival.py).

Verifies the finally-block release path that handles graceful-shutdown
scenarios (SIGTERM → CancelledError) where the per-proposal except branch
is bypassed. Covers: normal exit (0 stuck), one stuck proposal, and DB
query failure.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch


_WORKER_UUID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_PROPOSAL_ID = "prop-stuck-0001"


def _make_worker() -> MagicMock:
    worker = MagicMock()
    worker.worker_uuid = _WORKER_UUID
    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()
    return worker


def _make_session_cm(rows: list) -> MagicMock:
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


async def test_no_stuck_proposals_returns_zero() -> None:
    """Normal successful run: query returns empty, released count is 0."""
    from will.autonomy.proposal_consumer_revival import release_executing_proposals

    mock_registry = MagicMock()
    mock_registry.session.return_value = _make_session_cm([])

    with patch("body.services.service_registry.service_registry", mock_registry):
        released = await release_executing_proposals(_make_worker(), _WORKER_UUID)

    assert released == 0


async def test_one_stuck_proposal_is_released() -> None:
    """
    One EXECUTING proposal owned by this worker → mark_failed + revive_and_report
    called, released count is 1.
    """
    from will.autonomy.proposal_consumer_revival import release_executing_proposals

    mock_registry = MagicMock()
    mock_registry.session.return_value = _make_session_cm([(_PROPOSAL_ID,)])

    with (
        patch("body.services.service_registry.service_registry", mock_registry),
        patch(
            "will.autonomy.proposal_consumer_revival.mark_proposal_failed",
            new_callable=AsyncMock,
        ) as mock_mark,
        patch(
            "will.autonomy.proposal_consumer_revival.revive_and_report",
            new_callable=AsyncMock,
        ) as mock_revive,
    ):
        worker = _make_worker()
        released = await release_executing_proposals(worker, _WORKER_UUID)

    assert released == 1
    mock_mark.assert_awaited_once_with(
        _PROPOSAL_ID,
        "worker terminated during execution (finally-block release)",
    )
    mock_revive.assert_awaited_once()
    revive_args = mock_revive.await_args
    assert revive_args.args[1] == _PROPOSAL_ID


async def test_db_query_error_returns_zero() -> None:
    """DB failure during query → logged, returns 0, does not propagate."""
    from will.autonomy.proposal_consumer_revival import release_executing_proposals

    mock_registry = MagicMock()
    mock_registry.session.side_effect = RuntimeError("connection lost")

    with patch("body.services.service_registry.service_registry", mock_registry):
        released = await release_executing_proposals(_make_worker(), _WORKER_UUID)

    assert released == 0
