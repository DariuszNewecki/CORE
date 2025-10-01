# tests/core/test_cognitive_service.py
import json

import pytest
from sqlalchemy import insert

from services.database.models import CognitiveRole, LlmResource


@pytest.mark.anyio
async def test_cognitive_service_selects_cheapest_model(
    mock_core_env, get_test_session, monkeypatch, mocker
):
    from core.cognitive_service import CognitiveService

    # --- THIS IS THE CRITICAL FIX ---
    # We mock get_session at the source to ensure the CognitiveService
    # uses the same in-memory database session that our test is using.
    # This prevents the "operation is in progress" concurrency error with SQLite.
    mocker.patch("core.cognitive_service.get_session", return_value=get_test_session)
    # --- END OF CRITICAL FIX ---

    monkeypatch.setenv("CHEAP_API_URL", "http://cheap.api")
    monkeypatch.setenv("CHEAP_API_KEY", "cheap_key")
    monkeypatch.setenv("CHEAP_MODEL_NAME", "cheap-model")
    monkeypatch.setenv("EXPENSIVE_API_URL", "http://expensive.api")
    monkeypatch.setenv("EXPENSIVE_API_KEY", "expensive_key")
    monkeypatch.setenv("EXPENSIVE_MODEL_NAME", "expensive-model")

    resources_data = [
        {
            "name": "expensive_model",
            "env_prefix": "EXPENSIVE",
            "provided_capabilities": json.dumps(["nlu"]),
            "performance_metadata": json.dumps({"cost_rating": 5}),
        },
        {
            "name": "cheap_model",
            "env_prefix": "CHEAP",
            "provided_capabilities": json.dumps(["nlu"]),
            "performance_metadata": json.dumps({"cost_rating": 1}),
        },
    ]
    roles_data = [{"role": "TestRole", "required_capabilities": json.dumps(["nlu"])}]

    async with get_test_session as session:
        await session.execute(insert(LlmResource), resources_data)
        await session.execute(insert(CognitiveRole), roles_data)
        await session.commit()

    service = CognitiveService(mock_core_env)
    await service.initialize()

    client = service.get_client_for_role("TestRole")
    assert client.model_name == "cheap-model"
