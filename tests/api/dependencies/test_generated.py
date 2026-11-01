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


from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
# ID: 2e83dbd6-380e-4d89-8927-290b6f78a1a2
async def test_get_secrets_service_dep():
    from api.dependencies import get_secrets_service_dep

    session = MagicMock()
    expected_service = MagicMock()

    with patch(
        "api.dependencies._get_secrets_svc",
        new=AsyncMock(return_value=expected_service),
    ) as mock_get_secrets_svc:
        result = await get_secrets_service_dep(session=session)

    assert result is expected_service
    mock_get_secrets_svc.assert_awaited_once_with(session)
