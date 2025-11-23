# tests/api/test_knowledge_api.py
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert

from api.main import create_app
from services.database.models import Capability
from services.database.session_manager import get_db_session


@pytest.mark.asyncio
async def test_list_capabilities_endpoint(mock_core_env, get_test_session, mocker):
    """
    Tests the /v1/knowledge/capabilities endpoint with a real test database session.
    """
    async with get_test_session.begin():
        await get_test_session.execute(
            insert(Capability).values(
                name="test.cap", title="Test Cap", owner="test", domain="test"
            )
        )

    mock_config_instance = AsyncMock()
    mock_config_instance.get.return_value = "INFO"
    mock_config_instance.get_secret.return_value = "mock_secret"
    mocker.patch(
        "services.config_service.ConfigService.create",
        return_value=mock_config_instance,
    )

    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: get_test_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            response = await client.get("/v1/knowledge/capabilities")

    assert response.status_code == 200
    assert response.json()["capabilities"] == ["test.cap"]
