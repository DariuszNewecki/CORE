# tests/core/test_cognitive_service.py
import pytest
from sqlalchemy import insert

from services.database.models import CognitiveRole, LlmResource


@pytest.mark.anyio
async def test_cognitive_service_selects_cheapest_model(
    mock_core_env, get_test_session, monkeypatch
):
    from core.cognitive_service import CognitiveService

    monkeypatch.setenv("CHEAP_API_URL", "http://cheap.api")
    monkeypatch.setenv("CHEAP_API_KEY", "cheap_key")
    monkeypatch.setenv("CHEAP_MODEL_NAME", "cheap-model")
    monkeypatch.setenv("EXPENSIVE_API_URL", "http://expensive.api")
    monkeypatch.setenv("EXPENSIVE_API_KEY", "expensive_key")
    monkeypatch.setenv("EXPENSIVE_MODEL_NAME", "expensive-model")

    resources = [
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
    roles = [{"role": "TestRole", "required_capabilities": ["nlu"]}]
    await get_test_session.execute(insert(LlmResource), resources)
    await get_test_session.execute(insert(CognitiveRole), roles)
    await get_test_session.commit()

    service = CognitiveService(mock_core_env)
    client = service.get_client_for_role("TestRole")
    assert client.model_name == "cheap-model"
