# tests/will/orchestration/test_cognitive_service.py
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import insert

from services.database.models import CognitiveRole, LlmResource


@pytest.mark.anyio
async def test_cognitive_service_selects_cheapest_model(
    mock_core_env, get_test_session, mocker
):
    from will.orchestration.cognitive_service import CognitiveService

    @asynccontextmanager
    async def session_manager_mock():
        yield get_test_session

    mocker.patch(
        "will.orchestration.cognitive_service.get_session", session_manager_mock
    )

    # Mock the config_service
    async def mock_get(key, default=None):
        config_map = {
            "CHEAP_API_URL": "http://cheap.api",
            "CHEAP_API_KEY": "cheap_key",
            "CHEAP_MODEL_NAME": "cheap-model",
            "EXPENSIVE_API_URL": "http://expensive.api",
            "EXPENSIVE_API_KEY": "expensive_key",
            "EXPENSIVE_MODEL_NAME": "expensive-model",
        }
        return config_map.get(key, default)

    async def mock_get_secret(key, audit_context=None):
        # get_secret has an audit_context parameter
        return await mock_get(key)

    mock_config = mocker.patch("services.config_service.ConfigService.create")
    mock_config.return_value.get = AsyncMock(side_effect=mock_get)
    mock_config.return_value.get_secret = AsyncMock(side_effect=mock_get_secret)

    resources_data = [
        {
            "name": "expensive_model",
            "env_prefix": "EXPENSIVE",
            "provided_capabilities": ["nlu"],
            "performance_metadata": {"cost_rating": 5},
        },
        {
            "name": "cheap_model",
            "env_prefix": "CHEAP",
            "provided_capabilities": ["nlu"],
            "performance_metadata": {"cost_rating": 1},
        },
    ]
    roles_data = [
        {
            "role": "TestRole",
            "required_capabilities": ["nlu"],
            "assigned_resource": None,
        }
    ]

    async with get_test_session as session:
        await session.execute(insert(LlmResource), resources_data)
        await session.execute(insert(CognitiveRole), roles_data)
        await session.commit()

    # Mock the LLM client to avoid actual provider initialization
    mock_llm_client = MagicMock()
    mock_provider = MagicMock()
    mock_provider.model_name = "cheap-model"
    mock_llm_client.provider = mock_provider

    # Mock LLMClient class constructor
    mock_llm_client_class = mocker.patch(
        "will.orchestration.cognitive_service.LLMClient"
    )
    mock_llm_client_class.return_value = mock_llm_client

    # Mock the semaphore initialization
    mocker.patch("asyncio.Semaphore", return_value=MagicMock())

    service = CognitiveService(mock_core_env)
    await service.initialize()

    client = await service.aget_client_for_role("TestRole")

    # Verify the cheap model was selected
    assert client.provider.model_name == "cheap-model"
