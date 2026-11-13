from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.proposal_repository import ProposalRepository


# ID: 99531cdc-0f87-4685-aa97-e807fefc644b
async def test_ProposalRepository_create():
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    repo = ProposalRepository(session)

    proposal_id = str(uuid.uuid4())
    mock_proposal = MagicMock()
    mock_proposal.proposal_id = proposal_id

    mock_db_model = MagicMock()

    with patch(
        "will.autonomy.proposal_repository.ProposalMapper.to_db_model",
        return_value=mock_db_model,
    ) as mock_to_db_model:
        result = await repo.create(mock_proposal)

    assert result == proposal_id
    mock_to_db_model.assert_called_once()
    session.add.assert_called_once_with(mock_db_model)
    session.flush.assert_awaited_once()


# ID: f03a75da-03e2-426d-b436-173288862893
async def test_ProposalRepository_get() -> None:
    from will.autonomy.proposal_repository import ProposalRepository

    expected_proposal = MagicMock(name="expected_proposal")
    db_record = MagicMock(name="db_record")

    mock_result = MagicMock(name="result")
    mock_result.scalar_one_or_none.return_value = db_record

    mock_session = MagicMock(name="session")
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = ProposalRepository(mock_session)

    with patch(
        "will.autonomy.proposal_repository.ProposalMapper.from_db_model",
        return_value=expected_proposal,
    ) as mock_from_db_model:
        proposal = await repo.get("prop-123")

    mock_session.execute.assert_awaited_once()
    mock_result.scalar_one_or_none.assert_called_once()
    mock_from_db_model.assert_called_once_with(db_record)
    assert proposal is expected_proposal


# ID: 54e2a8e0-9e5f-4ee2-a0ff-949d7788d74c
async def test_ProposalRepository():
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()

    repo = ProposalRepository(session)

    proposal = MagicMock()
    proposal.proposal_id = "prop-123"

    db_model = MagicMock()

    with patch(
        "will.autonomy.proposal_repository.ProposalMapper.to_db_model",
        return_value=db_model,
    ) as mock_to_db:
        result_id = await repo.create(proposal)

    assert result_id == "prop-123"
    mock_to_db.assert_called_once()
    session.add.assert_called_once_with(db_model)
    session.flush.assert_awaited_once()


import pytest


@pytest.mark.asyncio
# ID: bd24db6f-4984-49f0-82cb-75502cdcbbb5
async def test_ProposalRepository_update_fields():
    from will.autonomy.proposal_repository import ProposalRepository

    session = MagicMock()
    session.execute = AsyncMock()

    repo = ProposalRepository(session)

    with patch(
        "shared.infrastructure.database.models.autonomous_proposals.AutonomousProposal"
    ) as mock_model:
        mock_model.proposal_id = MagicMock()
        mock_stmt = MagicMock()
        mock_model.proposal_id.__eq__ = MagicMock(return_value=MagicMock())
        # Build the update() chain by patching sqlalchemy.update
        with patch("sqlalchemy.update") as mock_update:
            chain = MagicMock()
            mock_update.return_value = chain
            chain.where.return_value = chain
            chain.values.return_value = chain

            await repo.update_fields("prop-123", {"state": "APPROVED"})

            mock_update.assert_called_once_with(mock_model)
            chain.where.assert_called_once()
            chain.values.assert_called_once_with(state="APPROVED")
            session.execute.assert_awaited_once_with(chain)


# ID: 437217f4-10d4-4c51-9efa-939cab5ca834
async def test_ProposalRepository_list_by_status_paginated() -> None:
    from will.autonomy.proposal_repository import Proposal, ProposalStatus

    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = ProposalRepository(mock_session)

    with patch(
        "will.autonomy.proposal_repository.ProposalMapper.from_db_model",
        return_value=MagicMock(spec=Proposal),
    ) as mock_from_db:
        status = ProposalStatus.PENDING
        proposals, has_more, next_cursor = await repo.list_by_status_paginated(
            status=status, limit=10, after_cursor=None
        )

    assert proposals == []
    assert has_more is False
    assert next_cursor is None
    mock_session.execute.assert_awaited_once()
    mock_from_db.assert_not_called()


import pytest


@pytest.mark.asyncio
# ID: c6e7e098-d68c-4fc9-bb36-a6591466e88f
async def test_ProposalRepository_list_by_status():
    # Arrange: mock the DB session and its async execute()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_proposal_model = MagicMock()
    mock_scalars.all.return_value = [mock_proposal_model]
    mock_result.scalars.return_value = mock_scalars

    session = MagicMock()
    session.execute = AsyncMock(return_value=mock_result)

    repo = ProposalRepository(session)

    status = MagicMock()
    status.value = "pending"

    sentinel_proposal = MagicMock()

    # Patch ProposalMapper where it is used (consuming module namespace)
    with patch("will.autonomy.proposal_repository.ProposalMapper") as mock_mapper:
        mock_mapper.from_db_model.return_value = sentinel_proposal

        # Act
        proposals = await repo.list_by_status(status)

    # Assert: session.execute awaited once with a statement, and result mapped
    session.execute.assert_awaited_once()
    executed_stmt = session.execute.await_args.args[0]
    assert executed_stmt is not None
    mock_result.scalars.assert_called_once()
    mock_scalars.all.assert_called_once()
    mock_mapper.from_db_model.assert_called_once_with(mock_proposal_model)
    assert proposals == [sentinel_proposal]



import pytest


@pytest.mark.asyncio
# ID: 09ec1920-69d1-4e1d-a0a6-7032a740f7c9
async def test_ProposalRepository_flow_targets():
    session = MagicMock()

    result_mock = MagicMock()
    result_mock.all.return_value = [
        ("alpha", "beta"),
        ("gamma", "delta"),
        ("alpha", "beta"),  # duplicate to confirm set dedup
    ]
    session.execute = AsyncMock(return_value=result_mock)

    repo = ProposalRepository(session)

    statuses = [MagicMock(value="pending"), MagicMock(value="in_review")]

    out = await repo.flow_targets(
        flow_id="flow-123",
        statuses=statuses,
        param_keys=("source", "target"),
    )

    assert out == {("alpha", "beta"), ("gamma", "delta")}
    session.execute.assert_awaited_once()
    result_mock.all.assert_called_once()
