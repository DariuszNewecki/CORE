"""Tests for BlackboardService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.services.blackboard_service.blackboard_service import BlackboardService


class TestBlackboardService:
    """Test suite for BlackboardService."""

    @pytest.fixture
    def service(self) -> BlackboardService:
        """Create a BlackboardService instance."""
        return BlackboardService()

    @pytest.mark.asyncio
    async def test_fetch_open_finding_subjects_by_prefix_empty(
        self, service: BlackboardService
    ) -> None:
        """fetch_open_finding_subjects_by_prefix returns empty set when no matches."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "body.services.service_registry.ServiceRegistry.session"
        ) as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session
            result = await service.fetch_open_finding_subjects_by_prefix("test::%")
            assert result == set()

    @pytest.mark.asyncio
    async def test_fetch_open_finding_subjects_by_prefix_returns_set(
        self, service: BlackboardService
    ) -> None:
        """fetch_open_finding_subjects_by_prefix returns set of subjects."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("subject1",), ("subject2",)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "body.services.service_registry.ServiceRegistry.session"
        ) as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session
            result = await service.fetch_open_finding_subjects_by_prefix("test::%")
            assert result == {"subject1", "subject2"}

    @pytest.mark.asyncio
    async def test_fetch_active_finding_subjects_by_prefix_empty(
        self, service: BlackboardService
    ) -> None:
        """fetch_active_finding_subjects_by_prefix returns empty set when no matches."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "body.services.service_registry.ServiceRegistry.session"
        ) as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session
            result = await service.fetch_active_finding_subjects_by_prefix("test::%")
            assert result == set()

    @pytest.mark.asyncio
    async def test_fetch_active_finding_subjects_by_prefix_returns_set(
        self, service: BlackboardService
    ) -> None:
        """fetch_active_finding_subjects_by_prefix returns set of subjects."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("subject1",), ("subject2",)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "body.services.service_registry.ServiceRegistry.session"
        ) as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session
            result = await service.fetch_active_finding_subjects_by_prefix("test::%")
            assert result == {"subject1", "subject2"}

    @pytest.mark.asyncio
    async def test_resolve_dry_run_entries_for_namespace_zero(
        self, service: BlackboardService
    ) -> None:
        """resolve_dry_run_entries_for_namespace returns 0 when no entries updated."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.begin = MagicMock()
        mock_session.begin.return_value.__aenter__.return_value = mock_session

        with patch(
            "body.services.service_registry.ServiceRegistry.session"
        ) as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_se
