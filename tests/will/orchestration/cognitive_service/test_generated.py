from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from will.orchestration.cognitive_service import CognitiveService


@pytest.mark.asyncio
# ID: 573bc67a-84da-48e8-897e-e5bbf4975c67
async def test_CognitiveService_aget_client_for_role():
    service = CognitiveService(repo_path=Path("/tmp/repo"))

    mock_orch = MagicMock()
    sentinel_client = object()
    mock_orch.get_client_for_role = AsyncMock(return_value=sentinel_client)

    service._require_ready = MagicMock(return_value=None)
    service._orch = mock_orch

    result = await service.aget_client_for_role("planner", high_reasoning=True)

    assert result is sentinel_client
    service._require_ready.assert_called_once_with()
    mock_orch.get_client_for_role.assert_awaited_once_with(
        "planner", high_reasoning=True
    )
