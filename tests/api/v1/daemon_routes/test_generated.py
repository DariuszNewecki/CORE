from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from api.v1.daemon_routes import daemon_start


@pytest.mark.asyncio
# ID: 32cd49f6-bfa9-4c83-9729-ca9387fdd1f0
async def test_daemon_start():
    mock_result = {"ok": True, "exit_code": 0}

    with patch(
        "api.v1.daemon_routes.start_daemon", return_value=mock_result
    ) as mock_start:
        mock_request = MagicMock()
        response = await daemon_start(mock_request)

        mock_start.assert_awaited_once()
        assert response == {"status": "started", "exit_code": 0}
