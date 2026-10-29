from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from api.cli.cognitive_roles_client import CognitiveRolesClient


# ID: 26bd1afe-b0df-40f8-bcde-183e101abda5
async def test_CognitiveRolesClient__project():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True})

    client = CognitiveRolesClient(facade)
    result = await client.project(write=True)

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/cognitive-roles/project",
        json={"write": True},
    )
    assert result == {"ok": True}
