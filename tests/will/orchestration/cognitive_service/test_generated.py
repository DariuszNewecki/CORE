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


# ID: 3f81ffc7-b529-4685-b7cc-b83c058c1b7d
def test_CognitiveService_qdrant_service():
    qdrant_service = MagicMock()
    service = CognitiveService(
        repo_path=Path("/tmp/repo"), qdrant_service=qdrant_service
    )

    result = service.qdrant_service

    assert result is qdrant_service


# ID: a04023a9-80b5-4ef7-b524-71aedb3b6c00
def test_CognitiveService() -> None:
    from will.orchestration.cognitive_service import CognitiveService

    qdrant = MagicMock()
    qdrant.search_similar = AsyncMock(return_value=[{"id": "x"}])
    service = CognitiveService(
        repo_path=Path("/tmp/repo"),
        qdrant_service=qdrant,
        session_factory=None,
    )

    async def _run() -> None:
        # Happy path: qdrant_service property returns the injected service.
        assert service.qdrant_service is qdrant

        # empty embedding path short-circuits before any client lookup.
        result = await service.get_embedding_for_code("")
        assert result is None

        # empty query short-circuits to empty list without touching qdrant.
        results = await service.search_capabilities("")
        assert results == []
        qdrant.search_similar.assert_not_called()

    asyncio.run(_run())



import pytest


@pytest.mark.asyncio
# ID: efacd8e0-06c1-48f0-acd5-b3339e3387f3
async def test_CognitiveService_search_capabilities() -> None:
    service = CognitiveService(repo_path=Path("/tmp/repo"))

    embedding = [0.1, 0.2, 0.3]
    expected_results = [{"id": "cap-1", "score": 0.99}]

    service.get_embedding_for_code = AsyncMock(return_value=embedding)

    mock_qdrant = MagicMock()
    mock_qdrant.search_similar = AsyncMock(return_value=expected_results)
    service._qdrant_service = mock_qdrant

    result = await service.search_capabilities("find me capabilities", limit=5)

    service.get_embedding_for_code.assert_awaited_once_with("find me capabilities")
    mock_qdrant.search_similar.assert_awaited_once_with(embedding, limit=5)
    assert result == expected_results
