from __future__ import annotations

from unittest.mock import AsyncMock, patch

from api.v1.symbols_routes import symbols_drift


# ID: 5bbf7a7f-ffe0-4be6-8fc0-1fd92ed04bae
async def test_symbols_drift():
    mock_result = {
        "anchor_violations": 3,
        "pending_symbols": 7,
        "last_sync_at": "2025-01-01T00:00:00Z",
    }
    with patch(
        "body.introspection.drift_service.run_drift_analysis_async",
        new=AsyncMock(return_value=mock_result),
    ):
        result = await symbols_drift()

    assert result == mock_result


from unittest.mock import MagicMock

from api.v1.symbols_routes import list_unassigned_symbols


# ID: a9b73e96-5f3d-458b-bb5f-1f8c39e75f80
async def test_list_unassigned_symbols():
    # Mock the session dependency
    mock_session = MagicMock()

    # Create mock graph data
    mock_graph = {
        "symbols": {
            "sym1": {
                "name": "valid_symbol",
                "file_path": "src/module.py",
                "capability": "unassigned",
                "other_data": "value1",
            },
            "sym2": {
                "name": "_private_symbol",
                "file_path": "src/other.py",
                "capability": "unassigned",
            },
            "sym3": {
                "name": "test_symbol",
                "file_path": "tests/test_module.py",
                "capability": "unassigned",
            },
            "sym4": {
                "name": "assigned_symbol",
                "file_path": "src/assigned.py",
                "capability": "assigned",
            },
        }
    }

    # Mock KnowledgeService and its get_graph method
    with patch("api.v1.symbols_routes.KnowledgeService") as mock_knowledge_service:
        mock_graph_instance = AsyncMock()
        mock_graph_instance.get_graph.return_value = mock_graph
        mock_knowledge_service.return_value = mock_graph_instance

        # Call the function
        result = await list_unassigned_symbols(session=mock_session)

        # Verify the KnowledgeService was initialized with the session
        mock_knowledge_service.assert_called_once_with(session=mock_session)

        # Verify only the valid unassigned symbol is returned
        assert result["count"] == 1
        assert result["unassigned"] == [
            {
                "key": "sym1",
                "name": "valid_symbol",
                "file_path": "src/module.py",
                "capability": "unassigned",
                "other_data": "value1",
            }
        ]
