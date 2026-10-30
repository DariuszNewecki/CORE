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
