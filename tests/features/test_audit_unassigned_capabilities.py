# tests/features/test_audit_unassigned_capabilities.py
from unittest.mock import AsyncMock, Mock, patch

# Module under test
from features.introspection.audit_unassigned_capabilities import get_unassigned_symbols


class TestAuditUnassignedCapabilities:
    """Test suite for audit_unassigned_capabilities module."""

    def test_get_unassigned_symbols_finds_matching_symbols(self):
        """Test that get_unassigned_symbols correctly identifies public unassigned symbols."""
        # Mock symbols data
        mock_symbols = {
            "symbol1": {"name": "public_func", "capability": "unassigned"},
            "symbol2": {
                "name": "_private_func",
                "capability": "unassigned",
            },  # Should be excluded (private)
            "symbol3": {
                "name": "assigned_func",
                "capability": "read",
            },  # Should be excluded (assigned capability)
            "symbol4": {
                "name": "another_public",
                "capability": "unassigned",
            },  # Should be included
        }

        # Mock the async chain
        mock_graph = {"symbols": mock_symbols}
        mock_knowledge_service = Mock()
        mock_knowledge_service.get_graph = AsyncMock(return_value=mock_graph)

        with (
            patch(
                "features.introspection.audit_unassigned_capabilities.KnowledgeService"
            ) as mock_ks_class,
            patch(
                "features.introspection.audit_unassigned_capabilities.settings"
            ) as mock_settings,
        ):
            mock_ks_class.return_value = mock_knowledge_service
            mock_settings.REPO_PATH = "/mock/repo/path"

            # Execute the function
            result = get_unassigned_symbols()

            # Verify results
            assert len(result) == 2
            assert result[0]["key"] == "symbol1"
            assert result[0]["name"] == "public_func"
            assert result[0]["capability"] == "unassigned"
            assert result[1]["key"] == "symbol4"
            assert result[1]["name"] == "another_public"
            assert result[1]["capability"] == "unassigned"

            # Verify service was called correctly
            mock_ks_class.assert_called_once_with("/mock/repo/path")
            mock_knowledge_service.get_graph.assert_called_once()

    def test_get_unassigned_symbols_no_matches(self):
        """Test that get_unassigned_symbols returns empty list when no symbols match criteria."""
        # Mock symbols data with no matching symbols
        mock_symbols = {
            "symbol1": {"name": "_private1", "capability": "unassigned"},  # Private
            "symbol2": {"name": "_private2", "capability": "unassigned"},  # Private
            "symbol3": {"name": "public1", "capability": "read"},  # Assigned capability
            "symbol4": {
                "name": "public2",
                "capability": "write",
            },  # Assigned capability
        }

        mock_graph = {"symbols": mock_symbols}
        mock_knowledge_service = Mock()
        mock_knowledge_service.get_graph = AsyncMock(return_value=mock_graph)

        with (
            patch(
                "features.introspection.audit_unassigned_capabilities.KnowledgeService"
            ) as mock_ks_class,
            patch(
                "features.introspection.audit_unassigned_capabilities.settings"
            ) as mock_settings,
        ):
            mock_ks_class.return_value = mock_knowledge_service
            mock_settings.REPO_PATH = "/mock/repo/path"

            result = get_unassigned_symbols()

            assert result == []
            mock_knowledge_service.get_graph.assert_called_once()

    def test_get_unassigned_symbols_empty_symbols(self):
        """Test that get_unassigned_symbols handles empty symbols dictionary."""
        mock_graph = {"symbols": {}}
        mock_knowledge_service = Mock()
        mock_knowledge_service.get_graph = AsyncMock(return_value=mock_graph)

        with (
            patch(
                "features.introspection.audit_unassigned_capabilities.KnowledgeService"
            ) as mock_ks_class,
            patch(
                "features.introspection.audit_unassigned_capabilities.settings"
            ) as mock_settings,
        ):
            mock_ks_class.return_value = mock_knowledge_service
            mock_settings.REPO_PATH = "/mock/repo/path"

            result = get_unassigned_symbols()

            assert result == []
            mock_knowledge_service.get_graph.assert_called_once()

    def test_get_unassigned_symbols_missing_symbols_key(self):
        """Test that get_unassigned_symbols handles missing symbols key in graph."""
        mock_graph = {}  # No symbols key
        mock_knowledge_service = Mock()
        mock_knowledge_service.get_graph = AsyncMock(return_value=mock_graph)

        with (
            patch(
                "features.introspection.audit_unassigned_capabilities.KnowledgeService"
            ) as mock_ks_class,
            patch(
                "features.introspection.audit_unassigned_capabilities.settings"
            ) as mock_settings,
        ):
            mock_ks_class.return_value = mock_knowledge_service
            mock_settings.REPO_PATH = "/mock/repo/path"

            result = get_unassigned_symbols()

            assert result == []
            mock_knowledge_service.get_graph.assert_called_once()

    def test_get_unassigned_symbols_missing_capability_field(self):
        """Test that get_unassigned_symbols handles symbols missing capability field."""
        mock_symbols = {
            "symbol1": {"name": "public_func"},  # Missing capability field
            "symbol2": {"name": "another_public", "capability": "unassigned"},  # Valid
        }

        mock_graph = {"symbols": mock_symbols}
        mock_knowledge_service = Mock()
        mock_knowledge_service.get_graph = AsyncMock(return_value=mock_graph)

        with (
            patch(
                "features.introspection.audit_unassigned_capabilities.KnowledgeService"
            ) as mock_ks_class,
            patch(
                "features.introspection.audit_unassigned_capabilities.settings"
            ) as mock_settings,
        ):
            mock_ks_class.return_value = mock_knowledge_service
            mock_settings.REPO_PATH = "/mock/repo/path"

            result = get_unassigned_symbols()

            # Only symbol2 should be included
            assert len(result) == 1
            assert result[0]["key"] == "symbol2"
            assert result[0]["name"] == "another_public"
            assert result[0]["capability"] == "unassigned"

    def test_get_unassigned_symbols_missing_name_field(self):
        """Test that get_unassigned_symbols handles symbols missing name field."""
        mock_symbols = {
            "symbol1": {"capability": "unassigned"},  # Missing name field
            "symbol2": {"name": "public_func", "capability": "unassigned"},  # Valid
        }

        mock_graph = {"symbols": mock_symbols}
        mock_knowledge_service = Mock()
        mock_knowledge_service.get_graph = AsyncMock(return_value=mock_graph)

        with (
            patch(
                "features.introspection.audit_unassigned_capabilities.KnowledgeService"
            ) as mock_ks_class,
            patch(
                "features.introspection.audit_unassigned_capabilities.settings"
            ) as mock_settings,
        ):
            mock_ks_class.return_value = mock_knowledge_service
            mock_settings.REPO_PATH = "/mock/repo/path"

            result = get_unassigned_symbols()

            # Only symbol2 should be included (symbol1 has no name, so we can't determine if it's public)
            assert len(result) == 1
            assert result[0]["key"] == "symbol2"
            assert result[0]["name"] == "public_func"
            assert result[0]["capability"] == "unassigned"

    def test_get_unassigned_symbols_exception_handling(self):
        """Test that get_unassigned_symbols handles exceptions gracefully."""
        mock_knowledge_service = Mock()
        mock_knowledge_service.get_graph = AsyncMock(
            side_effect=Exception("Test error")
        )

        with (
            patch(
                "features.introspection.audit_unassigned_capabilities.KnowledgeService"
            ) as mock_ks_class,
            patch(
                "features.introspection.audit_unassigned_capabilities.settings"
            ) as mock_settings,
            # CORRECTED: Patch 'logger' instead of 'log'
            patch(
                "features.introspection.audit_unassigned_capabilities.logger"
            ) as mock_logger,
        ):
            mock_ks_class.return_value = mock_knowledge_service
            mock_settings.REPO_PATH = "/mock/repo/path"

            result = get_unassigned_symbols()

            assert result == []
            # CORRECTED: Assert against the correct mock object
            mock_logger.error.assert_called_once_with(
                "Error processing knowledge graph: Test error"
            )

    def test_get_unassigned_symbols_key_added_to_result(self):
        """Test that the symbol key is properly added to each result dictionary."""
        mock_symbols = {
            "test.symbol.key": {"name": "public_func", "capability": "unassigned"},
            "another.symbol.key": {
                "name": "another_public",
                "capability": "unassigned",
            },
        }

        mock_graph = {"symbols": mock_symbols}
        mock_knowledge_service = Mock()
        mock_knowledge_service.get_graph = AsyncMock(return_value=mock_graph)

        with (
            patch(
                "features.introspection.audit_unassigned_capabilities.KnowledgeService"
            ) as mock_ks_class,
            patch(
                "features.introspection.audit_unassigned_capabilities.settings"
            ) as mock_settings,
        ):
            mock_ks_class.return_value = mock_knowledge_service
            mock_settings.REPO_PATH = "/mock/repo/path"

            result = get_unassigned_symbols()

            assert len(result) == 2
            assert result[0]["key"] == "test.symbol.key"
            assert result[1]["key"] == "another.symbol.key"
            # Original data should remain unchanged
            assert result[0]["name"] == "public_func"
            assert result[0]["capability"] == "unassigned"
