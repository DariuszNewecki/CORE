from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.dependencies import get_thesis_latest


@pytest.mark.asyncio
# ID: 96cd2f8a-6712-4ba5-8a8b-9d4211d8bf61
async def test_get_thesis_latest():
    records = [{"report": "a"}, {"report": "b"}]
    mock_daily_records = AsyncMock(return_value=records)
    with patch(
        "body.services.thesis.record.daily_records",
        new=mock_daily_records,
    ):
        result = await get_thesis_latest()

    mock_daily_records.assert_awaited_once()
    assert result == {"report": "b"}
