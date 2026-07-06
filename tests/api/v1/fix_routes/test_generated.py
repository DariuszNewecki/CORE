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
