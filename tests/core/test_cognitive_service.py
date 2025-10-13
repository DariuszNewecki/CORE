# tests/core/test_cognitive_service.py
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from services.database.models import CognitiveRole, LlmResource
from sqlalchemy import insert


@pytest.mark.anyio
async def test_cognitive_service_selects_cheapest_model(
    mock_core_env, get_test_session, mocker
):
    from core.cognitive_service import CognitiveService

    @asynccontextmanager
    async def session_manager_mock():
        yield get_test_session

    mocker.patch("core.cognitive_service.get_session", session_manager_mock)

    # Mock the config_service - need to patch where it's imported
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

    # Patch in the cognitive_service module where it's imported
    mock_config = mocker.patch("core.cognitive_service.config_service")
    mock_config.get = AsyncMock(side_effect=mock_get)

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

    service = CognitiveService(mock_core_env)
    await service.initialize()

    client = await service.aget_client_for_role("TestRole")
    assert client.provider.model_name == "cheap-model"
