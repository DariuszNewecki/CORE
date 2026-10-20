from __future__ import annotations

from unittest.mock import patch

import pytest

from api.v1.fix_routes import list_actions


@pytest.mark.asyncio
# ID: 6d59344f-2fd3-4d6c-9522-e7d64b01f638
async def test_list_actions():
    mock_actions = [
        {"name": "action1", "description": "Test action 1"},
        {"name": "action2", "description": "Test action 2"},
    ]
    with patch("api.v1.fix_routes.list_action_definitions", return_value=mock_actions):
        result = await list_actions()

    assert result == {"count": 2, "actions": mock_actions}


from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from api.v1.fix_routes import get_fix_run


# ID: e2f8790e-6c3d-4bca-a63a-9a269cccce85
async def test_get_fix_run() -> None:
    run_id = uuid4()

    row = {
        "id": run_id,
        "kind": "applier",
        "fix_id": "fix-123",
        "target_files": ["a.py", "b.py"],
        "write": True,
        "status": "succeeded",
        "requested_by": "alice",
        "requested_at": datetime(2024, 1, 1, 12, 0, 0),
        "started_at": datetime(2024, 1, 1, 12, 0, 5),
        "finished_at": datetime(2024, 1, 1, 12, 0, 10),
        "result": {"ok": True},
        "error": None,
    }

    mappings = MagicMock()
    mappings.first = MagicMock(return_value=row)

    execute_result = MagicMock()
    execute_result.mappings = MagicMock(return_value=mappings)

    session = MagicMock()
    session.execute = AsyncMock(return_value=execute_result)

    response = await get_fix_run(run_id, session)

    assert response["run_id"] == str(run_id)
    assert response["kind"] == "applier"
    assert response["fix_id"] == "fix-123"
    assert response["target_files"] == ["a.py", "b.py"]
    assert response["write"] is True
    assert response["status"] == "succeeded"
    assert response["requested_by"] == "alice"
    assert response["requested_at"] == "2024-01-01T12:00:00"
    assert response["started_at"] == "2024-01-01T12:00:05"
    assert response["finished_at"] == "2024-01-01T12:00:10"
    assert response["result"] == {"ok": True}
    assert response["error"] is None
    session.execute.assert_awaited_once()
