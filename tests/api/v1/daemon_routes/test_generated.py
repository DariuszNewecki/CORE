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


from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
# ID: 42d5a4db-b6d2-4248-a1ba-0089140ca3e0
async def test_daemon_stop() -> None:
    from api.v1.daemon_routes import daemon_stop

    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 0
    mock_background_tasks = MagicMock()

    with patch(
        "api.v1.daemon_routes.stop_daemon_background",
        new=AsyncMock(),
    ) as mock_stop:
        result = await daemon_stop(
            request=mock_request,
            response=mock_response,
            background_tasks=mock_background_tasks,
        )

    assert result == {"status": "stopping"}
    assert mock_response.status_code == 200
    mock_background_tasks.add_task.assert_called_once_with(mock_stop)
