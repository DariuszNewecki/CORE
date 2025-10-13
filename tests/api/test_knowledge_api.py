# tests/api/test_knowledge_api.py
import pytest
from httpx import ASGITransport, AsyncClient
from services.database.models import Capability
from sqlalchemy import insert


@pytest.mark.anyio
async def test_list_capabilities_endpoint(mock_core_env, get_test_session, mocker):
    from core.main import create_app

    # Seed the database with a capability for the service to find
    async with get_test_session as session:
        await session.execute(
            insert(Capability).values(
                name="test.cap", title="Test Cap", owner="test", domain="test"
            )
        )
        await session.commit()

    app = create_app()

    # Use AsyncClient with ASGITransport for FastAPI app testing
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # The lifespan context has started, but we're in test mode
        # so we need to manually initialize services
        await app.state.core_context.cognitive_service.initialize()
        await app.state.core_context.auditor_context.load_knowledge_graph()

        # Now make the request
        response = await client.get("/v1/knowledge/capabilities")
        assert response.status_code == 200
        assert response.json()["capabilities"] == ["test.cap"]
