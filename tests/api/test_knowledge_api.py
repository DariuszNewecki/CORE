# tests/api/test_knowledge_api.py
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.mark.anyio
async def test_list_capabilities_endpoint(mock_core_env, mocker):
    from core.main import create_app

    mocker.patch(
        "core.knowledge_service.KnowledgeService.list_capabilities",
        new_callable=AsyncMock,
        return_value=["test.cap"],
    )
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/knowledge/capabilities")
        assert response.status_code == 200
        assert response.json()["capabilities"] == ["test.cap"]
