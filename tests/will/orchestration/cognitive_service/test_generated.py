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


# ID: fdbd3e42-eff0-45b9-876a-d20b18e254df
async def test_CognitiveService_reload():
    service = CognitiveService(repo_path=Path("/tmp/repo"))

    service._loaded = True

    init_mock = AsyncMock()
    service.initialize = init_mock

    session = MagicMock()

    await service.reload(session)

    assert service._loaded is False
    init_mock.assert_awaited_once_with(session)


import pytest


@pytest.mark.asyncio
# ID: 4744184c-684b-4b79-a33b-8097dde3c662
async def test_CognitiveService_get_embed_model_revision():
    service = CognitiveService(repo_path=Path("/tmp/repo"))

    mock_config = MagicMock()
    mock_config.get = AsyncMock(return_value="rev-abc123")
    service._config = mock_config

    service._require_ready = MagicMock(return_value=None)

    result = await service.get_embed_model_revision()

    assert result == "rev-abc123"
    service._require_ready.assert_called_once()
    mock_config.get.assert_awaited_once_with("embed_model.revision")


import pytest


@pytest.mark.asyncio
# ID: 660d6a3e-8d54-4ab7-b810-bf24c8820f4f
async def test_CognitiveService_aget_vectorizer_client() -> None:
    service = CognitiveService(repo_path=Path("/tmp/repo"))

    expected_client = MagicMock(name="vectorizer_llm_client")
    service.aget_client_for_role = AsyncMock(return_value=expected_client)

    result = await service.aget_vectorizer_client()

    service.aget_client_for_role.assert_awaited_once_with("Vectorizer")
    assert result is expected_client


import asyncio
from unittest.mock import patch


# ID: c7a02feb-d0b9-4f91-a173-1d0c6ff179eb
def test_CognitiveService_initialize():
    async def _run():
        repo_path = Path("/tmp/repo")
        service = CognitiveService(repo_path=repo_path)

        session = MagicMock()

        mock_config = MagicMock()
        mock_config.detach = MagicMock()

        mock_mind_state = MagicMock()
        mock_mind_state.detach = MagicMock()

        mock_orch = MagicMock()
        mock_orch.initialize = AsyncMock()

        with (
            patch(
                "will.orchestration.cognitive_service.ConfigService"
            ) as ConfigServiceCls,
            patch(
                "will.orchestration.cognitive_service.MindStateService"
            ) as MindStateCls,
            patch(
                "will.orchestration.cognitive_service.CognitiveOrchestrator"
            ) as OrchCls,
        ):
            ConfigServiceCls.create = AsyncMock(return_value=mock_config)
            MindStateCls.return_value = mock_mind_state
            OrchCls.return_value = mock_orch

            await service.initialize(session)

        ConfigServiceCls.create.assert_awaited_once_with(session)
        MindStateCls.assert_called_once_with(session)
        OrchCls.assert_called_once()
        mock_orch.initialize.assert_awaited_once()

        mock_config.detach.assert_called_once_with()
        mock_mind_state.detach.assert_called_once_with()

        assert service._loaded is True
        assert service._config is mock_config
        assert service._mind_state is mock_mind_state
        assert service._orch is mock_orch

    asyncio.run(_run())
