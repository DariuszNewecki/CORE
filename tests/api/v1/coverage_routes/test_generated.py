from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from api.v1.coverage_routes import interactive_tests


@pytest.mark.asyncio
# ID: bc68649d-3378-4641-b1bb-91cadaceb691
async def test_interactive_tests():
    mock_request = MagicMock(spec=Request)
    mock_core_context = MagicMock()
    mock_request.app.state.core_context = mock_core_context

    mock_payload = MagicMock()
    mock_payload.target_file = "some/path.py"

    expected_result = {"status": "ok", "test_cases": ["test_a", "test_b"]}
    mock_run_tests = AsyncMock(return_value=expected_result)

    with patch("api.v1.coverage_routes.run_tests_interactive", mock_run_tests):
        result = await interactive_tests(request=mock_request, payload=mock_payload)

    assert result == expected_result
    mock_run_tests.assert_awaited_once_with(
        mock_core_context, target_file=mock_payload.target_file
    )
