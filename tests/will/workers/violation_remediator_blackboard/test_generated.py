from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from will.workers.violation_remediator_blackboard import mark_delegated


@pytest.mark.asyncio
# ID: 01d17815-f6de-42ff-b305-6ef85affcffe
async def test_mark_delegated():
    """Happy path: mark_delegated should return count of entries marked."""
    findings = [
        {"id": "finding-1", "type": "test"},
        {"id": "finding-2", "type": "test"},
    ]
    mock_service = AsyncMock()
    mock_service.mark_indeterminate = AsyncMock(return_value=len(findings))

    result = await mark_delegated(mock_service, findings)

    mock_service.mark_indeterminate.assert_awaited_once_with(["finding-1", "finding-2"])
    assert result == 2
