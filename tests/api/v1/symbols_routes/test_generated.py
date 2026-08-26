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
