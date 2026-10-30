from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.proposal_consumer_revival import release_executing_proposals


# ID: d94aad05-0425-4823-a47a-e470cf23aa29
async def test_release_executing_proposals() -> None:
    worker = MagicMock()
    worker_uuid = uuid.uuid4()

    row1 = (uuid.uuid4(),)
    row2 = (uuid.uuid4(),)

    result = MagicMock()
    result.fetchall = MagicMock(return_value=[row1, row2])

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    service_registry = MagicMock()
    service_registry.session = MagicMock(return_value=session_cm)

    mark_failed = AsyncMock()
    revive = AsyncMock()

    with (
        patch("body.services.service_registry.service_registry", service_registry),
        patch(
            "will.autonomy.proposal_consumer_revival.mark_proposal_failed", mark_failed
        ),
        patch("will.autonomy.proposal_consumer_revival.revive_and_report", revive),
    ):
        released = await release_executing_proposals(worker, worker_uuid)

    assert released == 2
    session.execute.assert_awaited_once()
    assert mark_failed.await_count == 2
    assert revive.await_count == 2
    mark_failed.assert_any_await(
        str(row1[0]), "worker terminated during execution (finally-block release)"
    )
    revive.assert_any_await(
        worker,
        str(row2[0]),
        "worker terminated during execution (finally-block release)",
    )


import pytest

from will.autonomy.proposal_consumer_revival import mark_proposal_failed


@pytest.mark.asyncio
# ID: 66cdb831-33a5-44d0-964a-2f3f0014934b
async def test_mark_proposal_failed():
    mock_session = MagicMock()

    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=None)

    mock_registry = MagicMock()
    mock_registry.session.return_value = mock_session_cm

    mock_state_manager = MagicMock()
    mock_state_manager.mark_failed = AsyncMock(return_value=None)

    with (
        patch("body.services.service_registry.service_registry", mock_registry),
        patch(
            "will.autonomy.proposal_state_manager.ProposalStateManager",
            return_value=mock_state_manager,
        ),
    ):
        await mark_proposal_failed("prop-123", "boom")

    mock_state_manager.mark_failed.assert_awaited_once_with("prop-123", "boom")
