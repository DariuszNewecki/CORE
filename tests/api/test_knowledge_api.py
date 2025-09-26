# tests/api/test_knowledge_api.py
"""
Tests for the /knowledge API endpoints.
"""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from core.main import app


# Use pytest.mark.anyio to run this test in an async context
@pytest.mark.anyio
async def test_list_capabilities_endpoint(mocker):
    """
    Tests the GET /knowledge/capabilities endpoint, mocking the service layer.
    """
    # 1. Arrange: Mock the KnowledgeService's async method to return a specific list.
    expected_capabilities = ["system.test.alpha", "system.test.beta"]
    mocker.patch(
        "core.knowledge_service.KnowledgeService.list_capabilities",
        new_callable=AsyncMock,
        return_value=expected_capabilities,
    )

    # 2. Act: Use the TestClient within the app's lifespan context manager.
    # This ensures the startup events (and service initializations) are run.
    with TestClient(app) as client:
        response = client.get("/knowledge/capabilities")

    # 3. Assert: Check the response.
    assert response.status_code == 200
    response_data = response.json()

    assert "capabilities" in response_data
    assert response_data["capabilities"] == expected_capabilities
