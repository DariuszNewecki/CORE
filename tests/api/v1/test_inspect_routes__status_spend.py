# tests/api/v1/test_inspect_routes__status_spend.py

"""GET /v1/status/spend forwards to get_spend and returns its payload."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from api.v1.inspect_routes import status_spend


# ID: 8b2f6d14-7c3a-4e95-b1d0-9a6e3c5f2b87
async def test_status_spend_delegates_to_facade() -> None:
    session = MagicMock()
    with patch(
        "api.v1.inspect_routes.get_spend",
        new=AsyncMock(return_value={"days": 3, "usd": 0.01}),
    ) as facade:
        out = await status_spend(days=3, session=session)
    facade.assert_awaited_once_with(session, 3)
    assert out == {"days": 3, "usd": 0.01}
