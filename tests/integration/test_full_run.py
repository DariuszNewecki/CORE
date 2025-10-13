# tests/integration/test_full_run.py
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from services.database.models import CognitiveRole, LlmResource
from sqlalchemy import insert


@pytest.mark.anyio
async def test_execute_goal_end_to_end(mock_core_env, get_test_session, mocker):
    from core.main import create_app

    mock_develop = mocker.patch(
        "features.autonomy.autonomous_developer.develop_from_goal",
        new_callable=AsyncMock,
    )

    @asynccontextmanager
    async def session_manager_mock():
        yield get_test_session

    mocker.patch(
        "api.v1.development_routes.get_db_session", return_value=get_test_session
    )
    mocker.patch("core.cognitive_service.get_session", session_manager_mock)
    # Patch knowledge_service's get_session instead of audit_context
    mocker.patch("core.knowledge_service.get_session", session_manager_mock)

    # Mock config_service for cognitive service initialization
    async def mock_get(key, default=None):
        config_map = {
            "TEST_API_URL": "http://test.api",
            "TEST_API_KEY": "test_key",
            "TEST_MODEL_NAME": "test-model",
        }
        return config_map.get(key, default)

    mock_config = mocker.patch("core.cognitive_service.config_service")
    mock_config.get = AsyncMock(side_effect=mock_get)

    async with get_test_session as session:
        await session.execute(
            insert(LlmResource).values(
                name="test_resource",
                env_prefix="TEST",
                provided_capabilities=["planning"],
            )
        )
        await session.execute(
            insert(CognitiveRole).values(
                role="AutonomousDeveloper", assigned_resource="test_resource"
            )
        )
        await session.commit()

    app = create_app()

    # Manually trigger the lifespan
    async with app.router.lifespan_context(app):
        # Set the test mode flag and manually initialize services
        app.state.core_context._is_test_mode = True
        await app.state.core_context.cognitive_service.initialize()
        await app.state.core_context.auditor_context.load_knowledge_graph()

        # Create client for making requests
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/develop/goal", json={"goal": "test goal"})

    assert response.status_code == 202
    assert "task_id" in response.json()
    task_id = response.json()["task_id"]

    mock_develop.assert_awaited_once()
    call_args = mock_develop.call_args[0]
    assert call_args[1] == "test goal"
    assert call_args[2] == task_id
