import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from typing import Any

from src.body.services.blackboard_service.blackboard_proposal_service import BlackboardProposalService


@pytest.fixture
def proposal_service() -> BlackboardProposalService:
    """Return a bare instance — all methods use ServiceRegistry internally."""
    return BlackboardProposalService()


class TestDeferEntriesToProposal:
    """Cover BlackboardProposalService.defer_entries_to_proposal."""

    async def test_returns_zero_for_empty_list(
        self, proposal_service: BlackboardProposalService
    ) -> None:
        """When entry_ids is empty the method returns 0 immediately."""
        result = await proposal_service.defer_entries_to_proposal([], "proposal-uuid-1")
        assert result == 0

    @patch("src.body.services.blackboard_service.blackboard_proposal_service.ServiceRegistry")
    async def test_updates_matching_entries(
        self, mock_registry: MagicMock, proposal_service: BlackboardProposalService
    ) -> None:
        """Entries in 'open' or 'claimed' status get deferred and counted."""
        mock_session = AsyncMock()
        mock_registry.session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        mock_execute = AsyncMock()
        mock_session.execute = mock_execute

        # Simulate one row updated per call, one entry with no match -> rowcount 0
        mock_execute.side_effect = [
            MagicMock(rowcount=1),
            MagicMock(rowcount=1),
            MagicMock(rowcount=0),
        ]

        result = await proposal_service.defer_entries_to_proposal(
            ["id-a", "id-b", "id-c"], "proposal-1"
        )
        assert result == 2
        # Each call used a transaction handle: begin is used per loop iteration
        assert mock_execute.call_count == 3


class TestResolveEntriesForProposal:
    """Cover BlackboardProposalService.resolve_entries_for_proposal."""

    async def test_returns_zero_for_empty_list(
        self, proposal_service: BlackboardProposalService
    ) -> None:
        """When entry_ids is empty the method returns 0."""
        result = await proposal_service.resolve_entries_for_proposal([], "proposal-uuid-1")
        assert result == 0

    @patch("src.body.services.blackboard_service.blackboard_proposal_service.ServiceRegistry")
    async def test_updates_and_counts_resolved(
        self, mock_registry: MagicMock, proposal_service: BlackboardProposalService
    ) -> None:
        """Only 'open'/'claimed' entries are resolved; proposal_id is merged."""
        mock_session = AsyncMock()
        mock_registry.session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        mock_execute = AsyncMock()
        mock_session.execute = mock_execute
        mock_execute.side_effect = [
            MagicMock(rowcount=1),
            MagicMock(rowcount=0),
        ]

        result = await proposal_service.resolve_entries_for_proposal(
            ["id-x", "id-y"], "proposal-99"
        )
        assert result == 1
        assert mock_execute.call_count == 2


class TestReviveFindingsForFailedProposal:
    """Cover BlackboardProposalService.revive_findings_for_failed_proposal."""

    @patch("src.body.services.blackboard_service.blackboard_proposal_service.ServiceRegistry")
    @patch("src.body.services.blackboard_service.blackboard_proposal_service.logger")
    async def test_returns_none_when_no_rows_revived(
        self,
        mock_logger: MagicMock,
        mock_registry: MagicMock,
        proposal_service: BlackboardProposalService,
    ) -> None:
        """No findings deferred → method returns None."""
        mock_session = AsyncMock()
        mock_registry.session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session

        mock_fetchall = MagicMock(return_value=[])
        mock_execute = AsyncMock()
        mock_execute.fetchall = moc
